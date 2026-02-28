"""Unit tests for vendor archive discovery and path cleansing."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from twinklr.core.profiling.discovery import (
    VendorArchive,
    cleanse_output_name,
    discover_vendor_archives,
)


def _write_zip(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w") as archive:
        archive.writestr("dummy.txt", b"data")


class TestDiscoverVendorArchives:
    def test_finds_zip_and_xsqz(self, tmp_path: Path) -> None:
        _write_zip(tmp_path / "VendorA" / "sequence1.zip")
        _write_zip(tmp_path / "VendorA" / "sequence2.xsqz")

        results = discover_vendor_archives(tmp_path)
        assert len(results) == 2
        vendors = {r.vendor for r in results}
        assert vendors == {"VendorA"}

    def test_discovers_across_vendors(self, tmp_path: Path) -> None:
        _write_zip(tmp_path / "Alpha" / "song.zip")
        _write_zip(tmp_path / "Beta" / "carol.zip")

        results = discover_vendor_archives(tmp_path)
        assert len(results) == 2
        vendors = {r.vendor for r in results}
        assert vendors == {"Alpha", "Beta"}

    def test_ignores_non_archive_files(self, tmp_path: Path) -> None:
        (tmp_path / "VendorA").mkdir()
        (tmp_path / "VendorA" / "readme.txt").write_text("hello")
        (tmp_path / "VendorA" / "layout.xml").write_text("<xml/>")
        _write_zip(tmp_path / "VendorA" / "real.zip")

        results = discover_vendor_archives(tmp_path)
        assert len(results) == 1
        assert results[0].archive_path.name == "real.zip"

    def test_ignores_hidden_directories(self, tmp_path: Path) -> None:
        _write_zip(tmp_path / ".working" / "temp.zip")
        _write_zip(tmp_path / "VendorA" / "real.zip")

        results = discover_vendor_archives(tmp_path)
        assert len(results) == 1
        assert results[0].vendor == "VendorA"

    def test_returns_sorted_results(self, tmp_path: Path) -> None:
        _write_zip(tmp_path / "Zebra" / "b.zip")
        _write_zip(tmp_path / "Alpha" / "a.zip")
        _write_zip(tmp_path / "Alpha" / "c.zip")

        results = discover_vendor_archives(tmp_path)
        keys = [(r.vendor, r.archive_path.name) for r in results]
        assert keys == [("Alpha", "a.zip"), ("Alpha", "c.zip"), ("Zebra", "b.zip")]

    def test_returns_empty_for_missing_dir(self, tmp_path: Path) -> None:
        results = discover_vendor_archives(tmp_path / "nonexistent")
        assert results == []

    def test_vendor_archive_metadata(self, tmp_path: Path) -> None:
        _write_zip(tmp_path / "FairyPixelDust" / "SugarPlum.zip")

        results = discover_vendor_archives(tmp_path)
        assert len(results) == 1
        assert isinstance(results[0], VendorArchive)
        assert results[0].vendor == "FairyPixelDust"
        assert results[0].archive_path == tmp_path / "FairyPixelDust" / "SugarPlum.zip"
        assert results[0].sequence_stem == "SugarPlum"


class TestCleanseOutputName:
    def test_basic_vendor_sequence(self) -> None:
        assert cleanse_output_name("FairyPixelDust", "DanceOfSugarPlum") == (
            "FairyPixelDust_DanceOfSugarPlum"
        )

    def test_spaces_replaced_with_hyphens(self) -> None:
        assert cleanse_output_name("BF Light Shows", "Holly Jolly Christmas") == (
            "BF-Light-Shows_Holly-Jolly-Christmas"
        )

    def test_special_chars_stripped(self) -> None:
        assert cleanse_output_name("Vendor!", "Song (feat. Artist) [HD]") == (
            "Vendor_Song-feat.-Artist-HD"
        )

    def test_multiple_spaces_collapsed(self) -> None:
        assert cleanse_output_name("A  B", "C   D") == "A-B_C-D"

    def test_leading_trailing_hyphens_stripped(self) -> None:
        assert cleanse_output_name(" Vendor ", " Song ") == "Vendor_Song"

    def test_preserves_dots_and_hyphens(self) -> None:
        assert cleanse_output_name("xTreme", "v1.4-final") == "xTreme_v1.4-final"
