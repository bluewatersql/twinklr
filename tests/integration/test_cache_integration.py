"""Integration tests for cache system with real filesystem.

Tests complete cache workflow using RealFileSystem and temporary directories.
"""

import hashlib
from pathlib import Path

from pydantic import BaseModel
import pytest

from twinklr.core.caching import FSCache, cached_step
from twinklr.core.io import RealFileSystem, absolute_path


class SampleArtifact(BaseModel):
    """Sample artifact for integration testing."""

    value: str
    checksum: str
    schema_version: int = 1


@pytest.fixture
async def cache(tmp_path: Path):
    """Provide FSCache with RealFileSystem and temp directory."""
    fs = RealFileSystem()
    cache_root = absolute_path(str(tmp_path / ".cache"))
    c = FSCache(fs, cache_root)
    await c.initialize()
    return c


class TestRealFilesystemCaching:
    """Integration tests with real filesystem."""

    async def test_cache_survives_across_calls(self, cache: FSCache, tmp_path: Path):
        """Test that cache persists between function calls."""
        compute_count = 0

        async def compute() -> SampleArtifact:
            nonlocal compute_count
            compute_count += 1
            return SampleArtifact(
                value="computed",
                checksum=hashlib.sha256(b"test").hexdigest(),
            )

        # First call: cache miss
        result1 = await cached_step(
            cache=cache,
            step_id="integration.test",
            step_version="1",
            inputs={"param": "value"},
            model_cls=SampleArtifact,
            compute=compute,
        )

        assert result1.value == "computed"
        assert compute_count == 1

        # Verify cache directory was created
        cache_dir = tmp_path / ".cache"
        assert cache_dir.exists()

        # Second call: cache hit (reuse same cache instance)
        result2 = await cached_step(
            cache=cache,
            step_id="integration.test",
            step_version="1",
            inputs={"param": "value"},
            model_cls=SampleArtifact,
            compute=compute,
        )

        assert result2.value == "computed"
        assert compute_count == 1  # Still 1, not recomputed

    async def test_cache_works_with_new_cache_instance(self, tmp_path: Path):
        """Test cache persists even with new cache instance."""
        fs = RealFileSystem()
        cache_root = absolute_path(str(tmp_path / ".cache"))

        # First cache instance
        cache1 = FSCache(fs, cache_root)
        await cache1.initialize()

        compute_count = 0

        async def compute() -> SampleArtifact:
            nonlocal compute_count
            compute_count += 1
            return SampleArtifact(value="v1", checksum="abc")

        # Store with first instance
        _result1 = await cached_step(
            cache=cache1,
            step_id="persistence.test",
            step_version="1",
            inputs={"x": 1},
            model_cls=SampleArtifact,
            compute=compute,
        )

        assert compute_count == 1

        # Create NEW cache instance pointing to same root
        cache2 = FSCache(fs, cache_root)
        await cache2.initialize()

        # Should hit cache even with new instance
        result2 = await cached_step(
            cache=cache2,
            step_id="persistence.test",
            step_version="1",
            inputs={"x": 1},
            model_cls=SampleArtifact,
            compute=compute,
        )

        assert result2.value == "v1"
        assert compute_count == 1  # Still 1, loaded from disk

    async def test_cache_invalidation_removes_files(self, cache: FSCache, tmp_path: Path):
        """Test that invalidation removes cache entry."""
        from twinklr.core.caching import CacheKey
        from twinklr.core.caching.fingerprint import compute_fingerprint

        # Store artifact
        artifact = SampleArtifact(value="test", checksum="xyz")
        fingerprint = compute_fingerprint("invalidation.test", "1", {"p": 1})
        key = CacheKey(
            step_id="invalidation.test",
            step_version="1",
            input_fingerprint=fingerprint,
        )

        await cache.store(key, artifact)

        # Verify entry exists
        assert await cache.exists(key)

        # Invalidate
        await cache.invalidate(key)

        # Verify entry removed
        assert not await cache.exists(key)

    async def test_concurrent_cache_reads(self, cache: FSCache):
        """Test that concurrent cache reads are safe."""
        import asyncio

        # Populate cache
        artifact = SampleArtifact(value="concurrent", checksum="123")
        from twinklr.core.caching import CacheKey
        from twinklr.core.caching.fingerprint import compute_fingerprint

        fingerprint = compute_fingerprint("concurrent.test", "1", {"p": 1})
        key = CacheKey(
            step_id="concurrent.test",
            step_version="1",
            input_fingerprint=fingerprint,
        )
        await cache.store(key, artifact)

        # Concurrent reads
        results = await asyncio.gather(*[cache.load(key, SampleArtifact) for _ in range(10)])

        # All should succeed and return same value
        assert all(r is not None for r in results)
        assert all(r.value == "concurrent" for r in results if r)  # type: ignore[union-attr]
