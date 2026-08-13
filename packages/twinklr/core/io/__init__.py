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

from twinklr.core.io.impl_fake import FakeFileSystem, FakeFileSystemSync
from twinklr.core.io.impl_null import NullFileSystem, NullFileSystemSync
from twinklr.core.io.impl_real import RealFileSystem, RealFileSystemSync
from twinklr.core.io.models import (
    AbsolutePath,
    RelativePath,
    WriteResult,
    absolute_path,
    anchored_path,
    relative_path,
)
from twinklr.core.io.protocols import FileSystem, FileSystemSync
from twinklr.core.io.utils import sanitize_path_component

__all__ = [
    # Path types and constructors
    "AbsolutePath",
    "FakeFileSystem",
    "FakeFileSystemSync",
    # Protocols
    "FileSystem",
    "FileSystemSync",
    "NullFileSystem",
    "NullFileSystemSync",
    # Async implementations
    "RealFileSystem",
    # Sync wrappers
    "RealFileSystemSync",
    "RelativePath",
    # Result types
    "WriteResult",
    "absolute_path",
    "anchored_path",
    "relative_path",
    # Utilities
    "sanitize_path_component",
]
