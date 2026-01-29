"""Tests for FSCache (async).

Tests the filesystem-backed cache implementation.
"""

from pydantic import BaseModel
import pytest

from blinkb0t.core.caching import CacheKey, FSCache
from blinkb0t.core.io import FakeFileSystem, absolute_path


class SampleArtifact(BaseModel):
    """Sample artifact model for testing."""

    value: str
    schema_version: int = 1


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


@pytest.fixture
def test_key():
    """Provide test cache key."""
    return CacheKey(
        step_id="test.step",
        step_version="1",
        input_fingerprint="abc123" * 10 + "abcd",  # 64 chars
    )


class TestInitialization:
    """Tests for cache initialization."""

    async def test_initialize_creates_root(self, fs: FakeFileSystem):
        """Test initialize creates cache root directory."""
        cache = FSCache(fs, absolute_path("/.cache"))
        await cache.initialize()

        assert await fs.is_dir(absolute_path("/.cache"))


class TestExists:
    """Tests for cache entry existence checks."""

    async def test_exists_returns_false_for_missing_entry(self, cache: FSCache, test_key: CacheKey):
        """Test exists returns False when entry doesn't exist."""
        assert not await cache.exists(test_key)

    async def test_exists_returns_true_for_complete_entry(self, cache: FSCache, test_key: CacheKey):
        """Test exists returns True when both artifact and meta exist."""
        artifact = SampleArtifact(value="test")
        await cache.store(test_key, artifact)

        assert await cache.exists(test_key)

    async def test_exists_returns_false_for_artifact_without_meta(
        self, cache: FSCache, test_key: CacheKey, fs: FakeFileSystem
    ):
        """Test exists returns False when artifact exists but meta missing."""
        # Write artifact manually without meta
        artifact_path = cache._artifact_path(test_key)
        await fs.mkdirs(cache._entry_dir(test_key))
        await fs.write_text(artifact_path, '{"value": "test", "schema_version": 1}')

        assert not await cache.exists(test_key)


class TestLoad:
    """Tests for loading cached artifacts."""

    async def test_load_returns_none_for_missing_entry(self, cache: FSCache, test_key: CacheKey):
        """Test load returns None when entry doesn't exist."""
        result = await cache.load(test_key, SampleArtifact)
        assert result is None

    async def test_load_returns_artifact_on_hit(self, cache: FSCache, test_key: CacheKey):
        """Test load returns cached artifact on cache hit."""
        artifact = SampleArtifact(value="cached")
        await cache.store(test_key, artifact)

        loaded = await cache.load(test_key, SampleArtifact)
        assert loaded is not None
        assert loaded.value == "cached"
        assert loaded.schema_version == 1

    async def test_load_validates_artifact_schema(
        self, cache: FSCache, test_key: CacheKey, fs: FakeFileSystem
    ):
        """Test load returns None when artifact fails validation."""
        # Store valid entry first
        artifact = SampleArtifact(value="test")
        await cache.store(test_key, artifact)

        # Corrupt artifact (invalid JSON)
        artifact_path = cache._artifact_path(test_key)
        await fs.write_text(artifact_path, "invalid json")

        loaded = await cache.load(test_key, SampleArtifact)
        assert loaded is None

    async def test_load_returns_none_for_meta_mismatch(self, cache: FSCache, fs: FakeFileSystem):
        """Test load returns None when meta doesn't match key."""
        # Store with one key
        key1 = CacheKey(
            step_id="test.step",
            step_version="1",
            input_fingerprint="a" * 64,
        )
        await cache.store(key1, SampleArtifact(value="test"))

        # Try to load with different key
        key2 = CacheKey(
            step_id="test.step",
            step_version="2",  # Different version
            input_fingerprint="a" * 64,
        )

        # Manually copy files to wrong location
        # (This simulates a meta mismatch scenario)
        entry_dir1 = cache._entry_dir(key1)
        entry_dir2 = cache._entry_dir(key2)
        await fs.mkdirs(entry_dir2)

        artifact_content = await fs.read_text(fs.join(entry_dir1, "artifact.json"))
        meta_content = await fs.read_text(fs.join(entry_dir1, "meta.json"))

        await fs.write_text(fs.join(entry_dir2, "artifact.json"), artifact_content)
        await fs.write_text(fs.join(entry_dir2, "meta.json"), meta_content)

        # Should return None due to meta mismatch
        loaded = await cache.load(key2, SampleArtifact)
        assert loaded is None


class TestStore:
    """Tests for storing cache artifacts."""

    async def test_store_creates_entry_directory(
        self, cache: FSCache, test_key: CacheKey, fs: FakeFileSystem
    ):
        """Test store creates entry directory."""
        artifact = SampleArtifact(value="test")
        await cache.store(test_key, artifact)

        entry_dir = cache._entry_dir(test_key)
        assert await fs.is_dir(entry_dir)

    async def test_store_writes_artifact_and_meta(
        self, cache: FSCache, test_key: CacheKey, fs: FakeFileSystem
    ):
        """Test store writes both artifact.json and meta.json."""
        artifact = SampleArtifact(value="test")
        await cache.store(test_key, artifact, compute_ms=100.5)

        artifact_path = cache._artifact_path(test_key)
        meta_path = cache._meta_path(test_key)

        assert await fs.is_file(artifact_path)
        assert await fs.is_file(meta_path)

        # Verify artifact content
        artifact_json = await fs.read_text(artifact_path)
        assert "test" in artifact_json

        # Verify meta content
        meta_json = await fs.read_text(meta_path)
        assert "test.step" in meta_json
        assert "100.5" in meta_json

    async def test_store_overwrites_existing_entry(self, cache: FSCache, test_key: CacheKey):
        """Test store overwrites existing cache entries."""
        await cache.store(test_key, SampleArtifact(value="first"))
        await cache.store(test_key, SampleArtifact(value="second"))

        loaded = await cache.load(test_key, SampleArtifact)
        assert loaded is not None
        assert loaded.value == "second"


class TestInvalidate:
    """Tests for cache invalidation."""

    async def test_invalidate_removes_entry(self, cache: FSCache, test_key: CacheKey):
        """Test invalidate removes cache entry."""
        artifact = SampleArtifact(value="test")
        await cache.store(test_key, artifact)

        assert await cache.exists(test_key)

        await cache.invalidate(test_key)

        assert not await cache.exists(test_key)

    async def test_invalidate_nonexistent_does_not_raise(self, cache: FSCache, test_key: CacheKey):
        """Test invalidate on nonexistent entry doesn't raise."""
        await cache.invalidate(test_key)  # Should not raise


class TestRoundtrip:
    """Integration tests for complete cache workflows."""

    async def test_store_load_roundtrip(self, cache: FSCache, test_key: CacheKey):
        """Test complete store → load roundtrip."""
        original = SampleArtifact(value="roundtrip test", schema_version=2)
        await cache.store(test_key, original, compute_ms=42.0)

        loaded = await cache.load(test_key, SampleArtifact)
        assert loaded is not None
        assert loaded.value == original.value
        assert loaded.schema_version == original.schema_version

    async def test_multiple_entries_isolated(self, cache: FSCache):
        """Test multiple cache entries are isolated from each other."""
        key1 = CacheKey(
            step_id="step.one",
            step_version="1",
            input_fingerprint="a" * 64,
        )
        key2 = CacheKey(
            step_id="step.two",
            step_version="1",
            input_fingerprint="b" * 64,
        )

        await cache.store(key1, SampleArtifact(value="first"))
        await cache.store(key2, SampleArtifact(value="second"))

        loaded1 = await cache.load(key1, SampleArtifact)
        loaded2 = await cache.load(key2, SampleArtifact)

        assert loaded1 is not None
        assert loaded2 is not None
        assert loaded1.value == "first"
        assert loaded2.value == "second"
