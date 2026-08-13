"""Boundary tests for recipe_builder.

Verifies that the recipe_builder subsystem remains offline-only and
does not introduce coupling to runtime planner, renderer, adapter,
or pipeline entrypoints.
"""

from __future__ import annotations

import importlib
from pathlib import Path
import sys

import pytest

RECIPE_BUILDER_ROOT = "twinklr.core.recipe_builder"

RECIPE_BUILDER_MODULES = (
    f"{RECIPE_BUILDER_ROOT}",
    f"{RECIPE_BUILDER_ROOT}.models",
    f"{RECIPE_BUILDER_ROOT}.evidence",
    f"{RECIPE_BUILDER_ROOT}.generation",
    f"{RECIPE_BUILDER_ROOT}.enrichment",
    f"{RECIPE_BUILDER_ROOT}.validation",
    f"{RECIPE_BUILDER_ROOT}.admission",
    f"{RECIPE_BUILDER_ROOT}.pipeline",
    f"{RECIPE_BUILDER_ROOT}.promotion",
)

RUNTIME_MODULES = (
    "twinklr.core.sequencer.display.renderer",
    "twinklr.core.sequencer.display.composition.engine",
    "twinklr.core.sequencer.display.export.writer",
    "twinklr.core.sequencer.planning.group_plan",
    "twinklr.core.sequencer.planning.planner",
    "twinklr.core.pipeline.display_stages",
    "twinklr.core.pipeline.orchestrator",
    "twinklr.core.agents",
)


def _collect_transitive_imports(module_name: str) -> set[str]:
    """Collect all module names transitively imported by *module_name*.

    Returns the set of fully qualified names that are loaded into
    ``sys.modules`` as a consequence of importing the target module.
    """
    before = set(sys.modules.keys())
    importlib.import_module(module_name)
    after = set(sys.modules.keys())
    return after - before


class TestNoRuntimeCoupling:
    """recipe_builder must not depend on runtime rendering or planning."""

    @pytest.mark.parametrize("rb_module", RECIPE_BUILDER_MODULES)
    @pytest.mark.parametrize("runtime_module", RUNTIME_MODULES)
    def test_recipe_builder_does_not_import_runtime(
        self, rb_module: str, runtime_module: str
    ) -> None:
        """Importing a recipe_builder module must not pull in runtime modules."""
        imported = _collect_transitive_imports(rb_module)
        assert runtime_module not in imported, (
            f"Importing {rb_module} pulled in runtime module {runtime_module}"
        )


class TestRuntimeDoesNotImportRecipeBuilder:
    """Runtime modules must not depend on recipe_builder."""

    @pytest.mark.parametrize("rb_module", RECIPE_BUILDER_MODULES)
    def test_runtime_renderer_does_not_import_recipe_builder(self, rb_module: str) -> None:
        """The display renderer must not import recipe_builder."""
        imported = _collect_transitive_imports("twinklr.core.sequencer.display.renderer")
        assert rb_module not in imported, (
            f"Display renderer imports recipe_builder module {rb_module}"
        )


class TestOfflineOnlyBehavior:
    """recipe_builder produces staged outputs and never mutates the live library."""

    def test_pipeline_writes_only_to_run_dir(self, tmp_path: Path) -> None:
        """Pipeline must write all artifacts under the run directory."""
        from twinklr.core.recipe_builder.pipeline import PipelineConfig, run_pipeline

        config = PipelineConfig(
            run_name="boundary_test_run",
            output_dir=tmp_path,
            dry_run=True,
        )
        manifest = run_pipeline(config)

        run_dir = tmp_path / "boundary_test_run"
        assert run_dir.is_dir()

        for name, artifact_path_str in manifest.artifact_paths.items():
            artifact_path = Path(artifact_path_str)
            if artifact_path.exists():
                assert str(artifact_path).startswith(str(run_dir)), (
                    f"Artifact '{name}' at {artifact_path} is outside run_dir {run_dir}"
                )

    def test_pipeline_does_not_touch_templates_dir(self, tmp_path: Path) -> None:
        """Pipeline must not create or modify files in the templates directory."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        sentinel = templates_dir / "sentinel.txt"
        sentinel.write_text("untouched")

        from twinklr.core.recipe_builder.pipeline import PipelineConfig, run_pipeline

        config = PipelineConfig(
            run_name="boundary_test",
            output_dir=tmp_path / "output",
            templates_dir=templates_dir,
            dry_run=True,
            synthetic_fallback=True,
        )
        run_pipeline(config)

        assert sentinel.read_text() == "untouched"
        contents = list(templates_dir.iterdir())
        assert contents == [sentinel], f"Templates dir was modified: {contents}"

    def test_manifest_records_fe_source(self, tmp_path: Path) -> None:
        """Manifest must record the FE source used for the run."""
        from twinklr.core.recipe_builder.pipeline import PipelineConfig, run_pipeline

        config = PipelineConfig(
            run_name="fe_test",
            output_dir=tmp_path,
            dry_run=True,
        )
        manifest = run_pipeline(config)
        assert "fe_dir" in manifest.input_paths

    def test_library_gap_report_written(self, tmp_path: Path) -> None:
        """Pipeline must write library_gap_report.json."""
        from twinklr.core.recipe_builder.pipeline import PipelineConfig, run_pipeline

        config = PipelineConfig(
            run_name="gap_report_test",
            output_dir=tmp_path,
            dry_run=True,
        )
        run_pipeline(config)

        gap_report = tmp_path / "gap_report_test" / "library_gap_report.json"
        assert gap_report.exists()

    def test_evidence_packets_written(self, tmp_path: Path) -> None:
        """Pipeline must write evidence_packets.jsonl."""
        from twinklr.core.recipe_builder.pipeline import PipelineConfig, run_pipeline

        config = PipelineConfig(
            run_name="evidence_test",
            output_dir=tmp_path,
            dry_run=True,
        )
        run_pipeline(config)

        evidence_path = tmp_path / "evidence_test" / "evidence_packets.jsonl"
        assert evidence_path.exists()

    def test_disable_bootstrap_skips_generation(self, tmp_path: Path) -> None:
        """Setting enable_bootstrap=False must skip the generation phase."""
        from twinklr.core.recipe_builder.pipeline import PipelineConfig, run_pipeline

        config = PipelineConfig(
            run_name="no_boot",
            output_dir=tmp_path,
            enable_bootstrap=False,
            dry_run=True,
        )
        manifest = run_pipeline(config)
        gen_status = next(ps for ps in manifest.phase_status if ps.phase == "generation")
        assert gen_status.status == "skipped"
        assert manifest.summary_metrics.recipe_candidates_generated == 0

    def test_disable_enrich_skips_enrichment(self, tmp_path: Path) -> None:
        """Setting enable_enrich=False must skip the enrichment phase."""
        from twinklr.core.recipe_builder.pipeline import PipelineConfig, run_pipeline

        config = PipelineConfig(
            run_name="no_enrich",
            output_dir=tmp_path,
            enable_enrich=False,
            dry_run=True,
        )
        manifest = run_pipeline(config)
        enrich_status = next(ps for ps in manifest.phase_status if ps.phase == "enrichment")
        assert enrich_status.status == "skipped"
        assert manifest.summary_metrics.metadata_candidates_generated == 0
