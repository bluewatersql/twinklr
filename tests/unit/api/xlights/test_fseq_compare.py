"""Headless FSEQ comparison tests (P2P-T5 CI tier)."""

from __future__ import annotations

from pathlib import Path

from twinklr.core.api.xlights import compare_fseqs


def test_fseqcmp_reports_equal(tmp_path: Path) -> None:
    """Identical FSEQ bytes compare equal without xLights or a display server."""
    expected = tmp_path / "expected.fseq"
    actual = tmp_path / "actual.fseq"
    expected.write_bytes(b"same deterministic payload")
    actual.write_bytes(expected.read_bytes())

    comparison = compare_fseqs(expected, actual)

    assert comparison.equal
    assert comparison.first_difference_offset is None
    assert "identical" in comparison.summary.lower()


def test_fseqcmp_detects_difference(tmp_path: Path) -> None:
    """The CI-tier result identifies the first changed byte and both file hashes."""
    expected = tmp_path / "expected.fseq"
    actual = tmp_path / "actual.fseq"
    expected.write_bytes(b"abc")
    actual.write_bytes(b"axc")

    comparison = compare_fseqs(expected, actual)

    assert not comparison.equal
    assert comparison.first_difference_offset == 1
    assert comparison.expected_sha256 != comparison.actual_sha256
    assert "byte 1" in comparison.summary
