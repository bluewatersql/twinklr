"""Tests for cached_step wrapper (async).

Tests the main cached_step() function that orchestrates cache operations.
"""

from pydantic import BaseModel
import pytest

from twinklr.core.caching import CacheOptions, FSCache, cached_step
from twinklr.core.io import FakeFileSystem, absolute_path


class SampleArtifact(BaseModel):
    """Sample artifact model for testing."""

    value: str
    compute_count: int = 0


@pytest.fixture
def fs():
    """Provide fresh FakeFileSystem instance."""
    return FakeFileSystem()


@pytest.fixture
async def cache(fs: FakeFileSystem):
    """Provide initialized FSCache instance."""
    c = FSCache(fs, absolute_path("/.cache"))
    await c.initialize()
    return c


class TestCacheHit:
    """Tests for cache hit behavior."""

    async def test_cache_hit_returns_cached_artifact(self, cache: FSCache):
        """Test cache hit returns cached artifact without recomputing."""
        compute_count = 0

        async def compute() -> SampleArtifact:
            nonlocal compute_count
            compute_count += 1
            return SampleArtifact(value="computed", compute_count=compute_count)

        # First call: cache miss, computes
        result1 = await cached_step(
            cache=cache,
            step_id="test.step",
            step_version="1",
            inputs={"param": "value"},
            model_cls=SampleArtifact,
            compute=compute,
        )

        assert result1.value == "computed"
        assert result1.compute_count == 1
        assert compute_count == 1

        # Second call: cache hit, does not recompute
        result2 = await cached_step(
            cache=cache,
            step_id="test.step",
            step_version="1",
            inputs={"param": "value"},
            model_cls=SampleArtifact,
            compute=compute,
        )

        assert result2.value == "computed"
        assert result2.compute_count == 1  # Same as first
        assert compute_count == 1  # Still 1, not recomputed

    async def test_different_inputs_cause_cache_miss(self, cache: FSCache):
        """Test different inputs produce different cache entries."""

        async def compute() -> SampleArtifact:
            return SampleArtifact(value="computed")

        # Call with input1
        _result1 = await cached_step(
            cache=cache,
            step_id="test.step",
            step_version="1",
            inputs={"param": "value1"},
            model_cls=SampleArtifact,
            compute=compute,
        )

        # Call with input2 (different) - should be cache miss
        compute_count = 0

        async def compute_counting() -> SampleArtifact:
            nonlocal compute_count
            compute_count += 1
            return SampleArtifact(value="computed2")

        _result2 = await cached_step(
            cache=cache,
            step_id="test.step",
            step_version="1",
            inputs={"param": "value2"},  # Different input
            model_cls=SampleArtifact,
            compute=compute_counting,
        )

        assert compute_count == 1  # Recomputed due to different input


class TestCacheMiss:
    """Tests for cache miss behavior."""

    async def test_cache_miss_computes_and_stores(self, cache: FSCache):
        """Test cache miss triggers computation and stores result."""

        async def compute() -> SampleArtifact:
            return SampleArtifact(value="freshly computed")

        result = await cached_step(
            cache=cache,
            step_id="test.step",
            step_version="1",
            inputs={"param": "value"},
            model_cls=SampleArtifact,
            compute=compute,
        )

        assert result.value == "freshly computed"

        # Verify stored in cache
        from twinklr.core.caching import CacheKey
        from twinklr.core.caching.fingerprint import compute_fingerprint

        fingerprint = compute_fingerprint("test.step", "1", {"param": "value"})
        key = CacheKey(
            step_id="test.step",
            step_version="1",
            input_fingerprint=fingerprint,
        )

        assert await cache.exists(key)


class TestCacheOptions:
    """Tests for cache options."""

    async def test_force_true_bypasses_cache_but_stores(self, cache: FSCache):
        """Test force=True bypasses cache but still stores result."""
        compute_count = 0

        async def compute() -> SampleArtifact:
            nonlocal compute_count
            compute_count += 1
            return SampleArtifact(value="computed", compute_count=compute_count)

        # First call: populate cache
        _result1 = await cached_step(
            cache=cache,
            step_id="test.step",
            step_version="1",
            inputs={"param": "value"},
            model_cls=SampleArtifact,
            compute=compute,
        )
        assert compute_count == 1

        # Second call with force=True: recomputes despite cache hit
        result2 = await cached_step(
            cache=cache,
            step_id="test.step",
            step_version="1",
            inputs={"param": "value"},
            model_cls=SampleArtifact,
            compute=compute,
            options=CacheOptions(force=True),
        )

        assert compute_count == 2  # Recomputed
        assert result2.compute_count == 2

    async def test_enabled_false_skips_all_cache_operations(self, cache: FSCache):
        """Test enabled=False skips cache load and store."""
        compute_count = 0

        async def compute() -> SampleArtifact:
            nonlocal compute_count
            compute_count += 1
            return SampleArtifact(value="computed", compute_count=compute_count)

        # First call with cache disabled
        _result1 = await cached_step(
            cache=cache,
            step_id="test.step",
            step_version="1",
            inputs={"param": "value"},
            model_cls=SampleArtifact,
            compute=compute,
            options=CacheOptions(enabled=False),
        )
        assert compute_count == 1

        # Second call with cache disabled - should recompute
        _result2 = await cached_step(
            cache=cache,
            step_id="test.step",
            step_version="1",
            inputs={"param": "value"},
            model_cls=SampleArtifact,
            compute=compute,
            options=CacheOptions(enabled=False),
        )
        assert compute_count == 2  # Recomputed

        # Third call with cache enabled - should still be cache miss
        _result3 = await cached_step(
            cache=cache,
            step_id="test.step",
            step_version="1",
            inputs={"param": "value"},
            model_cls=SampleArtifact,
            compute=compute,
            options=CacheOptions(enabled=True),
        )
        assert compute_count == 3  # Cache was never populated


class TestVersioning:
    """Tests for step versioning."""

    async def test_different_step_versions_cause_cache_miss(self, cache: FSCache):
        """Test different step versions produce separate cache entries."""

        async def compute_v1() -> SampleArtifact:
            return SampleArtifact(value="v1")

        # Store with version 1
        result1 = await cached_step(
            cache=cache,
            step_id="test.step",
            step_version="1",
            inputs={"param": "value"},
            model_cls=SampleArtifact,
            compute=compute_v1,
        )
        assert result1.value == "v1"

        # Call with version 2 (different) - should be cache miss
        compute_count = 0

        async def compute_counting() -> SampleArtifact:
            nonlocal compute_count
            compute_count += 1
            return SampleArtifact(value="v2")

        result2 = await cached_step(
            cache=cache,
            step_id="test.step",
            step_version="2",  # Different version
            inputs={"param": "value"},
            model_cls=SampleArtifact,
            compute=compute_counting,
        )

        assert compute_count == 1  # Recomputed due to different version
        assert result2.value == "v2"


class TestFingerprintStability:
    """Tests for fingerprint stability."""

    async def test_same_inputs_produce_cache_hit(self, cache: FSCache):
        """Test identical inputs produce stable fingerprints."""
        compute_count = 0

        async def compute() -> SampleArtifact:
            nonlocal compute_count
            compute_count += 1
            return SampleArtifact(value="computed")

        # Call twice with identical inputs
        await cached_step(
            cache=cache,
            step_id="test.step",
            step_version="1",
            inputs={"a": 1, "b": 2, "c": 3},
            model_cls=SampleArtifact,
            compute=compute,
        )

        await cached_step(
            cache=cache,
            step_id="test.step",
            step_version="1",
            inputs={"a": 1, "b": 2, "c": 3},
            model_cls=SampleArtifact,
            compute=compute,
        )

        assert compute_count == 1  # Second call hit cache

    async def test_input_order_does_not_matter(self, cache: FSCache):
        """Test input dict key order doesn't affect fingerprint."""
        compute_count = 0

        async def compute() -> SampleArtifact:
            nonlocal compute_count
            compute_count += 1
            return SampleArtifact(value="computed")

        # Call with keys in one order
        await cached_step(
            cache=cache,
            step_id="test.step",
            step_version="1",
            inputs={"z": 1, "a": 2, "m": 3},
            model_cls=SampleArtifact,
            compute=compute,
        )

        # Call with keys in different order - should hit cache
        await cached_step(
            cache=cache,
            step_id="test.step",
            step_version="1",
            inputs={"a": 2, "m": 3, "z": 1},  # Different order
            model_cls=SampleArtifact,
            compute=compute,
        )

        assert compute_count == 1  # Second call hit cache
