"""No-op filesystem for development/debugging.

All writes succeed but are discarded.
All reads fail.
"""

import asyncio
from pathlib import Path

from .models import AbsolutePath, WriteResult


class NullFileSystem:
    """
    No-op async filesystem for development/debugging.

    All writes succeed but are discarded.
    All reads fail.
    """

    def join(self, base: AbsolutePath, *parts: str) -> AbsolutePath:
        """Join paths (sync - no I/O)."""
        return AbsolutePath(Path(base).joinpath(*parts))

    async def exists(self, path: AbsolutePath) -> bool:
        """Always returns False (async)."""
        return False

    async def is_file(self, path: AbsolutePath) -> bool:
        """Always returns False (async)."""
        return False

    async def is_dir(self, path: AbsolutePath) -> bool:
        """Always returns False (async)."""
        return False

    async def read_text(self, path: AbsolutePath, encoding: str = "utf-8") -> str:
        """Always raises FileNotFoundError (async)."""
        raise FileNotFoundError(f"NullFileSystem: {path}")

    async def write_text(
        self,
        path: AbsolutePath,
        content: str,
        encoding: str = "utf-8",
    ) -> WriteResult:
        """Discard write, return fake success (async)."""
        return WriteResult(
            path=str(path),
            bytes_written=len(content.encode(encoding)),
            duration_ms=0.0,
        )

    async def mkdirs(self, path: AbsolutePath, exist_ok: bool = True) -> None:
        """No-op (async)."""
        pass

    async def listdir(self, path: AbsolutePath) -> list[str]:
        """Always returns empty list (async)."""
        return []

    async def remove(self, path: AbsolutePath) -> None:
        """No-op (async)."""
        pass

    async def rmdir(self, path: AbsolutePath, recursive: bool = False) -> None:
        """No-op (async)."""
        pass


class NullFileSystemSync:
    """
    Synchronous wrapper around NullFileSystem.
    """

    def __init__(self) -> None:
        self._async_fs = NullFileSystem()

    def join(self, base: AbsolutePath, *parts: str) -> AbsolutePath:
        """Join paths (sync - no I/O)."""
        return self._async_fs.join(base, *parts)

    def exists(self, path: AbsolutePath) -> bool:
        """Always returns False (blocking)."""
        return asyncio.run(self._async_fs.exists(path))

    def is_file(self, path: AbsolutePath) -> bool:
        """Always returns False (blocking)."""
        return asyncio.run(self._async_fs.is_file(path))

    def is_dir(self, path: AbsolutePath) -> bool:
        """Always returns False (blocking)."""
        return asyncio.run(self._async_fs.is_dir(path))

    def read_text(self, path: AbsolutePath, encoding: str = "utf-8") -> str:
        """Always raises FileNotFoundError (blocking)."""
        return asyncio.run(self._async_fs.read_text(path, encoding))

    def write_text(
        self,
        path: AbsolutePath,
        content: str,
        encoding: str = "utf-8",
    ) -> WriteResult:
        """Discard write, return fake success (blocking)."""
        return asyncio.run(self._async_fs.write_text(path, content, encoding))

    def mkdirs(self, path: AbsolutePath, exist_ok: bool = True) -> None:
        """No-op (blocking)."""
        asyncio.run(self._async_fs.mkdirs(path, exist_ok))

    def listdir(self, path: AbsolutePath) -> list[str]:
        """Always returns empty list (blocking)."""
        return asyncio.run(self._async_fs.listdir(path))

    def remove(self, path: AbsolutePath) -> None:
        """No-op (blocking)."""
        asyncio.run(self._async_fs.remove(path))

    def rmdir(self, path: AbsolutePath, recursive: bool = False) -> None:
        """No-op (blocking)."""
        asyncio.run(self._async_fs.rmdir(path, recursive))
