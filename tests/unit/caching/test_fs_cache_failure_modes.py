"""Failure-mode coverage for FSCache (P1-F29: these paths were unexercised).

Covers the public async cache lifecycle plus TTL expiry, meta/key mismatch,
corrupted artifacts and a missing commit marker. Failure modes must degrade to a
miss rather than returning stale or invalid data. This is the canonical home for
``FSCache`` coverage; it does not route through a synchronous compatibility wrapper.
"""

from __future__ import annotations

import time

from pydantic import BaseModel
import pytest

from twinklr.core.agents.audio.lyrics.stage import LYRICS_CACHE_VERSION
from twinklr.core.agents.sequencer.moving_heads.stage import MOVING_HEAD_CACHE_VERSION
from twinklr.core.caching import CacheKey, CacheMeta, FSCache
from twinklr.core.io import FakeFileSystem, absolute_path


class SampleArtifact(BaseModel):
    """Minimal cacheable payload."""

    value: str
    count: int = 0


def _key(fingerprint: str = "fp-1", version: str = "1") -> CacheKey:
    return CacheKey(
        domain="macro_plan",
        session_id="sess_abc",
        step_id="macro_plan",
        step_version=version,
        input_fingerprint=fingerprint,
    )


@pytest.fixture
def fs() -> FakeFileSystem:
    return FakeFileSystem()


@pytest.fixture
def cache(fs: FakeFileSystem) -> FSCache:
    return FSCache(fs, absolute_path("/cache"))


async def test_store_then_load_round_trips(cache: FSCache) -> None:
    key = _key()
    await cache.store(key, SampleArtifact(value="planned", count=3))

    loaded = await cache.load(key, SampleArtifact)

    assert loaded is not None
    assert loaded.value == "planned"
    assert loaded.count == 3


async def test_store_makes_entry_exist(cache: FSCache) -> None:
    key = _key()
    assert await cache.exists(key) is False

    await cache.store(key, SampleArtifact(value="stored"))

    assert await cache.exists(key) is True


async def test_load_returns_none_on_miss(cache: FSCache) -> None:
    assert await cache.load(_key(), SampleArtifact) is None


async def test_invalidate_removes_entry(cache: FSCache) -> None:
    key = _key()
    await cache.store(key, SampleArtifact(value="temporary"))

    await cache.invalidate(key)

    assert await cache.exists(key) is False


async def test_initialize_is_idempotent(cache: FSCache) -> None:
    await cache.initialize()
    await cache.initialize()


async def test_key_is_stable_across_cache_instances(fs: FakeFileSystem) -> None:
    """A second run with the same key reaches the first run's entry."""
    key = _key()
    await FSCache(fs, absolute_path("/cache")).store(key, SampleArtifact(value="first-run"))

    loaded = await FSCache(fs, absolute_path("/cache")).load(key, SampleArtifact)

    assert loaded is not None
    assert loaded.value == "first-run"


async def test_different_fingerprint_misses(cache: FSCache) -> None:
    await cache.store(_key("fp-1"), SampleArtifact(value="one"))

    assert await cache.load(_key("fp-2"), SampleArtifact) is None


@pytest.mark.parametrize(
    ("stage_name", "current_version"),
    [
        ("lyrics", LYRICS_CACHE_VERSION),
        ("moving_head_planner", MOVING_HEAD_CACHE_VERSION),
    ],
)
async def test_t4_stage_version_bump_rejects_pre_moment_cue_artifacts(
    cache: FSCache,
    stage_name: str,
    current_version: str,
) -> None:
    """A same-input v1 artifact cannot bypass T4 validation and cue binding."""
    assert current_version == "2"
    old_key = CacheKey(
        domain=stage_name,
        session_id="sess_t4",
        step_id=stage_name,
        step_version="1",
        input_fingerprint="unchanged-input-and-prompt-key",
    )
    current_key = old_key.model_copy(update={"step_version": current_version})
    await cache.store(old_key, SampleArtifact(value="pre-t4-unvalidated"))

    assert await cache.load(old_key, SampleArtifact) is not None
    assert await cache.load(current_key, SampleArtifact) is None


async def test_expired_entry_is_a_miss(fs: FakeFileSystem) -> None:
    cache = FSCache(fs, absolute_path("/cache"), ttl_seconds=60.0)
    key = _key()
    await cache.store(key, SampleArtifact(value="stale"))

    # Backdate the commit marker past the TTL.
    meta_path = cache._meta_path(key)
    meta = CacheMeta.model_validate_json(await fs.read_text(meta_path))
    aged = meta.model_copy(update={"created_at": time.time() - 3600})
    await fs.write_text(meta_path, aged.model_dump_json())

    assert await cache.exists(key) is False
    assert await cache.load(key, SampleArtifact) is None


async def test_unexpired_entry_is_a_hit(fs: FakeFileSystem) -> None:
    cache = FSCache(fs, absolute_path("/cache"), ttl_seconds=3600.0)
    key = _key()
    await cache.store(key, SampleArtifact(value="fresh"))

    loaded = await cache.load(key, SampleArtifact)

    assert loaded is not None
    assert loaded.value == "fresh"


async def test_meta_key_mismatch_is_a_miss(cache: FSCache, fs: FakeFileSystem) -> None:
    """Meta recorded under a different step version must not be served."""
    key = _key(version="1")
    await cache.store(key, SampleArtifact(value="v1"))

    meta_path = cache._meta_path(key)
    meta = CacheMeta.model_validate_json(await fs.read_text(meta_path))
    await fs.write_text(meta_path, meta.model_copy(update={"step_version": "9"}).model_dump_json())

    assert await cache.load(key, SampleArtifact) is None


async def test_corrupted_artifact_is_a_miss(cache: FSCache, fs: FakeFileSystem) -> None:
    key = _key()
    await cache.store(key, SampleArtifact(value="good"))
    await fs.write_text(cache._artifact_path(key), "{not valid json")

    assert await cache.load(key, SampleArtifact) is None


async def test_artifact_failing_schema_validation_is_a_miss(
    cache: FSCache, fs: FakeFileSystem
) -> None:
    key = _key()
    await cache.store(key, SampleArtifact(value="good"))
    await fs.write_text(cache._artifact_path(key), '{"count": "not-an-int"}')

    assert await cache.load(key, SampleArtifact) is None


async def test_missing_commit_marker_is_a_miss(cache: FSCache, fs: FakeFileSystem) -> None:
    """An artifact without its meta.json was never committed."""
    key = _key()
    await cache.store(key, SampleArtifact(value="half-written"))
    await fs.remove(cache._meta_path(key))

    assert await cache.exists(key) is False
    assert await cache.load(key, SampleArtifact) is None


async def test_corrupted_meta_is_a_miss(fs: FakeFileSystem) -> None:
    cache = FSCache(fs, absolute_path("/cache"), ttl_seconds=60.0)
    key = _key()
    await cache.store(key, SampleArtifact(value="good"))
    await fs.write_text(cache._meta_path(key), "not json at all")

    assert await cache.exists(key) is False
    assert await cache.load(key, SampleArtifact) is None


async def test_invalidate_removes_entry(cache: FSCache) -> None:
    key = _key()
    await cache.store(key, SampleArtifact(value="doomed"))

    await cache.invalidate(key)

    assert await cache.exists(key) is False
