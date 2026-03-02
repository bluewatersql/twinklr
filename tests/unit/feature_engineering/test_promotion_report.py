"""Tests for the PromotionReport Pydantic model.

Validates model creation, defaults, immutability, serialization,
and field semantics.
"""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from twinklr.core.feature_engineering.models.promotion import PromotionReport


def _make_report(**overrides: object) -> PromotionReport:
    """Create a valid PromotionReport with sensible defaults."""
    defaults: dict[str, object] = {
        "total_candidates": 100,
        "filtered_families": 5,
        "eligible_count": 95,
        "passed_quality_gate": 50,
        "rejected_count": 45,
        "after_cluster_dedup": 40,
        "promoted_count": 30,
        "effective_min_stability": 0.05,
        "effective_min_support": 5,
        "adaptive_stability_used": True,
        "family_distribution": {"sparkle": 10, "shimmer": 10, "bars": 10},
        "lane_distribution": {"BASE": 10, "RHYTHM": 10, "ACCENT": 10},
        "avg_layers_per_recipe": 1.8,
    }
    defaults.update(overrides)
    return PromotionReport(**defaults)  # type: ignore[arg-type]


class TestPromotionReportCreation:
    """Model construction and required fields."""

    def test_valid_creation(self) -> None:
        """All required fields produce a valid model."""
        report = _make_report()
        assert report.total_candidates == 100
        assert report.promoted_count == 30

    def test_defaults(self) -> None:
        """Optional fields have correct defaults."""
        report = _make_report()
        assert report.schema_version == "v1.0.0"
        assert report.capped_count == 0
        assert report.stack_promoted_count == 0


class TestPromotionReportImmutability:
    """Frozen model prevents mutation."""

    def test_frozen(self) -> None:
        """Assigning to a field raises ValidationError."""
        report = _make_report()
        with pytest.raises(ValidationError):
            report.promoted_count = 99  # type: ignore[misc]

    def test_forbids_extra(self) -> None:
        """Extra fields raise ValidationError."""
        with pytest.raises(ValidationError):
            _make_report(bogus_field="nope")


class TestPromotionReportSerialization:
    """JSON serialization round-trip."""

    def test_model_dump_json(self) -> None:
        """model_dump(mode='json') returns a dict with all keys."""
        report = _make_report()
        data = report.model_dump(mode="json")
        assert isinstance(data, dict)
        assert "total_candidates" in data
        assert "family_distribution" in data
        assert "lane_distribution" in data
        assert "avg_layers_per_recipe" in data

    def test_round_trip(self) -> None:
        """model_validate(model_dump()) produces identical model."""
        original = _make_report()
        data = original.model_dump(mode="json")
        restored = PromotionReport.model_validate(data)
        assert restored == original


class TestPromotionReportSemantics:
    """Field-level semantic validation."""

    def test_family_distribution_sums_to_promoted(self) -> None:
        """family_distribution values sum to promoted_count."""
        report = _make_report(
            promoted_count=25,
            family_distribution={"sparkle": 10, "shimmer": 8, "bars": 7},
        )
        assert sum(report.family_distribution.values()) == report.promoted_count

    def test_lane_distribution_keys(self) -> None:
        """lane_distribution uses string lane keys."""
        report = _make_report(
            lane_distribution={"BASE": 5, "RHYTHM": 15, "ACCENT": 10},
        )
        assert set(report.lane_distribution.keys()) == {"BASE", "RHYTHM", "ACCENT"}

    def test_capped_count_reflects_capping(self) -> None:
        """capped_count records templates removed by per-family cap."""
        report = _make_report(capped_count=5)
        assert report.capped_count == 5

    def test_stack_promoted_count(self) -> None:
        """stack_promoted_count records multi-layer promotions."""
        report = _make_report(stack_promoted_count=12)
        assert report.stack_promoted_count == 12
