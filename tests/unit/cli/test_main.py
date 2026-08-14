"""Unit tests for CLI path resolution helpers."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from twinklr.cli.main import _resolve_fixture_config_path, build_arg_parser, main


def test_resolve_fixture_config_path_relative_to_job_config_dir() -> None:
    """Relative fixture path resolves against job config directory."""
    job_config_path = Path("/tmp/project/job_config.json")
    resolved = _resolve_fixture_config_path(job_config_path, "configs/fixtures.json")
    assert resolved == Path("/tmp/project/configs/fixtures.json")


def test_resolve_fixture_config_path_keeps_absolute_path() -> None:
    """Absolute fixture path is preserved."""
    job_config_path = Path("/tmp/project/job_config.json")
    fixture_path = Path("/etc/twinklr/fixtures.json")
    resolved = _resolve_fixture_config_path(job_config_path, str(fixture_path))
    assert resolved == fixture_path


class TestEvalReportBridge:
    """Tests for the P1P-T10 `eval-report` CLI bridge."""

    def test_eval_report_listed_in_top_level_help(self) -> None:
        """`eval-report` is a registered subcommand (for `twinklr --help` listing)."""
        parser = build_arg_parser()
        assert "eval-report" in parser._subparsers._group_actions[0].choices

    def test_eval_report_dispatches_to_click_command(self) -> None:
        """`main()` hands eval-report argv straight to the existing click command."""
        with (
            patch.object(sys, "argv", ["twinklr", "eval-report", "--checkpoint", "x.json"]),
            patch("twinklr.core.reporting.evaluation.cli.eval_report_cli.main") as click_main,
        ):
            main()

        click_main.assert_called_once_with(
            args=["--checkpoint", "x.json"], prog_name="twinklr eval-report"
        )

    def test_eval_report_subcommand_registered(self) -> None:
        """`twinklr eval-report --help` works from the installed console script.

        Exercises the real console-script entry point (not just the in-process
        function), which is what the acceptance criterion asks for.
        """
        twinklr = Path(sys.executable).parent / "twinklr"
        assert twinklr.exists(), f"twinklr console script not found at {twinklr}"

        result = subprocess.run(
            [str(twinklr), "eval-report", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"twinklr eval-report --help failed: rc={result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        assert "checkpoint" in result.stdout.lower()

    def test_exactly_one_eval_report_implementation(self) -> None:
        """No duplicated click/argparse implementation of eval-report's logic.

        The argparse subparser carries no options of its own — everything lives in
        the click command it bridges to.
        """
        parser = build_arg_parser()
        subparsers_action = parser._subparsers._group_actions[0]
        eval_report_parser = subparsers_action.choices["eval-report"]
        assert eval_report_parser._actions == []  # no argparse-native options defined
