"""Tests for feature store bootstrap utilities (Phase 2B).

Covers SchemaBootstrapper and ReferenceDataLoader.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from twinklr.core.feature_store.bootstrap.loader import ReferenceDataLoader
from twinklr.core.feature_store.bootstrap.schema import SchemaBootstrapper

# ---------------------------------------------------------------------------
# SchemaBootstrapper tests
# ---------------------------------------------------------------------------


def _make_conn() -> sqlite3.Connection:
    """Create an in-memory SQLite connection."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _table_names(conn: sqlite3.Connection) -> set[str]:
    """Return set of all table names in the database."""
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}


def _index_names(conn: sqlite3.Connection) -> set[str]:
    """Return set of all index names in the database."""
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    return {row[0] for row in rows}


def test_bootstrapper_creates_all_tables() -> None:
    """Bootstrap on a fresh DB creates all 11 expected tables."""
    conn = _make_conn()
    SchemaBootstrapper(conn).bootstrap()

    tables = _table_names(conn)
    expected = {
        "phrases",
        "templates",
        "template_assignments",
        "stacks",
        "transitions",
        "recipes",
        "taxonomy",
        "propensity",
        "corpus_metadata",
        "reference_data",
        "schema_info",
    }
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"


def test_bootstrapper_creates_indexes() -> None:
    """Bootstrap creates all expected indexes."""
    conn = _make_conn()
    SchemaBootstrapper(conn).bootstrap()

    indexes = _index_names(conn)
    # Check a representative subset of expected indexes
    expected_prefixes = {
        "idx_phrases_",
        "idx_templates_",
        "idx_stacks_",
        "idx_transitions_",
        "idx_recipes_",
        "idx_taxonomy_",
        "idx_propensity_",
    }
    for prefix in expected_prefixes:
        assert any(name.startswith(prefix) for name in indexes), (
            f"No index with prefix {prefix!r} found. Indexes: {indexes}"
        )


def test_bootstrapper_sets_version() -> None:
    """Bootstrap sets schema_info version to '1.0.0'."""
    conn = _make_conn()
    bootstrapper = SchemaBootstrapper(conn)
    bootstrapper.bootstrap(version="1.0.0")

    row = conn.execute("SELECT value FROM schema_info WHERE key='version'").fetchone()
    assert row is not None
    assert row[0] == "1.0.0"


def test_check_version_matches() -> None:
    """check_version returns True when stored version matches expected."""
    conn = _make_conn()
    bootstrapper = SchemaBootstrapper(conn)
    bootstrapper.bootstrap(version="1.0.0")

    assert bootstrapper.check_version("1.0.0") is True


def test_check_version_mismatch() -> None:
    """check_version returns False when stored version differs from expected."""
    conn = _make_conn()
    bootstrapper = SchemaBootstrapper(conn)
    bootstrapper.bootstrap(version="1.0.0")

    assert bootstrapper.check_version("2.0.0") is False


def test_bootstrap_is_idempotent() -> None:
    """Running bootstrap twice on the same DB does not raise."""
    conn = _make_conn()
    bootstrapper = SchemaBootstrapper(conn)
    bootstrapper.bootstrap(version="1.0.0")
    bootstrapper.bootstrap(version="1.0.0")  # Should not raise

    tables = _table_names(conn)
    assert "phrases" in tables


def test_get_version_returns_stored() -> None:
    """get_version returns the stored version string."""
    conn = _make_conn()
    bootstrapper = SchemaBootstrapper(conn)
    bootstrapper.bootstrap(version="1.0.0")

    assert bootstrapper.get_version() == "1.0.0"


def test_get_version_returns_none_before_bootstrap() -> None:
    """get_version returns None when schema_info has no version entry."""
    conn = _make_conn()
    # Only ensure schema_info exists with no version row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_info (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    bootstrapper = SchemaBootstrapper(conn)

    assert bootstrapper.get_version() is None


def test_needs_migration_false_when_matching() -> None:
    """needs_migration returns False when version matches expected."""
    conn = _make_conn()
    bootstrapper = SchemaBootstrapper(conn)
    bootstrapper.bootstrap(version="1.0.0")

    assert bootstrapper.needs_migration("1.0.0") is False


def test_needs_migration_true_when_different() -> None:
    """needs_migration returns True when version differs."""
    conn = _make_conn()
    bootstrapper = SchemaBootstrapper(conn)
    bootstrapper.bootstrap(version="1.0.0")

    assert bootstrapper.needs_migration("2.0.0") is True


# ---------------------------------------------------------------------------
# ReferenceDataLoader tests
# ---------------------------------------------------------------------------


def _bootstrapped_conn() -> sqlite3.Connection:
    """Return a bootstrapped in-memory connection with reference_data table."""
    conn = _make_conn()
    SchemaBootstrapper(conn).bootstrap()
    return conn


def test_reference_loader_loads_files(tmp_path: Path) -> None:
    """load_directory loads all JSON files from the directory."""
    (tmp_path / "colors.json").write_text(json.dumps({"data": "red"}))
    (tmp_path / "palettes.json").write_text(json.dumps({"data": "warm"}))

    conn = _bootstrapped_conn()
    loader = ReferenceDataLoader(conn)
    count = loader.load_directory(tmp_path)

    assert count == 2
    row = conn.execute("SELECT data_json FROM reference_data WHERE data_key='colors'").fetchone()
    assert row is not None
    assert json.loads(row[0]) == {"data": "red"}


def test_reference_loader_empty_dir(tmp_path: Path) -> None:
    """load_directory returns 0 for an empty directory."""
    conn = _bootstrapped_conn()
    loader = ReferenceDataLoader(conn)
    count = loader.load_directory(tmp_path)

    assert count == 0


def test_reference_loader_missing_dir(tmp_path: Path) -> None:
    """load_directory returns 0 for a nonexistent directory."""
    conn = _bootstrapped_conn()
    loader = ReferenceDataLoader(conn)
    count = loader.load_directory(tmp_path / "does_not_exist")

    assert count == 0


def test_reference_loader_extracts_version(tmp_path: Path) -> None:
    """JSON with top-level 'version' field is stored with that version."""
    (tmp_path / "effects.json").write_text(json.dumps({"version": "2.3.1", "data": [1, 2, 3]}))

    conn = _bootstrapped_conn()
    loader = ReferenceDataLoader(conn)
    loader.load_directory(tmp_path)

    row = conn.execute("SELECT version FROM reference_data WHERE data_key='effects'").fetchone()
    assert row is not None
    assert row[0] == "2.3.1"


def test_reference_loader_default_version_empty(tmp_path: Path) -> None:
    """JSON without 'version' field is stored with empty version string."""
    (tmp_path / "data.json").write_text(json.dumps({"items": []}))

    conn = _bootstrapped_conn()
    loader = ReferenceDataLoader(conn)
    loader.load_directory(tmp_path)

    row = conn.execute("SELECT version FROM reference_data WHERE data_key='data'").fetchone()
    assert row is not None
    assert row[0] == ""


def test_reference_loader_upserts_on_reload(tmp_path: Path) -> None:
    """Loading the same file twice updates the existing row."""
    data_file = tmp_path / "effects.json"
    data_file.write_text(json.dumps({"v": 1}))

    conn = _bootstrapped_conn()
    loader = ReferenceDataLoader(conn)
    loader.load_directory(tmp_path)

    data_file.write_text(json.dumps({"v": 2}))
    loader.load_directory(tmp_path)

    row = conn.execute("SELECT data_json FROM reference_data WHERE data_key='effects'").fetchone()
    assert json.loads(row[0]) == {"v": 2}
