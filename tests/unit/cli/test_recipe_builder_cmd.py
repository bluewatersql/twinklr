"""Tests for the `twinklr curate-catalog` CLI subcommand."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from twinklr.cli.main import build_arg_parser
from twinklr.cli.recipe_builder_cmd import run_curate_catalog_command

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CATALOG_TEMPLATES_DIR = _REPO_ROOT / "catalog" / "templates"


class TestArgParsing:
    """`build_arg_parser()` accepts the `curate-catalog` subcommand and its flags."""

    def test_help_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        parser = build_arg_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["curate-catalog", "--help"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "--promote" in out
        assert "--dry-run" in out

    def test_default_templates_dir_is_none(self) -> None:
        """--templates-dir defaults to None, which resolves to catalog/templates/."""
        parser = build_arg_parser()
        args = parser.parse_args(["curate-catalog", "--dry-run"])
        assert args.templates_dir is None

    def test_defaults(self) -> None:
        parser = build_arg_parser()
        args = parser.parse_args(["curate-catalog"])
        assert args.cmd == "curate-catalog"
        assert args.run_name == "curate_run"
        assert args.output_dir == Path("data/recipe_builder")
        assert args.dry_run is False
        assert args.enable_bootstrap is True
        assert args.enable_enrich is True
        assert args.phase == "all"
        assert args.promote is False
        assert args.promote_from is None

    def test_promote_flags_parse(self, tmp_path: Path) -> None:
        parser = build_arg_parser()
        args = parser.parse_args(["curate-catalog", "--promote", "--promote-from", str(tmp_path)])
        assert args.promote is True
        assert args.promote_from == tmp_path

    def test_no_bootstrap_and_no_enrich_flags(self) -> None:
        parser = build_arg_parser()
        args = parser.parse_args(["curate-catalog", "--no-bootstrap", "--no-enrich"])
        assert args.enable_bootstrap is False
        assert args.enable_enrich is False


class TestSmokeRunAgainstTmpCatalog:
    """End-to-end smoke test: dry-run pipeline + explicit promote via the CLI command."""

    def _tmp_catalog(self, tmp_path: Path) -> Path:
        tmp_templates = tmp_path / "templates"
        shutil.copytree(_CATALOG_TEMPLATES_DIR, tmp_templates)
        return tmp_templates

    def test_dry_run_produces_manifest_and_staged_recipes(self, tmp_path: Path) -> None:
        tmp_templates = self._tmp_catalog(tmp_path)
        parser = build_arg_parser()
        args = parser.parse_args(
            [
                "curate-catalog",
                "--run-name",
                "cli_smoke",
                "--output-dir",
                str(tmp_path / "runs"),
                "--templates-dir",
                str(tmp_templates),
                "--dry-run",
            ]
        )

        exit_code = run_curate_catalog_command(args)

        assert exit_code == 0
        run_dir = tmp_path / "runs" / "cli_smoke"
        manifest_path = run_dir / "run_manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert manifest["run_name"] == "cli_smoke"

        staged_dir = run_dir / "staged_recipes"
        assert staged_dir.is_dir()
        assert list(staged_dir.glob("*.json"))

        # Staged only — the tmp catalog's index.json must be untouched.
        index = json.loads((tmp_templates / "index.json").read_text())
        original_index = json.loads((_CATALOG_TEMPLATES_DIR / "index.json").read_text())
        assert len(index["entries"]) == len(original_index["entries"])

    def test_dry_run_then_promote_updates_index(self, tmp_path: Path) -> None:
        tmp_templates = self._tmp_catalog(tmp_path)
        original_index = json.loads((tmp_templates / "index.json").read_text())
        entries_before = len(original_index["entries"])

        parser = build_arg_parser()
        run_args = parser.parse_args(
            [
                "curate-catalog",
                "--run-name",
                "cli_promote_smoke",
                "--output-dir",
                str(tmp_path / "runs"),
                "--templates-dir",
                str(tmp_templates),
                "--dry-run",
            ]
        )
        assert run_curate_catalog_command(run_args) == 0

        promote_args = parser.parse_args(
            [
                "curate-catalog",
                "--run-name",
                "cli_promote_smoke",
                "--output-dir",
                str(tmp_path / "runs"),
                "--templates-dir",
                str(tmp_templates),
                "--promote",
                "--promote-from",
                str(tmp_path / "runs" / "cli_promote_smoke"),
            ]
        )
        assert run_curate_catalog_command(promote_args) == 0

        index_after = json.loads((tmp_templates / "index.json").read_text())
        assert len(index_after["entries"]) > entries_before

        # A second identical promote call is a no-op.
        assert run_curate_catalog_command(promote_args) == 0
        index_final = json.loads((tmp_templates / "index.json").read_text())
        assert len(index_final["entries"]) == len(index_after["entries"])
