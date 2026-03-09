"""Integration tests for the recipe_builder pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from twinklr.core.recipe_builder.pipeline import PipelineConfig, run_pipeline


class TestPipelineIntegration:
    """End-to-end pipeline tests using the real template catalog."""

    def _run(self, tmp_path: Path, **kwargs) -> object:
        config = PipelineConfig(
            run_name="test_run",
            output_dir=tmp_path,
            dry_run=True,
            **kwargs,
        )
        return run_pipeline(config)

    def test_all_phases_complete(self, tmp_path: Path):
        manifest = self._run(tmp_path)
        statuses = {ps.phase: ps.status for ps in manifest.phase_status}
        for phase in ("analysis", "generation", "enrichment", "validation", "admission"):
            assert statuses[phase] == "completed", (
                f"Phase {phase} not completed: {statuses[phase]}"
            )

    def test_run_dir_created(self, tmp_path: Path):
        self._run(tmp_path)
        assert (tmp_path / "test_run").is_dir()

    def test_run_manifest_written(self, tmp_path: Path):
        self._run(tmp_path)
        manifest_path = tmp_path / "test_run" / "run_manifest.json"
        assert manifest_path.exists()
        data = json.loads(manifest_path.read_text())
        assert data["run_name"] == "test_run"

    def test_catalog_analysis_written(self, tmp_path: Path):
        self._run(tmp_path)
        analysis_path = tmp_path / "test_run" / "catalog_analysis.json"
        assert analysis_path.exists()
        data = json.loads(analysis_path.read_text())
        assert "total_recipes" in data

    def test_opportunities_written(self, tmp_path: Path):
        self._run(tmp_path)
        opp_path = tmp_path / "test_run" / "opportunities.json"
        assert opp_path.exists()
        data = json.loads(opp_path.read_text())
        assert "opportunities" in data

    def test_recipe_candidates_generated(self, tmp_path: Path):
        manifest = self._run(tmp_path)
        assert manifest.summary_metrics.recipe_candidates_generated > 0

    def test_opportunities_identified(self, tmp_path: Path):
        manifest = self._run(tmp_path)
        assert manifest.summary_metrics.opportunities_identified > 0

    def test_catalog_loaded(self, tmp_path: Path):
        manifest = self._run(tmp_path)
        assert manifest.summary_metrics.total_recipes_in_catalog > 0

    def test_staged_recipes_written(self, tmp_path: Path):
        manifest = self._run(tmp_path)
        staged_dir = tmp_path / "test_run" / "staged_recipes"
        if manifest.summary_metrics.recipe_candidates_generated > 0:
            assert staged_dir.is_dir()
            staged_count = len(list(staged_dir.glob("*.json")))
            assert staged_count > 0
            assert staged_count <= manifest.summary_metrics.recipe_candidates_generated

    def test_admission_report_parseable(self, tmp_path: Path):
        self._run(tmp_path)
        from twinklr.core.recipe_builder.models import AdmissionReport

        adm_path = tmp_path / "test_run" / "admission_report.json"
        report = AdmissionReport.model_validate_json(adm_path.read_text())
        total = sum(report.counts.values())
        assert total == len(report.decisions)

    def test_partial_run_analysis_only(self, tmp_path: Path):
        manifest = self._run(tmp_path, phases=("analysis",))
        statuses = {ps.phase: ps.status for ps in manifest.phase_status}
        assert statuses["analysis"] == "completed"
        assert statuses.get("generation") in ("skipped", None)

    def test_summary_metrics_consistent(self, tmp_path: Path):
        manifest = self._run(tmp_path)
        m = manifest.summary_metrics
        total_candidates = (
            m.recipe_candidates_generated + m.metadata_candidates_generated
        )
        admitted = m.accepted_to_stage + m.review_required + m.rejected
        assert admitted == total_candidates

    def test_dry_run_uses_deterministic_generation(self, tmp_path: Path):
        self._run(tmp_path)
        candidates_path = tmp_path / "test_run" / "generated_recipe_candidates.json"
        if candidates_path.exists():
            data = json.loads(candidates_path.read_text())
            for candidate in data.get("candidates", []):
                assert candidate["generation_mode"] == "deterministic"
