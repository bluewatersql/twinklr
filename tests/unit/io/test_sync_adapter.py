"""Tests for SyncAdapter and backward-compat sync wrappers.

Verifies:
- SyncAdapter wraps async methods and returns correct results
- SyncAdapter passes non-async attributes through
- NullFileSystemSync backward compat (same API, same behavior)
- RealFileSystemSync backward compat (same API, same behavior)
- FSCacheSync backward compat (same API, same behavior)
- Protocol conformance preserved
"""

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel
import pytest

from twinklr.core.caching.backends.fs import FSCacheSync
from twinklr.core.caching.models import CacheKey
from twinklr.core.io import AbsolutePath, absolute_path
from twinklr.core.io.impl_null import NullFileSystemSync
from twinklr.core.io.impl_real import RealFileSystem, RealFileSystemSync
from twinklr.core.io.sync_adapter import SyncAdapter

if TYPE_CHECKING:
    from twinklr.core.io import FileSystemSync

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _SimpleAsyncObj:
    """Minimal async class for unit-testing SyncAdapter in isolation."""

    sync_attr = "hello"
    sync_number = 42

    async def async_return_value(self) -> str:
        """Returns a fixed string asynchronously."""
        return "async_result"

    async def async_with_args(self, a: int, b: int) -> int:
        """Returns sum asynchronously."""
        return a + b

    async def async_raises(self) -> None:
        """Raises RuntimeError asynchronously."""
        raise RuntimeError("async error")

    def sync_method(self) -> str:
        """Plain synchronous method."""
        return "sync_result"


class _SampleArtifact(BaseModel):
    """Minimal Pydantic model for FSCacheSync tests."""

    value: str


# ---------------------------------------------------------------------------
# SyncAdapter unit tests
# ---------------------------------------------------------------------------


class TestSyncAdapterWrapsAsync:
    """SyncAdapter wraps async methods and returns correct results."""

    def test_wraps_coroutine_method_no_args(self) -> None:
        """SyncAdapter.async_return_value() returns unwrapped value synchronously."""
        adapter = SyncAdapter(_SimpleAsyncObj())
        result = adapter.async_return_value()
        assert result == "async_result"

    def test_wraps_coroutine_method_with_args(self) -> None:
        """SyncAdapter forwards positional and keyword args to the wrapped coroutine."""
        adapter = SyncAdapter(_SimpleAsyncObj())
        assert adapter.async_with_args(3, 4) == 7
        assert adapter.async_with_args(a=10, b=20) == 30

    def test_async_exception_propagates(self) -> None:
        """Exceptions raised inside async methods propagate through SyncAdapter."""
        adapter = SyncAdapter(_SimpleAsyncObj())
        with pytest.raises(RuntimeError, match="async error"):
            adapter.async_raises()


class TestSyncAdapterPassthroughNonAsync:
    """SyncAdapter passes non-async attributes through unchanged."""

    def test_sync_string_attribute(self) -> None:
        """Plain string attribute is returned as-is."""
        adapter = SyncAdapter(_SimpleAsyncObj())
        assert adapter.sync_attr == "hello"

    def test_sync_int_attribute(self) -> None:
        """Plain integer attribute is returned as-is."""
        adapter = SyncAdapter(_SimpleAsyncObj())
        assert adapter.sync_number == 42

    def test_sync_method_callable(self) -> None:
        """Non-async method is returned callable and works correctly."""
        adapter = SyncAdapter(_SimpleAsyncObj())
        assert adapter.sync_method() == "sync_result"

    def test_missing_attribute_raises_attribute_error(self) -> None:
        """AttributeError is raised for attributes that do not exist."""
        adapter = SyncAdapter(_SimpleAsyncObj())
        with pytest.raises(AttributeError):
            _ = adapter.nonexistent_attribute


# ---------------------------------------------------------------------------
# NullFileSystemSync backward compat
# ---------------------------------------------------------------------------


class TestNullFileSystemSyncBackwardCompat:
    """NullFileSystemSync: same API, same behavior as before."""

    @pytest.fixture()
    def fs(self) -> NullFileSystemSync:
        """Fresh NullFileSystemSync instance."""
        return NullFileSystemSync()

    @pytest.fixture()
    def root(self) -> AbsolutePath:
        """Stable test root path."""
        return absolute_path("/tmp/null_test")

    def test_is_subclass_of_sync_adapter(self, fs: NullFileSystemSync) -> None:
        """NullFileSystemSync is a thin SyncAdapter subclass."""
        assert isinstance(fs, SyncAdapter)

    def test_exists_always_false(self, fs: NullFileSystemSync, root: AbsolutePath) -> None:
        """exists() always returns False for NullFileSystem."""
        assert fs.exists(root) is False

    def test_is_file_always_false(self, fs: NullFileSystemSync, root: AbsolutePath) -> None:
        """is_file() always returns False."""
        assert fs.is_file(root) is False

    def test_is_dir_always_false(self, fs: NullFileSystemSync, root: AbsolutePath) -> None:
        """is_dir() always returns False."""
        assert fs.is_dir(root) is False

    def test_read_text_raises_file_not_found(
        self, fs: NullFileSystemSync, root: AbsolutePath
    ) -> None:
        """read_text() always raises FileNotFoundError."""
        path = fs.join(root, "file.txt")
        with pytest.raises(FileNotFoundError):
            fs.read_text(path)

    def test_write_text_returns_write_result(
        self, fs: NullFileSystemSync, root: AbsolutePath
    ) -> None:
        """write_text() returns WriteResult with correct bytes_written."""
        path = fs.join(root, "file.txt")
        content = "hello world"
        result = fs.write_text(path, content)
        assert result.bytes_written == len(content.encode("utf-8"))

    def test_mkdirs_is_noop(self, fs: NullFileSystemSync, root: AbsolutePath) -> None:
        """mkdirs() completes without error."""
        fs.mkdirs(root)  # Should not raise

    def test_listdir_returns_empty_list(self, fs: NullFileSystemSync, root: AbsolutePath) -> None:
        """listdir() always returns []."""
        assert fs.listdir(root) == []

    def test_remove_is_noop(self, fs: NullFileSystemSync, root: AbsolutePath) -> None:
        """remove() completes without error."""
        fs.remove(fs.join(root, "file.txt"))  # Should not raise

    def test_rmdir_is_noop(self, fs: NullFileSystemSync, root: AbsolutePath) -> None:
        """rmdir() completes without error."""
        fs.rmdir(root)  # Should not raise

    def test_join_returns_correct_path(self, fs: NullFileSystemSync, root: AbsolutePath) -> None:
        """join() produces correct absolute path."""
        result = fs.join(root, "a", "b")
        assert str(result).endswith("/a/b")


# ---------------------------------------------------------------------------
# RealFileSystemSync backward compat
# ---------------------------------------------------------------------------


class TestRealFileSystemSyncBackwardCompat:
    """RealFileSystemSync: same API, same behavior as before."""

    @pytest.fixture()
    def fs(self) -> RealFileSystemSync:
        """Fresh RealFileSystemSync instance."""
        return RealFileSystemSync()

    @pytest.fixture()
    def tmp_root(self, tmp_path: Path) -> AbsolutePath:
        """Temporary directory as AbsolutePath."""
        return AbsolutePath(tmp_path)

    def test_is_subclass_of_sync_adapter(self, fs: RealFileSystemSync) -> None:
        """RealFileSystemSync is a thin SyncAdapter subclass."""
        assert isinstance(fs, SyncAdapter)

    def test_mkdirs_creates_directory(self, fs: RealFileSystemSync, tmp_root: AbsolutePath) -> None:
        """mkdirs() creates directories on the real filesystem."""
        target = fs.join(tmp_root, "a", "b", "c")
        fs.mkdirs(target)
        assert Path(target).is_dir()

    def test_write_and_read_roundtrip(self, fs: RealFileSystemSync, tmp_root: AbsolutePath) -> None:
        """write_text() followed by read_text() round-trips content correctly."""
        file_path = fs.join(tmp_root, "hello.txt")
        content = "Hello, SyncAdapter!"
        result = fs.write_text(file_path, content)
        assert result.bytes_written == len(content.encode("utf-8"))
        assert fs.read_text(file_path) == content

    def test_exists_true_for_written_file(
        self, fs: RealFileSystemSync, tmp_root: AbsolutePath
    ) -> None:
        """exists() returns True after writing a file."""
        file_path = fs.join(tmp_root, "exists_test.txt")
        fs.write_text(file_path, "data")
        assert fs.exists(file_path) is True

    def test_exists_false_for_nonexistent(
        self, fs: RealFileSystemSync, tmp_root: AbsolutePath
    ) -> None:
        """exists() returns False for a path that was never written."""
        assert fs.exists(fs.join(tmp_root, "ghost.txt")) is False

    def test_is_file_true_for_file(self, fs: RealFileSystemSync, tmp_root: AbsolutePath) -> None:
        """is_file() returns True for a written file."""
        file_path = fs.join(tmp_root, "isfile.txt")
        fs.write_text(file_path, "data")
        assert fs.is_file(file_path) is True

    def test_is_dir_true_for_created_dir(
        self, fs: RealFileSystemSync, tmp_root: AbsolutePath
    ) -> None:
        """is_dir() returns True for a created directory."""
        fs.mkdirs(tmp_root)
        assert fs.is_dir(tmp_root) is True

    def test_listdir_returns_written_files(
        self, fs: RealFileSystemSync, tmp_root: AbsolutePath
    ) -> None:
        """listdir() returns names of files written into a directory."""
        fs.write_text(fs.join(tmp_root, "file_a.txt"), "a")
        fs.write_text(fs.join(tmp_root, "file_b.txt"), "b")
        entries = fs.listdir(tmp_root)
        assert "file_a.txt" in entries
        assert "file_b.txt" in entries

    def test_remove_deletes_file(self, fs: RealFileSystemSync, tmp_root: AbsolutePath) -> None:
        """remove() deletes an existing file."""
        file_path = fs.join(tmp_root, "to_delete.txt")
        fs.write_text(file_path, "bye")
        fs.remove(file_path)
        assert not Path(file_path).exists()

    def test_join_returns_correct_path(
        self, fs: RealFileSystemSync, tmp_root: AbsolutePath
    ) -> None:
        """join() produces correct absolute path."""
        result = fs.join(tmp_root, "x", "y")
        assert str(result).endswith("/x/y")


# ---------------------------------------------------------------------------
# FSCacheSync backward compat
# ---------------------------------------------------------------------------


class TestFSCacheSyncBackwardCompat:
    """FSCacheSync: same API, same behavior as before."""

    @pytest.fixture()
    def cache_key(self) -> CacheKey:
        """Stable cache key for tests."""
        return CacheKey(
            domain="test_domain",
            session_id="sess_001",
            step_id="step.alpha",
            step_version="v1",
            input_fingerprint="abc123",
        )

    @pytest.fixture()
    def real_cache(self, tmp_path: Path) -> FSCacheSync:
        """FSCacheSync backed by RealFileSystem for integration-style assertions."""

        fs = RealFileSystem()
        root = AbsolutePath(tmp_path)
        return FSCacheSync(fs, root)

    def test_is_subclass_of_sync_adapter(self, real_cache: FSCacheSync) -> None:
        """FSCacheSync is a thin SyncAdapter subclass."""
        assert isinstance(real_cache, SyncAdapter)

    def test_exists_returns_false_on_empty_cache(
        self, real_cache: FSCacheSync, cache_key: CacheKey
    ) -> None:
        """exists() returns False when no entry has been stored."""
        assert real_cache.exists(cache_key) is False

    def test_store_and_exists(self, real_cache: FSCacheSync, cache_key: CacheKey) -> None:
        """store() makes exists() return True."""
        artifact = _SampleArtifact(value="stored_value")
        real_cache.store(cache_key, artifact)
        assert real_cache.exists(cache_key) is True

    def test_store_and_load_roundtrip(self, real_cache: FSCacheSync, cache_key: CacheKey) -> None:
        """store() followed by load() returns an equal artifact."""
        artifact = _SampleArtifact(value="round_trip")
        real_cache.store(cache_key, artifact)
        loaded = real_cache.load(cache_key, _SampleArtifact)
        assert loaded is not None
        assert loaded.value == "round_trip"

    def test_load_returns_none_on_miss(self, real_cache: FSCacheSync, cache_key: CacheKey) -> None:
        """load() returns None when entry does not exist."""
        result = real_cache.load(cache_key, _SampleArtifact)
        assert result is None

    def test_invalidate_removes_entry(self, real_cache: FSCacheSync, cache_key: CacheKey) -> None:
        """invalidate() causes exists() to return False."""
        artifact = _SampleArtifact(value="to_be_removed")
        real_cache.store(cache_key, artifact)
        real_cache.invalidate(cache_key)
        assert real_cache.exists(cache_key) is False

    def test_initialize_is_idempotent(self, real_cache: FSCacheSync) -> None:
        """initialize() can be called multiple times without error."""
        real_cache.initialize()
        real_cache.initialize()


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """Verify sync wrappers still satisfy the FileSystemSync protocol."""

    def test_null_filesystem_sync_conforms_to_protocol(self) -> None:
        """NullFileSystemSync satisfies FileSystemSync protocol."""
        fs: FileSystemSync = NullFileSystemSync()
        # Protocol attrs must be callable
        assert callable(fs.join)
        assert callable(fs.exists)
        assert callable(fs.is_file)
        assert callable(fs.is_dir)
        assert callable(fs.read_text)
        assert callable(fs.write_text)
        assert callable(fs.mkdirs)
        assert callable(fs.listdir)
        assert callable(fs.remove)
        assert callable(fs.rmdir)

    def test_real_filesystem_sync_conforms_to_protocol(self) -> None:
        """RealFileSystemSync satisfies FileSystemSync protocol."""
        fs: FileSystemSync = RealFileSystemSync()
        assert callable(fs.join)
        assert callable(fs.exists)
        assert callable(fs.write_text)
        assert callable(fs.read_text)
