"""Schema bootstrapper for the SQLite feature store.

Reads DDL from JSON schema files and applies them to a SQLite connection.
This is the only place that creates tables, views, and indexes — no
hardcoded DDL lives in the backend module (except the minimal schema_info
bootstrap check performed here).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

# Default schema directory: schemas/ alongside the feature_store package root.
_DEFAULT_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"

# Minimal hardcoded DDL for the bootstrap-sentinel table only.
_SCHEMA_INFO_DDL = (
    "CREATE TABLE IF NOT EXISTS schema_info (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
)


class SchemaBootstrapper:
    """Applies JSON-defined DDL to a SQLite connection.

    Args:
        conn: Open SQLite connection.
        schema_dir: Directory containing ``tables.json``, ``views.json``,
            and ``indexes.json``. Defaults to the ``schemas/`` directory
            alongside the feature_store package.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        schema_dir: Path | None = None,
    ) -> None:
        self._conn = conn
        self._schema_dir = schema_dir if schema_dir is not None else _DEFAULT_SCHEMA_DIR

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def bootstrap(self, version: str = "1.0.0") -> None:
        """Create all tables, views, and indexes; set schema version.

        Safe to call on an existing database — all DDL uses ``IF NOT EXISTS``
        semantics so repeated calls are idempotent.

        Args:
            version: Schema version string to record in ``schema_info``.
        """
        self._ensure_schema_info()
        tables = self._load_json("tables.json")
        views = self._load_json("views.json")
        indexes = self._load_json("indexes.json")

        with self._conn:
            for table in tables:
                ddl = self._build_table_ddl(table)
                self._conn.execute(ddl)
            for view in views:
                ddl = self._build_view_ddl(view)
                self._conn.execute(ddl)
            for index in indexes:
                ddl = self._build_index_ddl(index)
                self._conn.execute(ddl)
            self._conn.execute(
                "INSERT OR REPLACE INTO schema_info (key, value) VALUES ('version', ?)",
                (version,),
            )

    def check_version(self, expected: str) -> bool:
        """Return True if the stored schema version matches *expected*.

        Args:
            expected: Version string to compare against (e.g. ``"1.0.0"``).

        Returns:
            ``True`` when versions match, ``False`` otherwise.
        """
        stored = self.get_version()
        return stored == expected

    def get_version(self) -> str | None:
        """Return the stored schema version, or ``None`` if not set.

        Returns:
            Version string from ``schema_info``, or ``None``.
        """
        self._ensure_schema_info()
        row = self._conn.execute("SELECT value FROM schema_info WHERE key='version'").fetchone()
        if row is None:
            return None
        return str(row[0])

    def needs_migration(self, expected: str) -> bool:
        """Return True when the stored version differs from *expected*.

        Args:
            expected: Expected schema version string.

        Returns:
            ``True`` when a migration is needed, ``False`` when up-to-date.
        """
        return not self.check_version(expected)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_schema_info(self) -> None:
        """Create schema_info table if it does not exist."""
        self._conn.execute(_SCHEMA_INFO_DDL)

    def _load_json(self, filename: str) -> list[Any]:
        """Load and parse a JSON schema file.

        Args:
            filename: Filename within ``schema_dir``.

        Returns:
            Parsed JSON list.
        """
        path = self._schema_dir / filename
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _build_table_ddl(table: dict[str, Any]) -> str:
        """Generate ``CREATE TABLE IF NOT EXISTS`` DDL from a table spec.

        Args:
            table: Dict with ``name``, ``columns``, and optional ``primary_key``.

        Returns:
            DDL string.
        """
        name: str = table["name"]
        columns: list[str] = table["columns"]
        composite_pk: list[str] | None = table.get("primary_key")

        col_defs = list(columns)
        if composite_pk:
            pk_cols = ", ".join(composite_pk)
            col_defs.append(f"PRIMARY KEY ({pk_cols})")

        col_block = ",\n  ".join(col_defs)
        return f"CREATE TABLE IF NOT EXISTS {name} (\n  {col_block}\n)"

    @staticmethod
    def _build_view_ddl(view: dict[str, Any]) -> str:
        """Generate ``CREATE VIEW IF NOT EXISTS`` DDL from a view spec.

        Args:
            view: Dict with ``name`` and ``sql`` keys.

        Returns:
            DDL string.
        """
        name: str = view["name"]
        sql: str = view["sql"]
        return f"CREATE VIEW IF NOT EXISTS {name} AS {sql}"

    @staticmethod
    def _build_index_ddl(index: dict[str, Any]) -> str:
        """Generate ``CREATE INDEX IF NOT EXISTS`` DDL from an index spec.

        Args:
            index: Dict with ``name``, ``table``, ``columns``, and ``unique``.

        Returns:
            DDL string.
        """
        name: str = index["name"]
        table: str = index["table"]
        columns: list[str] = index["columns"]
        unique: bool = index.get("unique", False)

        unique_kw = "UNIQUE " if unique else ""
        col_list = ", ".join(columns)
        return f"CREATE {unique_kw}INDEX IF NOT EXISTS {name} ON {table} ({col_list})"
