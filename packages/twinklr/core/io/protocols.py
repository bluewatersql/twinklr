"""Protocols for filesystem operations.

Defines async-first FileSystem protocol and sync convenience wrapper protocol.
"""

from typing import Protocol

from .models import AbsolutePath, WriteResult


class FileSystem(Protocol):
    """
    Protocol for async filesystem operations.

    All implementations must provide atomic write semantics and
    handle platform-specific details transparently.

    Async methods are primary; sync wrappers available via FileSystemSync.
    """

    # Path operations (sync - no I/O)
    def join(self, base: AbsolutePath, *parts: str) -> AbsolutePath:
        """
        Safely join path components.

        Args:
            base: Base absolute path
            *parts: Path segments to join

        Returns:
            New absolute path

        Raises:
            ValueError: If result escapes base directory
        """
        ...

    # Existence checks (async)
    async def exists(self, path: AbsolutePath) -> bool:
        """Check if path exists (file or directory)."""
        ...

    async def is_file(self, path: AbsolutePath) -> bool:
        """Check if path exists and is a file."""
        ...

    async def is_dir(self, path: AbsolutePath) -> bool:
        """Check if path exists and is a directory."""
        ...

    # Read operations (async)
    async def read_text(self, path: AbsolutePath, encoding: str = "utf-8") -> str:
        """
        Read text file contents.

        Args:
            path: File path
            encoding: Text encoding

        Returns:
            File contents as string

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: On read failure
        """
        ...

    # Write operations (async, atomic)
    async def write_text(
        self,
        path: AbsolutePath,
        content: str,
        encoding: str = "utf-8",
    ) -> WriteResult:
        """
        Atomically write text to file.

        Uses temp file + atomic replace to ensure readers never
        observe partial writes.

        Args:
            path: Target file path
            content: Text to write
            encoding: Text encoding

        Returns:
            WriteResult with metadata

        Raises:
            IOError: On write failure
        """
        ...

    # Directory operations (async)
    async def mkdirs(self, path: AbsolutePath, exist_ok: bool = True) -> None:
        """
        Create directory and all parents.

        Args:
            path: Directory path
            exist_ok: Don't raise if directory exists

        Raises:
            IOError: On creation failure
        """
        ...

    async def listdir(self, path: AbsolutePath) -> list[str]:
        """
        List directory contents (names only).

        Args:
            path: Directory path

        Returns:
            List of entry names (not full paths)

        Raises:
            FileNotFoundError: If directory doesn't exist
            IOError: On read failure
        """
        ...

    # Removal operations (async)
    async def remove(self, path: AbsolutePath) -> None:
        """
        Remove a file.

        Args:
            path: File path

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: On removal failure
        """
        ...

    async def rmdir(self, path: AbsolutePath, recursive: bool = False) -> None:
        """
        Remove a directory.

        Args:
            path: Directory path
            recursive: Remove contents recursively

        Raises:
            FileNotFoundError: If directory doesn't exist
            IOError: On removal failure
        """
        ...


class FileSystemSync(Protocol):
    """
    Synchronous convenience wrapper protocol.

    Provides blocking versions of FileSystem operations for
    simple scripts, tests, and non-async contexts.

    Implementations typically wrap an async FileSystem and use
    asyncio.run() to execute operations.
    """

    def join(self, base: AbsolutePath, *parts: str) -> AbsolutePath:
        """Safely join path components (sync, no I/O)."""
        ...

    def exists(self, path: AbsolutePath) -> bool:
        """Check if path exists (blocking)."""
        ...

    def is_file(self, path: AbsolutePath) -> bool:
        """Check if path is a file (blocking)."""
        ...

    def is_dir(self, path: AbsolutePath) -> bool:
        """Check if path is a directory (blocking)."""
        ...

    def read_text(self, path: AbsolutePath, encoding: str = "utf-8") -> str:
        """Read text file (blocking)."""
        ...

    def write_text(
        self,
        path: AbsolutePath,
        content: str,
        encoding: str = "utf-8",
    ) -> WriteResult:
        """Write text file atomically (blocking)."""
        ...

    def mkdirs(self, path: AbsolutePath, exist_ok: bool = True) -> None:
        """Create directory and parents (blocking)."""
        ...

    def listdir(self, path: AbsolutePath) -> list[str]:
        """List directory contents (blocking)."""
        ...

    def remove(self, path: AbsolutePath) -> None:
        """Remove file (blocking)."""
        ...

    def rmdir(self, path: AbsolutePath, recursive: bool = False) -> None:
        """Remove directory (blocking)."""
        ...
