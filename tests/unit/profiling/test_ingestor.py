"""Unit tests for package ingestor."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from twinklr.core.profiling.models.enums import FileKind
from twinklr.core.profiling.pack.ingestor import (
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
