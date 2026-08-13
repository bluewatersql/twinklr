"""Unit tests for package ingestor."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from twinklr.core.profiling.models.enums import FileKind
from twinklr.core.profiling.pack.ingestor import (
    _validate_zip_entry,
    extract_zip_flat,
    ingest_zip,
    is_zip_like,
)


def _write_zip(path: Path, members: dict[str, bytes]) -> None:
    with ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)


def test_is_zip_like() -> None:
    assert is_zip_like(Path("foo.zip")) is True
    assert is_zip_like(Path("foo.xsqz")) is True
    assert is_zip_like(Path("foo.xsq")) is False


def test_extract_zip_flat_single_level(tmp_path: Path) -> None:
    zip_path = tmp_path / "pack.zip"
    out_dir = tmp_path / "out"
    _write_zip(zip_path, {"folder/a.txt": b"hello", "b.bin": b"x"})

    extract_zip_flat(zip_path, out_dir)

    assert (out_dir / "a.txt").exists()
    assert (out_dir / "b.bin").exists()


def test_extract_zip_flat_recursive(tmp_path: Path) -> None:
    inner = tmp_path / "inner.zip"
    _write_zip(inner, {"nested/file.txt": b"content"})

    outer = tmp_path / "outer.zip"
    _write_zip(outer, {"inner.zip": inner.read_bytes()})

    out_dir = tmp_path / "out"
    extract_zip_flat(outer, out_dir)

    assert (out_dir / "file.txt").exists()
    assert not (out_dir / "inner.zip").exists()


def test_cycle_protection_identical_archives(tmp_path: Path) -> None:
    inner = tmp_path / "inner.zip"
    _write_zip(inner, {"dup.txt": b"same"})

    outer = tmp_path / "outer.zip"
    _write_zip(
        outer,
        {
            "inner_a.zip": inner.read_bytes(),
            "inner_b.zip": inner.read_bytes(),
        },
    )

    out_dir = tmp_path / "out"
    extract_zip_flat(outer, out_dir)

    assert (out_dir / "dup.txt").exists()


def test_ingest_zip_detects_xsq(tmp_path: Path) -> None:
    zip_path = tmp_path / "pack.zip"
    _write_zip(zip_path, {"sequence.xsq": b"<xsequence></xsequence>"})

    manifest, _ = ingest_zip(zip_path)
    assert manifest.sequence_file_id is not None


def test_ingest_zip_sniff_promotes_xml(tmp_path: Path) -> None:
    zip_path = tmp_path / "pack.zip"
    _write_zip(zip_path, {"sequence.xml": b"<xsequence></xsequence>"})

    manifest, extracted = ingest_zip(zip_path)

    assert manifest.sequence_file_id is not None
    promoted = [
        f for f in manifest.files if f.kind is FileKind.SEQUENCE and f.original_ext == ".xml"
    ]
    assert len(promoted) == 1
    assert (extracted / promoted[0].filename).exists()


def test_ingest_zip_sniff_negative_for_layout_xml(tmp_path: Path) -> None:
    zip_path = tmp_path / "pack.zip"
    _write_zip(zip_path, {"xlights_rgbeffects.xml": b"<xrgb></xrgb>"})

    manifest, _ = ingest_zip(zip_path)

    assert manifest.sequence_file_id is None
    assert manifest.rgb_effects_file_id is not None


def test_ingest_zip_xsqz_source_extensions(tmp_path: Path) -> None:
    xsqz_path = tmp_path / "pack.xsqz"
    _write_zip(xsqz_path, {"sequence.xsq": b"<xsequence></xsequence>"})

    manifest, _ = ingest_zip(xsqz_path)
    assert manifest.source_extensions == frozenset({".xsqz"})


def test_ingest_zip_ignores_appledouble_sequence_file(tmp_path: Path) -> None:
    zip_path = tmp_path / "pack.zip"
    _write_zip(
        zip_path,
        {
            "._Broken.xsq": b"not xml",
            "valid_sequence.xsq": b"<xsequence></xsequence>",
        },
    )

    manifest, extracted = ingest_zip(zip_path)
    assert manifest.sequence_file_id is not None
    assert not (extracted / "._Broken.xsq").exists()


# ---------------------------------------------------------------------------
# SEC-03: Zip path traversal validation tests
# ---------------------------------------------------------------------------


def test_validate_zip_entry_safe_path(tmp_path: Path) -> None:
    """A normal zip entry resolves within the target directory."""
    target = _validate_zip_entry("safe_file.xsq", tmp_path)
    assert target == (tmp_path / "safe_file.xsq").resolve()


def test_validate_zip_entry_nested_safe_path(tmp_path: Path) -> None:
    """A nested entry (basename only used) resolves safely."""
    target = _validate_zip_entry("subdir/safe_file.xsq", tmp_path)
    # Path navigation stays inside tmp_path
    assert str(target).startswith(str(tmp_path.resolve()))


def test_validate_zip_entry_path_traversal_raises(tmp_path: Path) -> None:
    """A zip entry with path traversal (../../) raises ValueError."""
    import pytest

    with pytest.raises(ValueError, match="would extract outside target directory"):
        _validate_zip_entry("../../etc/passwd", tmp_path)


def test_validate_zip_entry_absolute_path_raises(tmp_path: Path) -> None:
    """A zip entry with an absolute path raises ValueError."""
    import pytest

    with pytest.raises(ValueError, match="would extract outside target directory"):
        _validate_zip_entry("/etc/passwd", tmp_path)


def test_validate_zip_entry_deep_traversal_raises(tmp_path: Path) -> None:
    """A deeply nested path traversal attempt raises ValueError."""
    import pytest

    with pytest.raises(ValueError, match="would extract outside target directory"):
        _validate_zip_entry("a/b/c/../../../../../../../../etc/shadow", tmp_path)


def test_extract_zip_flat_traversal_entry_raises(tmp_path: Path) -> None:
    """Zip archive containing a path-traversal entry raises ValueError during extraction."""
    import pytest

    zip_path = tmp_path / "evil.zip"
    out_dir = tmp_path / "out"

    # Manually craft a zip with a traversal entry
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("../../etc/passwd", b"root:x:0:0:root:/root:/bin/bash")

    with pytest.raises(ValueError, match="would extract outside target directory"):
        extract_zip_flat(zip_path, out_dir)


# ---------------------------------------------------------------------------
# Content-hash identity (P1K-T1)
# ---------------------------------------------------------------------------


def test_ingest_zip_is_idempotent_on_unchanged_archive(tmp_path: Path) -> None:
    """Re-ingesting byte-identical input yields identical package_id/file_ids."""
    zip_path = tmp_path / "pack.xsqz"
    _write_zip(
        zip_path,
        {
            "sequence.xsq": b"<xsequence></xsequence>",
            "xlights_rgbeffects.xml": b"<xrgb></xrgb>",
            "song.mp3": b"audio-bytes",
        },
    )

    first, _ = ingest_zip(zip_path)
    second, _ = ingest_zip(zip_path)

    assert first.package_id == second.package_id
    assert first.package_id == first.zip_sha256[:16]
    assert [f.file_id for f in first.files] == [f.file_id for f in second.files]
    assert first.sequence_file_id == second.sequence_file_id
    assert first.rgb_effects_file_id == second.rgb_effects_file_id


def test_ingest_zip_changes_id_on_content_change(tmp_path: Path) -> None:
    """A single changed byte in the archive changes package_id."""
    original = tmp_path / "original.zip"
    _write_zip(original, {"sequence.xsq": b"<xsequence></xsequence>"})

    mutated = tmp_path / "mutated.zip"
    data = bytearray(original.read_bytes())
    data[-1] = (data[-1] + 1) % 256
    mutated.write_bytes(bytes(data))

    first, _ = ingest_zip(original)
    second, _ = ingest_zip(mutated)

    assert first.zip_sha256 != second.zip_sha256
    assert first.package_id != second.package_id


def test_duplicate_content_files_share_file_id(tmp_path: Path) -> None:
    """Byte-identical files are content-addressed to the same file_id."""
    zip_path = tmp_path / "dupes.zip"
    _write_zip(
        zip_path,
        {
            "one.txt": b"same-bytes",
            "two.txt": b"same-bytes",
            "sequence.xsq": b"<xsequence></xsequence>",
        },
    )

    manifest, _ = ingest_zip(zip_path)
    by_name = {entry.filename: entry for entry in manifest.files}

    assert by_name["one.txt"].file_id == by_name["two.txt"].file_id
    assert all(entry.file_id == entry.sha256 for entry in manifest.files)


def test_promoted_xml_sequence_file_id_is_content_derived(tmp_path: Path) -> None:
    """An XML sequence promoted to .xsq gets its own SHA-256 as file_id."""
    zip_path = tmp_path / "promote.zip"
    _write_zip(zip_path, {"show.xml": b"<xsequence><head/></xsequence>"})

    first, _ = ingest_zip(zip_path)
    second, _ = ingest_zip(zip_path)

    promoted = next(entry for entry in first.files if entry.original_ext == ".xml")
    assert promoted.file_id == promoted.sha256
    assert first.sequence_file_id == second.sequence_file_id == promoted.file_id
