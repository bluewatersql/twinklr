"""Filesystem abstraction layer for Twinklr.

Provides safe, testable, async-first filesystem operations with sync convenience wrappers.

Example (async):
    >>> from twinklr.core.io import RealFileSystem, absolute_path
    >>> fs = RealFileSystem()
    >>> path = fs.join(absolute_path("/tmp"), "cache", "test.txt")
    >>> await fs.write_text(path, "Hello, world!")
    >>> content = await fs.read_text(path)

Example (sync):
    >>> from twinklr.core.io import RealFileSystemSync, absolute_path
    >>> fs = RealFileSystemSync()
    >>> path = fs.join(absolute_path("/tmp"), "cache", "test.txt")
    >>> fs.write_text(path, "Hello, world!")
    >>> content = fs.read_text(path)
"""

from .impl_fake import FakeFileSystem, FakeFileSystemSync
from .impl_null import NullFileSystem, NullFileSystemSync
from .impl_real import RealFileSystem, RealFileSystemSync
from .models import AbsolutePath, RelativePath, WriteResult, absolute_path, relative_path
from .protocols import FileSystem, FileSystemSync
from .utils import sanitize_path_component

__all__ = [
    # Path types and constructors
    "AbsolutePath",
    "RelativePath",
    "absolute_path",
    "relative_path",
    # Result types
    "WriteResult",
    # Protocols
    "FileSystem",
    "FileSystemSync",
    # Async implementations
    "RealFileSystem",
    "FakeFileSystem",
    "NullFileSystem",
    # Sync wrappers
    "RealFileSystemSync",
    "FakeFileSystemSync",
    "NullFileSystemSync",
    # Utilities
    "sanitize_path_component",
]
