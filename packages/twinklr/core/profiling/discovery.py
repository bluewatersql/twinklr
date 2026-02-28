"""Vendor archive discovery and path cleansing utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from twinklr.core.profiling.pack.ingestor import ZIP_EXTENSIONS

_UNSAFE_CHARS = re.compile(r"[^\w.\-]")
_MULTI_HYPHEN = re.compile(r"-{2,}")


@dataclass(frozen=True)
class VendorArchive:
    """A discovered archive within the vendor_sequences directory tree."""

    vendor: str
    archive_path: Path
    sequence_stem: str


def discover_vendor_archives(vendor_root: Path) -> list[VendorArchive]:
    """Recursively discover zip/xsqz archives under ``<vendor_root>/<vendor>/``.

    Args:
        vendor_root: Root directory containing vendor subdirectories.

    Returns:
        Sorted list of discovered archives with vendor metadata.
    """
    if not vendor_root.exists():
        return []

    results: list[VendorArchive] = []
    for vendor_dir in sorted(vendor_root.iterdir()):
        if not vendor_dir.is_dir() or vendor_dir.name.startswith("."):
            continue
        vendor = vendor_dir.name
        for path in sorted(vendor_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in ZIP_EXTENSIONS:
                continue
            results.append(
                VendorArchive(
                    vendor=vendor,
                    archive_path=path,
                    sequence_stem=path.stem,
                )
            )
    return results


def cleanse_output_name(vendor: str, sequence_stem: str) -> str:
    """Produce a filesystem-safe ``<vendor>_<sequence>`` identifier.

    Replaces whitespace with hyphens, strips unsafe characters, and collapses
    repeated hyphens.
    """
    clean_vendor = _cleanse_segment(vendor)
    clean_stem = _cleanse_segment(sequence_stem)
    return f"{clean_vendor}_{clean_stem}"


def _cleanse_segment(value: str) -> str:
    result = value.strip()
    result = re.sub(r"\s+", "-", result)
    result = _UNSAFE_CHARS.sub("", result)
    result = _MULTI_HYPHEN.sub("-", result)
    return result.strip("-")
