"""Real filesystem implementation using aiofiles for async I/O.

Provides atomic writes via temp file + os.replace().
Async-first with high-performance non-blocking I/O.
"""

import asyncio
import os
import time
from pathlib import Path
from tempfile import NamedTemporaryFile

import aiofiles  # type: ignore[import-untyped]
import aiofiles.os  # type: ignore[import-untyped]

from .models import AbsolutePath, WriteResult


class RealFileSystem:
    """
    Real filesystem implementation using aiofiles for async I/O.

    Provides atomic writes via temp file + os.replace().
    Async-first with high-performance non-blocking I/O.
    """

    def join(self, base: AbsolutePath, *parts: str) -> AbsolutePath:
        """Join paths (sync - no I/O)."""
        result = Path(base).joinpath(*parts).resolve()

        # Security: Ensure result is still under base
        base_resolved = Path(base).resolve()
        try:
            result.relative_to(base_resolved)
        except ValueError as e:
            raise ValueError(f"Path traversal detected: {result} escapes {base}") from e

        return AbsolutePath(result)

    async def exists(self, path: AbsolutePath) -> bool:
        """Check existence asynchronously."""
        return bool(await aiofiles.os.path.exists(path))

    async def is_file(self, path: AbsolutePath) -> bool:
        """Check if file asynchronously."""
        return bool(await aiofiles.os.path.isfile(path))

    async def is_dir(self, path: AbsolutePath) -> bool:
        """Check if directory asynchronously."""
        return bool(await aiofiles.os.path.isdir(path))

    async def read_text(self, path: AbsolutePath, encoding: str = "utf-8") -> str:
        """Read text file asynchronously."""
        async with aiofiles.open(path, encoding=encoding) as f:
            content: str = await f.read()
            return content

    async def write_text(
        self,
        path: AbsolutePath,
        content: str,
        encoding: str = "utf-8",
    ) -> WriteResult:
        """Atomically write text file asynchronously."""
        start = time.perf_counter()
        path_obj = Path(path)

        # Ensure parent directory exists
        await aiofiles.os.makedirs(path_obj.parent, exist_ok=True)

        # Atomic write: temp file → replace
        # Create temp file in same directory for atomic replace
        loop = asyncio.get_event_loop()

        def create_temp_file() -> str:
            tmp = NamedTemporaryFile(
                mode="w",
                encoding=encoding,
                dir=path_obj.parent,
                delete=False,
            )
            tmp_path = tmp.name
            tmp.close()
            return tmp_path

        tmp_path = await loop.run_in_executor(None, create_temp_file)

        try:
            # Write content asynchronously
            async with aiofiles.open(tmp_path, mode="w", encoding=encoding) as f:
                await f.write(content)

            # Atomic replace (os.replace is fast, run in executor)
            await loop.run_in_executor(None, os.replace, tmp_path, str(path))
        except Exception:
            # Clean up temp on failure
            try:
                await aiofiles.os.unlink(tmp_path)
            except Exception:
                pass
            raise

        duration = (time.perf_counter() - start) * 1000
        bytes_written = len(content.encode(encoding))

        return WriteResult(
            path=str(path),
            bytes_written=bytes_written,
            duration_ms=duration,
        )

    async def mkdirs(self, path: AbsolutePath, exist_ok: bool = True) -> None:
        """Create directory and parents asynchronously."""
        await aiofiles.os.makedirs(path, exist_ok=exist_ok)

    async def listdir(self, path: AbsolutePath) -> list[str]:
        """List directory contents asynchronously."""
        entries: list[str] = await aiofiles.os.listdir(path)
        return entries

    async def remove(self, path: AbsolutePath) -> None:
        """Remove file asynchronously."""
        await aiofiles.os.unlink(path)

    async def rmdir(self, path: AbsolutePath, recursive: bool = False) -> None:
        """Remove directory asynchronously."""
        if recursive:
            # shutil.rmtree is blocking, run in executor
            loop = asyncio.get_event_loop()
            import shutil

            await loop.run_in_executor(None, shutil.rmtree, str(path))
        else:
            await aiofiles.os.rmdir(path)


class RealFileSystemSync:
    """
    Synchronous wrapper around RealFileSystem.

    Uses asyncio.run() to execute async operations in blocking mode.
    Suitable for simple scripts, tests, and non-async contexts.
    """

    def __init__(self) -> None:
        self._async_fs = RealFileSystem()

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
        """Write text file atomically (blocking)."""
        return asyncio.run(self._async_fs.write_text(path, content, encoding))

    def mkdirs(self, path: AbsolutePath, exist_ok: bool = True) -> None:
        """Create directory and parents (blocking)."""
        asyncio.run(self._async_fs.mkdirs(path, exist_ok))

    def listdir(self, path: AbsolutePath) -> list[str]:
        """List directory contents (blocking)."""
        return asyncio.run(self._async_fs.listdir(path))

    def remove(self, path: AbsolutePath) -> None:
        """Remove file (blocking)."""
        asyncio.run(self._async_fs.remove(path))

    def rmdir(self, path: AbsolutePath, recursive: bool = False) -> None:
        """Remove directory (blocking)."""
        asyncio.run(self._async_fs.rmdir(path, recursive))
