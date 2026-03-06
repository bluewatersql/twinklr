"""Unit tests for the build_coverage_gap script."""

from __future__ import annotations

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_script_module():
    """Import build_coverage_gap as a module (not a package)."""
    script_path = (
        Path(__file__).parent.parent.parent.parent / "scripts" / "build" / "build_coverage_gap.py"
    )
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_coverage_gap", script_path)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCoverageGapScript:
    """Tests for build_coverage_gap.py script functions."""

    def test_script_importable(self) -> None:
        """Script can be imported without error."""
        mod = _load_script_module()
        assert hasattr(mod, "build_coverage_gap")

    def test_coverage_gap_produces_valid_json(self, tmp_path: Path) -> None:
        """build_coverage_gap writes valid JSON output."""
        mod = _load_script_module()
        out_file = tmp_path / "coverage_gap.json"
        mod.build_coverage_gap(output_path=out_file)
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert "generated_at" in data
        assert "effects" in data
        assert "summary" in data
        assert isinstance(data["effects"], list)
        assert len(data["effects"]) > 0

    def test_coverage_gap_summary_counts(self, tmp_path: Path) -> None:
        """Summary fields are integers and consistent with effects list."""
        mod = _load_script_module()
        out_file = tmp_path / "coverage_gap.json"
        mod.build_coverage_gap(output_path=out_file)
        data = json.loads(out_file.read_text())
        summary = data["summary"]

        assert isinstance(summary["total_effects"], int)
        assert isinstance(summary["with_handler"], int)
        assert isinstance(summary["with_template"], int)
        assert isinstance(summary["tier1_gaps"], int)
        assert isinstance(summary["tier2_gaps"], int)

        # Totals must be consistent
        effects = data["effects"]
        assert summary["total_effects"] == len(effects)
        assert summary["with_handler"] == sum(1 for e in effects if e["has_handler"])
        assert summary["with_template"] == sum(1 for e in effects if e["has_template"])

    def test_coverage_gap_effect_entry_shape(self, tmp_path: Path) -> None:
        """Each effect entry has the required fields."""
        mod = _load_script_module()
        out_file = tmp_path / "coverage_gap.json"
        mod.build_coverage_gap(output_path=out_file)
        data = json.loads(out_file.read_text())
        for entry in data["effects"]:
            assert "effect_family" in entry
            assert "corpus_phrase_count" in entry
            assert "has_handler" in entry
            assert "has_template" in entry
            assert "priority_tier" in entry
            assert entry["priority_tier"] in (1, 2, 3)

    def test_coverage_gap_tier1_handlers_present(self, tmp_path: Path) -> None:
        """After Phase 09, all Tier 1 effects have has_handler=True."""
        mod = _load_script_module()
        out_file = tmp_path / "coverage_gap.json"
        mod.build_coverage_gap(output_path=out_file)
        data = json.loads(out_file.read_text())
        tier1 = [e for e in data["effects"] if e["priority_tier"] == 1]
        for entry in tier1:
            assert entry["has_handler"], (
                f"Tier 1 effect '{entry['effect_family']}' is missing a handler"
            )
