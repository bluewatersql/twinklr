"""Tests for FakeFileSystem (async).

Tests the in-memory fake filesystem implementation.
"""

import pytest

from twinklr.core.io import AbsolutePath, FakeFileSystem, absolute_path


@pytest.fixture
def fs():
    """Provide fresh FakeFileSystem instance."""
    return FakeFileSystem()


@pytest.fixture
def test_root():
    """Provide test root path."""
    return absolute_path("/test")


class TestJoin:
    """Tests for path joining (sync operation)."""

    def test_join_single_part(self, fs: FakeFileSystem, test_root: AbsolutePath):
        """Test joining single path component."""
        result = fs.join(test_root, "subdir")
        assert str(result) == "/test/subdir"

    def test_join_multiple_parts(self, fs: FakeFileSystem, test_root: AbsolutePath):
        """Test joining multiple path components."""
        result = fs.join(test_root, "a", "b", "c")
        assert str(result) == "/test/a/b/c"


class TestExistence:
    """Tests for existence checks."""

    async def test_exists_returns_false_for_nonexistent(
        self, fs: FakeFileSystem, test_root: AbsolutePath
    ):
        """Test that nonexistent paths return False."""
        assert not await fs.exists(test_root)

    async def test_exists_returns_true_for_file(self, fs: FakeFileSystem, test_root: AbsolutePath):
        """Test that existing file returns True."""
        test_file = fs.join(test_root, "test.txt")
        await fs.write_text(test_file, "content")
        assert await fs.exists(test_file)

    async def test_exists_returns_true_for_directory(
        self, fs: FakeFileSystem, test_root: AbsolutePath
    ):
        """Test that existing directory returns True."""
        await fs.mkdirs(test_root)
        assert await fs.exists(test_root)

    async def test_is_file_returns_true_for_file(self, fs: FakeFileSystem, test_root: AbsolutePath):
        """Test is_file returns True for files."""
        test_file = fs.join(test_root, "test.txt")
        await fs.write_text(test_file, "content")
        assert await fs.is_file(test_file)

    async def test_is_file_returns_false_for_directory(
        self, fs: FakeFileSystem, test_root: AbsolutePath
    ):
        """Test is_file returns False for directories."""
        await fs.mkdirs(test_root)
        assert not await fs.is_file(test_root)

    async def test_is_dir_returns_true_for_directory(
        self, fs: FakeFileSystem, test_root: AbsolutePath
    ):
        """Test is_dir returns True for directories."""
        await fs.mkdirs(test_root)
        assert await fs.is_dir(test_root)

    async def test_is_dir_returns_false_for_file(self, fs: FakeFileSystem, test_root: AbsolutePath):
        """Test is_dir returns False for files."""
        test_file = fs.join(test_root, "test.txt")
        await fs.write_text(test_file, "content")
        assert not await fs.is_dir(test_file)


class TestReadWrite:
    """Tests for read/write operations."""

    async def test_write_and_read_roundtrip(self, fs: FakeFileSystem, test_root: AbsolutePath):
        """Test write → read roundtrip succeeds."""
        test_file = fs.join(test_root, "test.txt")
        content = "Hello, world!"

        # Write
        result = await fs.write_text(test_file, content)
        assert result.bytes_written == len(content.encode("utf-8"))
        assert result.path == str(test_file)

        # Read back
        read_content = await fs.read_text(test_file)
        assert read_content == content

    async def test_write_creates_parent_directories(
        self, fs: FakeFileSystem, test_root: AbsolutePath
    ):
        """Test that write auto-creates parent directories."""
        test_file = fs.join(test_root, "a", "b", "c", "test.txt")
        await fs.write_text(test_file, "content")

        # Parents should exist
        assert await fs.is_dir(fs.join(test_root, "a"))
        assert await fs.is_dir(fs.join(test_root, "a", "b"))
        assert await fs.is_dir(fs.join(test_root, "a", "b", "c"))

    async def test_read_nonexistent_raises_error(self, fs: FakeFileSystem, test_root: AbsolutePath):
        """Test reading nonexistent file raises FileNotFoundError."""
        test_file = fs.join(test_root, "nonexistent.txt")
        with pytest.raises(FileNotFoundError):
            await fs.read_text(test_file)

    async def test_write_overwrites_existing_file(
        self, fs: FakeFileSystem, test_root: AbsolutePath
    ):
        """Test that write overwrites existing files."""
        test_file = fs.join(test_root, "test.txt")

        await fs.write_text(test_file, "first")
        await fs.write_text(test_file, "second")

        content = await fs.read_text(test_file)
        assert content == "second"


class TestDirectories:
    """Tests for directory operations."""

    async def test_mkdirs_creates_directory(self, fs: FakeFileSystem, test_root: AbsolutePath):
        """Test mkdirs creates directory."""
        await fs.mkdirs(test_root)
        assert await fs.is_dir(test_root)

    async def test_mkdirs_creates_parents(self, fs: FakeFileSystem, test_root: AbsolutePath):
        """Test mkdirs creates parent directories."""
        nested = fs.join(test_root, "a", "b", "c")
        await fs.mkdirs(nested)

        assert await fs.is_dir(test_root)
        assert await fs.is_dir(fs.join(test_root, "a"))
        assert await fs.is_dir(fs.join(test_root, "a", "b"))
        assert await fs.is_dir(nested)

    async def test_mkdirs_exist_ok_true_does_not_raise(
        self, fs: FakeFileSystem, test_root: AbsolutePath
    ):
        """Test mkdirs with exist_ok=True doesn't raise on existing directory."""
        await fs.mkdirs(test_root, exist_ok=True)
        await fs.mkdirs(test_root, exist_ok=True)  # Should not raise

    async def test_mkdirs_exist_ok_false_raises(self, fs: FakeFileSystem, test_root: AbsolutePath):
        """Test mkdirs with exist_ok=False raises on existing directory."""
        await fs.mkdirs(test_root, exist_ok=True)
        with pytest.raises(FileExistsError):
            await fs.mkdirs(test_root, exist_ok=False)

    async def test_listdir_returns_children(self, fs: FakeFileSystem, test_root: AbsolutePath):
        """Test listdir returns immediate children."""
        await fs.mkdirs(test_root)
        await fs.write_text(fs.join(test_root, "file1.txt"), "content1")
        await fs.write_text(fs.join(test_root, "file2.txt"), "content2")
        await fs.mkdirs(fs.join(test_root, "subdir"))

        children = await fs.listdir(test_root)
        assert sorted(children) == ["file1.txt", "file2.txt", "subdir"]

    async def test_listdir_nonexistent_raises_error(
        self, fs: FakeFileSystem, test_root: AbsolutePath
    ):
        """Test listdir on nonexistent directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await fs.listdir(test_root)


class TestRemoval:
    """Tests for file/directory removal."""

    async def test_remove_deletes_file(self, fs: FakeFileSystem, test_root: AbsolutePath):
        """Test remove deletes files."""
        test_file = fs.join(test_root, "test.txt")
        await fs.write_text(test_file, "content")

        await fs.remove(test_file)
        assert not await fs.exists(test_file)

    async def test_remove_nonexistent_raises_error(
        self, fs: FakeFileSystem, test_root: AbsolutePath
    ):
        """Test remove on nonexistent file raises FileNotFoundError."""
        test_file = fs.join(test_root, "nonexistent.txt")
        with pytest.raises(FileNotFoundError):
            await fs.remove(test_file)

    async def test_rmdir_deletes_empty_directory(self, fs: FakeFileSystem, test_root: AbsolutePath):
        """Test rmdir deletes empty directories."""
        await fs.mkdirs(test_root)
        await fs.rmdir(test_root, recursive=False)
        assert not await fs.exists(test_root)

    async def test_rmdir_recursive_deletes_contents(
        self, fs: FakeFileSystem, test_root: AbsolutePath
    ):
        """Test rmdir with recursive=True deletes contents."""
        await fs.mkdirs(fs.join(test_root, "a", "b"))
        await fs.write_text(fs.join(test_root, "file.txt"), "content")
        await fs.write_text(fs.join(test_root, "a", "file2.txt"), "content2")

        await fs.rmdir(test_root, recursive=True)
        assert not await fs.exists(test_root)

    async def test_rmdir_nonexistent_raises_error(
        self, fs: FakeFileSystem, test_root: AbsolutePath
    ):
        """Test rmdir on nonexistent directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await fs.rmdir(test_root)
