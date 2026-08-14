"""CLI coverage for the deterministic, headless FSEQ comparison entry point."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys

import pytest

from twinklr.cli.fseqcmp_cmd import run_fseqcmp_command


def test_fseqcmp_command_returns_zero_for_equal_files(tmp_path: Path) -> None:
    """``twinklr --fseqcmp`` is usable by CI without a running xLights instance."""
    left = tmp_path / "left.fseq"
    right = tmp_path / "right.fseq"
    left.write_bytes(b"same")
    right.write_bytes(b"same")

    assert run_fseqcmp_command(left, right) == 0


def test_fseqcmp_command_returns_one_for_different_files(tmp_path: Path) -> None:
    """A mismatch returns a standard failing check exit status."""
    left = tmp_path / "left.fseq"
    right = tmp_path / "right.fseq"
    left.write_bytes(b"left")
    right.write_bytes(b"right")

    assert run_fseqcmp_command(left, right) == 1


def test_main_routes_top_level_fseqcmp_option(monkeypatch: pytest.MonkeyPatch) -> None:
    """The documented ``twinklr --fseqcmp`` spelling reaches the headless checker."""
    cli_main = importlib.import_module("twinklr.cli.main")
    called_with: list[Path] = []

    def fake_run(expected_path: Path, actual_path: Path) -> int:
        called_with.extend((expected_path, actual_path))
        return 0

    monkeypatch.setattr(cli_main, "run_fseqcmp_command", fake_run)
    monkeypatch.setattr(sys, "argv", ["twinklr", "--fseqcmp", "left.fseq", "right.fseq"])

    with pytest.raises(SystemExit) as exit_result:
        cli_main.main()

    assert exit_result.value.code == 0
    assert called_with == [Path("left.fseq"), Path("right.fseq")]
