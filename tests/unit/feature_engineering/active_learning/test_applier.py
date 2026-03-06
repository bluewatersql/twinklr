"""Tests for CorrectionApplier."""

from __future__ import annotations

from twinklr.core.feature_engineering.active_learning.applier import CorrectionApplier
from twinklr.core.feature_engineering.active_learning.models import (
    TaxonomyCorrectionResult,
)


def _approved(
    candidate_id: str = "cand_001",
    original_family: str = "unknown",
    original_motion: str = "unknown",
    corrected_family: str | None = "SPARKLE",
    corrected_motion: str | None = "sparkle",
    confidence: float = 0.9,
) -> TaxonomyCorrectionResult:
    return TaxonomyCorrectionResult(
        candidate_id=candidate_id,
        original_family=original_family,
        original_motion=original_motion,
        corrected_family=corrected_family,
        corrected_motion=corrected_motion,
        correction_confidence=confidence,
        rationale="Test correction.",
        approved=True,
    )


def _rejected(
    candidate_id: str = "cand_002",
    original_family: str = "unknown",
    original_motion: str = "unknown",
) -> TaxonomyCorrectionResult:
    return TaxonomyCorrectionResult(
        candidate_id=candidate_id,
        original_family=original_family,
        original_motion=original_motion,
        corrected_family=None,
        corrected_motion=None,
        correction_confidence=0.0,
        rationale="LLM response parse error",
        approved=False,
    )


class TestCorrectionApplier:
    def test_approved_corrections_applied_to_taxonomy_rules(self) -> None:
        """Approved corrections mutate taxonomy_rules and appear in the report."""
        applier = CorrectionApplier()
        taxonomy_rules: dict[str, dict[str, str]] = {
            "cand_001": {"family": "unknown", "motion": "unknown"},
        }
        corrections = (_approved(candidate_id="cand_001"),)

        report = applier.apply(corrections, taxonomy_rules)

        assert report.total_applied > 0
        assert report.total_approved == 1
        assert taxonomy_rules["cand_001"]["family"] == "SPARKLE"
        assert taxonomy_rules["cand_001"]["motion"] == "sparkle"
        assert len(report.corrections) == 1
        rec = report.corrections[0]
        assert rec.before_family == "unknown"
        assert rec.after_family == "SPARKLE"

    def test_confidence_uplift_is_non_negative_for_improving_corrections(self) -> None:
        """Confidence uplift >= 0 when approved corrections have higher confidence."""
        applier = CorrectionApplier()
        taxonomy_rules: dict[str, dict[str, str]] = {
            "c1": {"family": "unknown", "motion": "unknown"},
            "c2": {"family": "unknown", "motion": "unknown"},
        }
        # Unapproved item has 0.0 confidence, approved has 0.85 — uplift should be > 0.
        corrections = (
            _rejected(candidate_id="c2"),
            _approved(candidate_id="c1", confidence=0.85),
        )

        report = applier.apply(corrections, taxonomy_rules)

        assert report.confidence_uplift >= 0.0
        assert report.mean_confidence_after >= report.mean_confidence_before

    def test_empty_corrections_returns_zero_report(self) -> None:
        """Empty corrections produce a report with zero counts and no changes."""
        applier = CorrectionApplier()
        taxonomy_rules: dict[str, dict[str, str]] = {
            "cand_x": {"family": "STROBE", "motion": "pulse"},
        }
        original_rules = dict(taxonomy_rules)

        report = applier.apply((), taxonomy_rules)

        assert report.total_candidates == 0
        assert report.total_approved == 0
        assert report.total_applied == 0
        assert len(report.corrections) == 0
        assert taxonomy_rules == original_rules

    def test_rejected_corrections_not_applied(self) -> None:
        """Rejected corrections leave taxonomy_rules unchanged."""
        applier = CorrectionApplier()
        taxonomy_rules: dict[str, dict[str, str]] = {
            "cand_002": {"family": "unknown", "motion": "unknown"},
        }
        corrections = (_rejected(candidate_id="cand_002"),)

        report = applier.apply(corrections, taxonomy_rules)

        assert report.total_applied == 0
        assert taxonomy_rules["cand_002"]["family"] == "unknown"

    def test_unknown_ratio_decreases_after_corrections(self) -> None:
        """Applying corrections that fix unknown families reduces unknown_ratio_after."""
        applier = CorrectionApplier()
        taxonomy_rules: dict[str, dict[str, str]] = {
            "c1": {"family": "unknown", "motion": "unknown"},
            "c2": {"family": "WAVE", "motion": "sweep"},
        }
        corrections = (
            _approved(candidate_id="c1", corrected_family="SHIMMER", corrected_motion="static"),
        )

        report = applier.apply(corrections, taxonomy_rules)

        # Before: 1/2 entries were unknown → 0.5
        assert abs(report.unknown_ratio_before - 0.5) < 1e-6
        # After: c1 is now SHIMMER/static, c2 is WAVE/sweep → both known → 0.0
        assert report.unknown_ratio_after < report.unknown_ratio_before
