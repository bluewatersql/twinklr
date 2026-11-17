"""CLI contract for moving-head template data validation."""

from __future__ import annotations

from pathlib import Path
import shutil

from twinklr.cli.main import build_arg_parser
from twinklr.cli.template_cmd import run_template_validate_command
from twinklr.core.sequencer.moving_heads.templates.data_loader import (
    PHYSICAL_TEMPLATE_DIR,
    load_template_document,
)


def test_template_validate_command(tmp_path: Path) -> None:
    shutil.copy(PHYSICAL_TEMPLATE_DIR / "mirror_wings.json", tmp_path / "mirror_wings.json")
    document = load_template_document(tmp_path / "mirror_wings.json")
    assert document.template.template_id == "mirror_wings"

    validate_args = build_arg_parser().parse_args(
        ["template-validate", "--template-dir", str(tmp_path)]
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
