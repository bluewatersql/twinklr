"""Models for filesystem abstraction layer.

Provides type-safe path wrappers and operation result types.
"""

from pathlib import Path
from typing import NewType

from pydantic import BaseModel, Field

# Type-safe path wrappers
AbsolutePath = NewType("AbsolutePath", Path)
RelativePath = NewType("RelativePath", Path)


def absolute_path(path: str | Path) -> AbsolutePath:
    """
    Validate and construct an absolute path.

    Args:
        path: String or Path object

    Returns:
        AbsolutePath instance

    Raises:
        ValueError: If path is not absolute

    Example:
        >>> p = absolute_path("/tmp/cache")
        >>> assert Path(p).is_absolute()
    """
    p = Path(path).resolve()
    if not p.is_absolute():
        raise ValueError(f"Path must be absolute: {path}")
    return AbsolutePath(p)


def relative_path(path: str | Path) -> RelativePath:
    """
    Validate and construct a relative path.

    Args:
        path: String or Path object

    Returns:
        RelativePath instance

    Raises:
        ValueError: If path is absolute

    Example:
        >>> p = relative_path("cache/step_id")
        >>> assert not Path(p).is_absolute()
    """
    p = Path(path)
    if p.is_absolute():
        raise ValueError(f"Path must be relative: {path}")
    return RelativePath(p)


class WriteResult(BaseModel):
    """Result of a filesystem write operation.

    Attributes:
        path: Final path written
        bytes_written: Number of bytes written
        duration_ms: Operation duration in milliseconds
    """

    path: str = Field(description="Final path written")
    bytes_written: int = Field(description="Number of bytes written", ge=0)
    duration_ms: float = Field(description="Operation duration in milliseconds", ge=0.0)
