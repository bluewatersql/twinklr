"""In-memory filesystem for fast, isolated testing.

Simulates filesystem operations without disk I/O.
Async operations complete immediately but maintain async interface.
"""

import asyncio
from pathlib import Path

from .models import AbsolutePath, WriteResult


class FakeFileSystem:
    """
    In-memory async filesystem for testing.

    Simulates filesystem operations without disk I/O.
    Async operations complete immediately but maintain async interface.
    Not thread-safe (use per-test instance).
    """

    def __init__(self) -> None:
        self._files: dict[str, str] = {}
        self._dirs: set[str] = {"/"}  # Root always exists

    def join(self, base: AbsolutePath, *parts: str) -> AbsolutePath:
        """Join paths (sync - no I/O)."""
        result = Path(base).joinpath(*parts)

        # Normalize to absolute
        if not result.is_absolute():
            result = Path("/") / result

        return AbsolutePath(result)

    async def exists(self, path: AbsolutePath) -> bool:
        """Check existence (async, immediate)."""
        path_str = str(Path(path))
        return path_str in self._files or path_str in self._dirs

    async def is_file(self, path: AbsolutePath) -> bool:
        """Check if file (async, immediate)."""
        return str(Path(path)) in self._files

    async def is_dir(self, path: AbsolutePath) -> bool:
        """Check if directory (async, immediate)."""
        return str(Path(path)) in self._dirs

    async def read_text(self, path: AbsolutePath, encoding: str = "utf-8") -> str:
        """Read text (async, immediate)."""
        path_str = str(Path(path))
        if path_str not in self._files:
            raise FileNotFoundError(f"File not found: {path}")
        return self._files[path_str]

    async def write_text(
        self,
        path: AbsolutePath,
        content: str,
        encoding: str = "utf-8",
    ) -> WriteResult:
        """Write text (async, immediate)."""
        path_obj = Path(path)
        path_str = str(path_obj)

        # Auto-create parent directories
        parent = str(path_obj.parent)
        if parent not in self._dirs:
            self._ensure_parents(path_obj.parent)

        self._files[path_str] = content

        return WriteResult(
            path=path_str,
            bytes_written=len(content.encode(encoding)),
            duration_ms=0.0,
        )

    def _ensure_parents(self, path: Path) -> None:
        """Recursively create parent directories (sync helper)."""
        parts = path.parts
        for i in range(1, len(parts) + 1):
            dir_path = str(Path(*parts[:i]))
            self._dirs.add(dir_path)

    async def mkdirs(self, path: AbsolutePath, exist_ok: bool = True) -> None:
        """Create directory (async, immediate)."""
        path_str = str(Path(path))
        if not exist_ok and path_str in self._dirs:
            raise FileExistsError(f"Directory exists: {path}")
        self._ensure_parents(Path(path))
        self._dirs.add(path_str)

    async def listdir(self, path: AbsolutePath) -> list[str]:
        """List directory (async, immediate)."""
        path_str = str(Path(path))
        if path_str not in self._dirs:
            raise FileNotFoundError(f"Directory not found: {path}")

        # Find immediate children
        children = []
        for file_path in self._files.keys():
            if Path(file_path).parent == Path(path_str):
                children.append(Path(file_path).name)
        for dir_path in self._dirs:
            if Path(dir_path).parent == Path(path_str):
                children.append(Path(dir_path).name)

        return sorted(set(children))

    async def remove(self, path: AbsolutePath) -> None:
        """Remove file (async, immediate)."""
        path_str = str(Path(path))
        if path_str not in self._files:
            raise FileNotFoundError(f"File not found: {path}")
        del self._files[path_str]

    async def rmdir(self, path: AbsolutePath, recursive: bool = False) -> None:
        """Remove directory (async, immediate)."""
        path_str = str(Path(path))
        if path_str not in self._dirs:
            raise FileNotFoundError(f"Directory not found: {path}")

        if recursive:
            # Remove all children
            to_remove_files = [p for p in self._files.keys() if p.startswith(path_str + "/")]
            to_remove_dirs = [p for p in self._dirs if p.startswith(path_str + "/")]
            for p in to_remove_files:
                del self._files[p]
            for p in to_remove_dirs:
                self._dirs.discard(p)

        self._dirs.discard(path_str)


class FakeFileSystemSync:
    """
    Synchronous wrapper around FakeFileSystem.

    Since fake operations are instant, this is a thin wrapper
    using asyncio.run() for consistency with RealFileSystemSync.
    """

    def __init__(self) -> None:
        self._async_fs = FakeFileSystem()

    def join(self, base: AbsolutePath, *parts: str) -> AbsolutePath:
        """Join paths (sync - no I/O)."""
        return self._async_fs.join(base, *parts)

    def exists(self, path: AbsolutePath) -> bool:
        """Check existence (blocking)."""
        return asyncio.run(self._async_fs.exists(path))

    def is_file(self, path: AbsolutePath) -> bool:
        """Check if file (blocking)."""
        return asyncio.run(self._async_fs.is_file(path))

    def is_dir(self, path: AbsolutePath) -> bool:
        """Check if directory (blocking)."""
        return asyncio.run(self._async_fs.is_dir(path))

    def read_text(self, path: AbsolutePath, encoding: str = "utf-8") -> str:
        """Read text file (blocking)."""
        return asyncio.run(self._async_fs.read_text(path, encoding))

    def write_text(
        self,
        path: AbsolutePath,
        content: str,
        encoding: str = "utf-8",
    ) -> WriteResult:
        """Write text file (blocking)."""
        return asyncio.run(self._async_fs.write_text(path, content, encoding))

    def mkdirs(self, path: AbsolutePath, exist_ok: bool = True) -> None:
        """Create directory (blocking)."""
        asyncio.run(self._async_fs.mkdirs(path, exist_ok))

    def listdir(self, path: AbsolutePath) -> list[str]:
        """List directory (blocking)."""
        return asyncio.run(self._async_fs.listdir(path))

    def remove(self, path: AbsolutePath) -> None:
        """Remove file (blocking)."""
        asyncio.run(self._async_fs.remove(path))

    def rmdir(self, path: AbsolutePath, recursive: bool = False) -> None:
        """Remove directory (blocking)."""
        asyncio.run(self._async_fs.rmdir(path, recursive))
