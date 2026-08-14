"""Deterministic, headless comparison for rendered xLights FSEQ outputs."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path


@dataclass(frozen=True)
class FseqComparison:
    """Byte-level comparison result suitable for a CI assertion or CLI report."""

    expected_path: Path
    actual_path: Path
    equal: bool
    expected_size: int
    actual_size: int
    expected_sha256: str
    actual_sha256: str
    first_difference_offset: int | None

    @property
    def summary(self) -> str:
        """Return a concise, actionable comparison summary."""
        if self.equal:
            return (
                "FSEQ files are byte-identical "
                f"({self.expected_size} bytes; sha256={self.expected_sha256})."
            )
        location = (
            f"byte {self.first_difference_offset}"
            if self.first_difference_offset is not None
            else "the file-length boundary"
        )
        return (
            f"FSEQ files differ at {location}: expected {self.expected_size} bytes "
            f"(sha256={self.expected_sha256}), actual {self.actual_size} bytes "
            f"(sha256={self.actual_sha256})."
        )


def _first_difference_offset(expected: bytes, actual: bytes) -> int | None:
    """Find the first byte that differs, including a deterministic length boundary."""
    for offset, (expected_byte, actual_byte) in enumerate(zip(expected, actual, strict=False)):
        if expected_byte != actual_byte:
            return offset
    if len(expected) != len(actual):
        return min(len(expected), len(actual))
    return None


def compare_fseqs(expected_path: Path, actual_path: Path) -> FseqComparison:
    """Compare two rendered FSEQ files without requiring xLights or a display server.

    This intentionally compares bytes rather than inventing a second FSEQ parser. xLights
    owns the binary format and a full render should be deterministic; the hashes, sizes,
    and first changed byte make a failure inspectable while remaining version-agnostic.
    """
    expected = expected_path.read_bytes()
    actual = actual_path.read_bytes()
    expected_hash = hashlib.sha256(expected).hexdigest()
    actual_hash = hashlib.sha256(actual).hexdigest()
    equal = expected == actual
    return FseqComparison(
        expected_path=expected_path,
        actual_path=actual_path,
        equal=equal,
        expected_size=len(expected),
        actual_size=len(actual),
        expected_sha256=expected_hash,
        actual_sha256=actual_hash,
        first_difference_offset=None if equal else _first_difference_offset(expected, actual),
    )
