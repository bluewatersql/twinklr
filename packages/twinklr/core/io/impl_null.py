"""No-op filesystem for development/debugging.

All writes succeed but are discarded.
All reads fail.
"""

from pathlib import Path

from twinklr.core.io.models import AbsolutePath, WriteResult
from twinklr.core.io.sync_adapter import SyncAdapter


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


class NullFileSystemSync(SyncAdapter):
    """Synchronous wrapper around NullFileSystem.

    Delegates all method calls to a NullFileSystem instance via SyncAdapter.
    Maintains full backward compatibility: class name and public API are unchanged.
    """

    def __init__(self) -> None:
        """Initialize with a NullFileSystem instance."""
        super().__init__(NullFileSystem())
