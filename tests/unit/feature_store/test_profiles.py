"""Unit tests for ProfileRecord model and feature store profile methods.

TDD: These tests are written first to drive the implementation of:
- ProfileRecord model in models.py
- 5 new protocol methods in protocols.py
- SQLiteFeatureStore profile implementations
- NullFeatureStore profile no-op stubs
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError
import pytest

from twinklr.core.feature_store.backends.null import NullFeatureStore
from twinklr.core.feature_store.factory import create_feature_store
from twinklr.core.feature_store.models import CorpusStats, FeatureStoreConfig, ProfileRecord
from twinklr.core.feature_store.protocols import FeatureStoreProviderSync

if TYPE_CHECKING:
    from twinklr.core.feature_store.backends.sqlite import SQLiteFeatureStore


@pytest.fixture
def sqlite_store(tmp_path: Path) -> SQLiteFeatureStore:
    cfg = FeatureStoreConfig(backend="sqlite", db_path=tmp_path / "test.db")
    store = create_feature_store(cfg)
    store.initialize()
    yield store
    store.close()


def _make_profile(
    package_id: str = "pkg1",
    sequence_file_id: str = "seq1",
    profile_path: str = "/data/profiles/pkg1/seq1",
    sequence_sha256: str | None = "abc123",
    fe_status: str = "pending",
    **overrides: object,
) -> ProfileRecord:
    return ProfileRecord(
        profile_id=f"{package_id}/{sequence_file_id}",
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        profile_path=profile_path,
        sequence_sha256=sequence_sha256,
        fe_status=fe_status,
        **overrides,
    )


# ---------------------------------------------------------------------------
# Model tests (no store required)
# ---------------------------------------------------------------------------


def test_profile_record_full_fields() -> None:
    """Construct a ProfileRecord with all fields set explicitly."""
    p = ProfileRecord(
        profile_id="pkg1/seq1",
        package_id="pkg1",
        sequence_file_id="seq1",
        profile_path="/data/profiles/pkg1/seq1",
        zip_sha256="zip_hash_abc",
        sequence_sha256="seq_hash_xyz",
        song="Jingle Bells",
        artist="Various",
        duration_ms=180000,
        effect_total_events=42,
        schema_version="2.0.0",
        fe_status="complete",
        fe_error=None,
        profiled_at="2024-01-01T00:00:00",
        fe_completed_at="2024-01-01T01:00:00",
    )
    assert p.profile_id == "pkg1/seq1"
    assert p.package_id == "pkg1"
    assert p.sequence_file_id == "seq1"
    assert p.profile_path == "/data/profiles/pkg1/seq1"
    assert p.zip_sha256 == "zip_hash_abc"
    assert p.sequence_sha256 == "seq_hash_xyz"
    assert p.song == "Jingle Bells"
    assert p.artist == "Various"
    assert p.duration_ms == 180000
    assert p.effect_total_events == 42
    assert p.schema_version == "2.0.0"
    assert p.fe_status == "complete"
    assert p.fe_error is None
    assert p.profiled_at == "2024-01-01T00:00:00"
    assert p.fe_completed_at == "2024-01-01T01:00:00"


def test_profile_record_minimal_defaults() -> None:
    """Minimal required fields — optional fields use defaults."""
    p = ProfileRecord(
        profile_id="pkg2/seq2",
        package_id="pkg2",
        sequence_file_id="seq2",
        profile_path="/data/profiles/pkg2/seq2",
    )
    assert p.fe_status == "pending"
    assert p.schema_version == ""
    assert p.zip_sha256 is None
    assert p.sequence_sha256 is None
    assert p.song is None
    assert p.artist is None
    assert p.duration_ms is None
    assert p.effect_total_events is None
    assert p.fe_error is None
    assert p.profiled_at is None
    assert p.fe_completed_at is None


def test_profile_record_frozen_and_extra_forbid() -> None:
    """ProfileRecord is frozen (immutable) and rejects extra fields."""
    # Extra fields are forbidden.
    with pytest.raises(ValidationError):
        ProfileRecord(
            profile_id="a",
            package_id="b",
            sequence_file_id="c",
            profile_path="/d",
            extra_field="bad",
        )

    # Cannot mutate an existing instance.
    p = _make_profile()
    with pytest.raises(ValidationError):
        p.fe_status = "complete"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SQLite backend — profile method tests
# ---------------------------------------------------------------------------


def test_upsert_and_query_round_trip(sqlite_store: SQLiteFeatureStore) -> None:
    """Upsert a profile and verify it comes back via query_profiles."""
    profile = _make_profile()
    result = sqlite_store.upsert_profile(profile)
    assert result == 1

    profiles = sqlite_store.query_profiles()
    assert len(profiles) == 1
    retrieved = profiles[0]
    assert retrieved.profile_id == profile.profile_id
    assert retrieved.package_id == profile.package_id
    assert retrieved.sequence_file_id == profile.sequence_file_id
    assert retrieved.profile_path == profile.profile_path
    assert retrieved.sequence_sha256 == profile.sequence_sha256
    assert retrieved.fe_status == "pending"


def test_query_profiles_filter_pending(sqlite_store: SQLiteFeatureStore) -> None:
    """Insert pending and complete profiles — filter returns only pending."""
    pending = _make_profile(package_id="pkg1", sequence_file_id="seq1", fe_status="pending")
    complete = _make_profile(package_id="pkg2", sequence_file_id="seq2", fe_status="complete")
    sqlite_store.upsert_profile(pending)
    sqlite_store.upsert_profile(complete)

    results = sqlite_store.query_profiles(fe_status="pending")
    assert len(results) == 1
    assert results[0].fe_status == "pending"
    assert results[0].profile_id == "pkg1/seq1"


def test_query_profiles_filter_complete(sqlite_store: SQLiteFeatureStore) -> None:
    """Insert pending and complete profiles — filter returns only complete."""
    pending = _make_profile(package_id="pkg1", sequence_file_id="seq1", fe_status="pending")
    complete = _make_profile(package_id="pkg2", sequence_file_id="seq2", fe_status="complete")
    sqlite_store.upsert_profile(pending)
    sqlite_store.upsert_profile(complete)

    results = sqlite_store.query_profiles(fe_status="complete")
    assert len(results) == 1
    assert results[0].fe_status == "complete"
    assert results[0].profile_id == "pkg2/seq2"


def test_query_profiles_no_filter(sqlite_store: SQLiteFeatureStore) -> None:
    """No filter — all profiles are returned."""
    sqlite_store.upsert_profile(
        _make_profile(package_id="pkg1", sequence_file_id="seq1", fe_status="pending")
    )
    sqlite_store.upsert_profile(
        _make_profile(package_id="pkg2", sequence_file_id="seq2", fe_status="complete")
    )
    sqlite_store.upsert_profile(
        _make_profile(package_id="pkg3", sequence_file_id="seq3", fe_status="error")
    )

    results = sqlite_store.query_profiles()
    assert len(results) == 3


def test_query_profile_by_sha_found(sqlite_store: SQLiteFeatureStore) -> None:
    """SHA lookup returns the matching ProfileRecord."""
    profile = _make_profile(sequence_sha256="deadbeef")
    sqlite_store.upsert_profile(profile)

    result = sqlite_store.query_profile_by_sha("deadbeef")
    assert result is not None
    assert result.sequence_sha256 == "deadbeef"
    assert result.profile_id == profile.profile_id


def test_query_profile_by_sha_not_found(sqlite_store: SQLiteFeatureStore) -> None:
    """Unknown SHA returns None."""
    result = sqlite_store.query_profile_by_sha("nonexistent_sha")
    assert result is None


def test_mark_fe_complete(sqlite_store: SQLiteFeatureStore) -> None:
    """mark_fe_complete sets fe_status='complete' and populates fe_completed_at."""
    profile = _make_profile(fe_status="pending")
    sqlite_store.upsert_profile(profile)

    sqlite_store.mark_fe_complete(profile.profile_id)

    results = sqlite_store.query_profiles()
    assert len(results) == 1
    updated = results[0]
    assert updated.fe_status == "complete"
    assert updated.fe_completed_at is not None


def test_mark_fe_error(sqlite_store: SQLiteFeatureStore) -> None:
    """mark_fe_error sets fe_status='error' and stores the error message."""
    profile = _make_profile(fe_status="pending")
    sqlite_store.upsert_profile(profile)

    sqlite_store.mark_fe_error(profile.profile_id, "Something went wrong")

    results = sqlite_store.query_profiles()
    assert len(results) == 1
    updated = results[0]
    assert updated.fe_status == "error"
    assert updated.fe_error == "Something went wrong"


def test_upsert_idempotent(sqlite_store: SQLiteFeatureStore) -> None:
    """Upserting the same profile_id twice results in exactly one row."""
    profile = _make_profile()
    sqlite_store.upsert_profile(profile)
    sqlite_store.upsert_profile(profile)

    results = sqlite_store.query_profiles()
    assert len(results) == 1


def test_corpus_stats_includes_profile_count(sqlite_store: SQLiteFeatureStore) -> None:
    """After upserting a profile, get_corpus_stats().profile_count == 1."""
    profile = _make_profile()
    sqlite_store.upsert_profile(profile)

    stats = sqlite_store.get_corpus_stats()
    assert isinstance(stats, CorpusStats)
    assert stats.profile_count == 1


# ---------------------------------------------------------------------------
# Null backend — protocol conformance
# ---------------------------------------------------------------------------


def test_null_backend_protocol_conformance() -> None:
    """NullFeatureStore satisfies the protocol and returns correct types for profile methods."""
    store = NullFeatureStore()
    assert isinstance(store, FeatureStoreProviderSync)

    profile = _make_profile()

    # upsert returns 0
    result = store.upsert_profile(profile)
    assert result == 0

    # query returns empty tuple
    profiles = store.query_profiles()
    assert profiles == ()
    profiles_filtered = store.query_profiles(fe_status="pending")
    assert profiles_filtered == ()

    # SHA lookup returns None
    found = store.query_profile_by_sha("any_sha")
    assert found is None

    # Mark methods are no-ops (should not raise)
    store.mark_fe_complete(profile.profile_id)
    store.mark_fe_error(profile.profile_id, "error msg")
