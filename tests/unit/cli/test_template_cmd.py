"""CLI contract for moving-head template data conversion and validation."""

from __future__ import annotations

from pathlib import Path

from twinklr.cli.main import build_arg_parser
from twinklr.cli.template_cmd import (
    run_template_export_command,
    run_template_validate_command,
)
from twinklr.core.sequencer.moving_heads.templates.data_loader import (
    load_template_document,
)


def test_template_export_parser_contract(tmp_path: Path) -> None:
    args = build_arg_parser().parse_args(
        [
            "template-export",
            "--out",
            str(tmp_path),
            "--template-id",
            "ambient_random_wash",
        ]
    )

    assert args.cmd == "template-export"
    assert args.template_id == ["ambient_random_wash"]


def test_template_export_and_validate_commands(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    export_args = build_arg_parser().parse_args(
        [
            "template-export",
            "--out",
            str(export_dir),
            "--template-id",
            "ambient_random_wash",
        ]
    )

    assert run_template_export_command(export_args) == 0
    document = load_template_document(export_dir / "ambient_random_wash.json")
    assert document.template.template_id == "ambient_random_wash"

    validate_args = build_arg_parser().parse_args(
        ["template-validate", "--template-dir", str(export_dir)]
    )
    assert run_template_validate_command(validate_args) == 0


def test_run_parser_accepts_configured_template_directory(tmp_path: Path) -> None:
    args = build_arg_parser().parse_args(
        [
            "run",
            "--audio",
            "song.wav",
            "--config",
            "job.json",
            "--template-dir",
            str(tmp_path),
            "--allow-template-overrides",
        ]
    )

    assert args.template_dir == tmp_path
    assert args.allow_template_overrides is True
