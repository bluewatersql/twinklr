"""Tests for diversity validators."""

from twinklr.core.agents.sequencer.group_planner.validators import (
    DIVERSITY_CONSTRAINTS,
    LaneDiversityStats,
    ValidationSeverity,
    compute_lane_stats,
    validate_lane_diversity,
    validate_section_diversity,
)
from twinklr.core.sequencer.planning import LanePlan, SectionCoordinationPlan
from twinklr.core.sequencer.templates.group.models import (
    CoordinationPlan,
    GroupPlacement,
)
from twinklr.core.sequencer.timing import TimeRef
from twinklr.core.sequencer.vocabulary import CoordinationMode, LaneKind
from twinklr.core.sequencer.vocabulary.timing import TimeRefKind

from .conftest import DEFAULT_THEME


class TestDiversityConstraints:
    """Test DiversityConstraints dataclass."""

    def test_base_constraints(self):
        """Test BASE lane constraints."""
        constraints = DIVERSITY_CONSTRAINTS[LaneKind.BASE]
        assert constraints.min_unique_template_ids == 5
        assert constraints.max_uses_per_template_id == 3
        assert constraints.max_consecutive_same_template_id == 1

    def test_rhythm_constraints(self):
        """Test RHYTHM lane constraints."""
        constraints = DIVERSITY_CONSTRAINTS[LaneKind.RHYTHM]
        assert constraints.min_unique_template_ids == 9
        assert constraints.max_uses_per_template_id == 2
        assert constraints.max_consecutive_same_template_id == 0

    def test_accent_constraints(self):
        """Test ACCENT lane constraints."""
        constraints = DIVERSITY_CONSTRAINTS[LaneKind.ACCENT]
        assert constraints.min_unique_template_ids == 8
        assert constraints.max_uses_per_template_id == 2
        assert constraints.max_consecutive_same_template_id == 0


class TestComputeLaneStats:
    """Test compute_lane_stats function."""

    def test_empty_placements(self):
        """Test computing stats with no placements."""
        stats = compute_lane_stats([], LaneKind.BASE)
        assert stats.total_placements == 0
        assert stats.unique_template_ids == 0
        assert stats.max_uses_single_template == 0
        assert stats.max_consecutive_same_template == 0
        assert stats.top2_share == 0.0

    def test_single_placement(self):
        """Test computing stats with single placement."""
        placements = [
            GroupPlacement(
                placement_id="p1",
                group_id="g1",
                template_id="template_a",
                start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=2, beat=1),
            )
        ]
        stats = compute_lane_stats(placements, LaneKind.BASE)
        assert stats.total_placements == 1
        assert stats.unique_template_ids == 1
        assert stats.max_uses_single_template == 1
        assert stats.max_consecutive_same_template == 1
        assert stats.top2_share == 1.0

    def test_multiple_unique_templates(self):
        """Test computing stats with multiple unique templates."""
        placements = [
            GroupPlacement(
                placement_id=f"p{i}",
                group_id="g1",
                template_id=f"template_{chr(97 + i)}",  # a, b, c
                start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=i * 2 + 1, beat=1),
                end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=i * 2 + 2, beat=1),
            )
            for i in range(3)
        ]
        stats = compute_lane_stats(placements, LaneKind.RHYTHM)
        assert stats.total_placements == 3
        assert stats.unique_template_ids == 3
        assert stats.max_uses_single_template == 1

    def test_template_reuse(self):
        """Test computing stats with template reuse."""
        placements = [
            GroupPlacement(
                placement_id="p1",
                group_id="g1",
                template_id="template_a",
                start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=2, beat=1),
            ),
            GroupPlacement(
                placement_id="p2",
                group_id="g2",
                template_id="template_b",
                start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=3, beat=1),
                end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=4, beat=1),
            ),
            GroupPlacement(
                placement_id="p3",
                group_id="g3",
                template_id="template_a",  # Reuse
                start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=5, beat=1),
                end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=6, beat=1),
            ),
        ]
        stats = compute_lane_stats(placements, LaneKind.BASE)
        assert stats.unique_template_ids == 2
        assert stats.max_uses_single_template == 2  # template_a used twice
        assert stats.template_use_counts["template_a"] == 2

    def test_consecutive_detection(self):
        """Test consecutive template detection."""
        placements = [
            GroupPlacement(
                placement_id=f"p{i}",
                group_id=f"g{i}",
                template_id="template_a" if i < 3 else "template_b",
                start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=i * 2 + 1, beat=1),
                end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=i * 2 + 2, beat=1),
            )
            for i in range(5)
        ]
        stats = compute_lane_stats(placements, LaneKind.RHYTHM)
        assert stats.max_consecutive_same_template == 3  # A A A

    def test_top2_share(self):
        """Test top 2 share calculation."""
        # 10 placements: 5x template_a, 3x template_b, 2x template_c
        placements = []
        bar_num = 1
        for template_id, count in [("template_a", 5), ("template_b", 3), ("template_c", 2)]:
            for _ in range(count):
                placements.append(
                    GroupPlacement(
                        placement_id=f"p{len(placements)}",
                        group_id=f"g{len(placements)}",
                        template_id=template_id,
                        start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=bar_num, beat=1),
                        end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=bar_num + 1, beat=1),
                    )
                )
                bar_num += 2

        stats = compute_lane_stats(placements, LaneKind.BASE)
        # Top 2: template_a (5) + template_b (3) = 8 out of 10 = 0.8
        assert stats.top2_share == 0.8


class TestValidateLaneDiversity:
    """Test validate_lane_diversity function."""

    def test_all_constraints_met(self):
        """Test validation passes when all constraints met."""
        stats = LaneDiversityStats(
            lane=LaneKind.BASE,
            total_placements=10,
            unique_template_ids=6,
            max_uses_single_template=2,
            max_consecutive_same_template=1,
            top2_share=0.4,
            template_use_counts={"a": 2, "b": 2, "c": 2, "d": 2, "e": 1, "f": 1},
        )
        constraints = DIVERSITY_CONSTRAINTS[LaneKind.BASE]
        issues = validate_lane_diversity(stats, constraints)
        assert len(issues) == 0

    def test_insufficient_unique_templates(self):
        """Test error when insufficient unique templates."""
        stats = LaneDiversityStats(
            lane=LaneKind.RHYTHM,
            total_placements=10,
            unique_template_ids=5,  # Need 9
            max_uses_single_template=2,
            max_consecutive_same_template=0,
            top2_share=0.3,
            template_use_counts={},
        )
        constraints = DIVERSITY_CONSTRAINTS[LaneKind.RHYTHM]
        issues = validate_lane_diversity(stats, constraints)

        assert len(issues) == 1
        assert issues[0].severity == ValidationSeverity.ERROR
        assert issues[0].code == "INSUFFICIENT_UNIQUE_TEMPLATES"

    def test_template_overused(self):
        """Test error when template overused."""
        stats = LaneDiversityStats(
            lane=LaneKind.RHYTHM,
            total_placements=10,
            unique_template_ids=9,
            max_uses_single_template=3,  # Max 2 allowed
            max_consecutive_same_template=0,
            top2_share=0.3,
            template_use_counts={"a": 3, "b": 1, "c": 1},
        )
        constraints = DIVERSITY_CONSTRAINTS[LaneKind.RHYTHM]
        issues = validate_lane_diversity(stats, constraints)

        assert any(i.code == "TEMPLATE_OVERUSED" for i in issues)

    def test_consecutive_reuse_violation(self):
        """Test error for consecutive reuse."""
        stats = LaneDiversityStats(
            lane=LaneKind.RHYTHM,
            total_placements=10,
            unique_template_ids=9,
            max_uses_single_template=2,
            max_consecutive_same_template=1,  # Max 0 allowed
            top2_share=0.3,
            template_use_counts={},
        )
        constraints = DIVERSITY_CONSTRAINTS[LaneKind.RHYTHM]
        issues = validate_lane_diversity(stats, constraints)

        assert any(i.code == "CONSECUTIVE_REUSE_VIOLATION" for i in issues)

    def test_top_heavy_distribution_warning(self):
        """Test warning for top-heavy distribution."""
        stats = LaneDiversityStats(
            lane=LaneKind.RHYTHM,
            total_placements=10,
            unique_template_ids=9,
            max_uses_single_template=2,
            max_consecutive_same_template=0,
            top2_share=0.6,  # Limit is 0.35
            template_use_counts={},
        )
        constraints = DIVERSITY_CONSTRAINTS[LaneKind.RHYTHM]
        issues = validate_lane_diversity(stats, constraints)

        warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]
        assert len(warnings) == 1
        assert warnings[0].code == "TOP_HEAVY_DISTRIBUTION"


class TestValidateSectionDiversity:
    """Test validate_section_diversity function."""

    def test_plan_with_minimal_lane(self):
        """Test validating minimal plan."""
        plan = SectionCoordinationPlan(
            section_id="section1",
            theme=DEFAULT_THEME,
            lane_plans=[
                LanePlan(
                    lane=LaneKind.BASE,
                    target_roles=["all"],
                    coordination_plans=[],
                )
            ],
        )
        result = validate_section_diversity(plan)
        # Empty coordination_plans means 0 placements - should pass (no constraints violated)
        assert result.is_valid is True

    def test_plan_with_diverse_templates(self):
        """Test validating plan with good diversity."""
        # Create placements with good diversity
        placements = [
            GroupPlacement(
                placement_id=f"p{i}",
                group_id=f"g{i}",
                template_id=f"template_{chr(97 + i)}",  # a, b, c, d, e, f
                start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=i * 2 + 1, beat=1),
                end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=i * 2 + 2, beat=1),
            )
            for i in range(6)
        ]

        plan = SectionCoordinationPlan(
            section_id="section1",
            theme=DEFAULT_THEME,
            lane_plans=[
                LanePlan(
                    lane=LaneKind.BASE,
                    target_roles=["all"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.UNIFIED,
                            group_ids=["g1", "g2"],
                            placements=placements,
                        )
                    ],
                )
            ],
        )

        result = validate_section_diversity(plan)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_plan_with_insufficient_diversity(self):
        """Test validating plan with insufficient diversity."""
        # Only 2 unique templates (need 5 for BASE)
        placements = [
            GroupPlacement(
                placement_id=f"p{i}",
                group_id=f"g{i}",
                template_id="template_a" if i % 2 == 0 else "template_b",
                start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=i * 2 + 1, beat=1),
                end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=i * 2 + 2, beat=1),
            )
            for i in range(10)
        ]

        plan = SectionCoordinationPlan(
            section_id="section1",
            theme=DEFAULT_THEME,
            lane_plans=[
                LanePlan(
                    lane=LaneKind.BASE,
                    target_roles=["all"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.UNIFIED,
                            group_ids=["g1", "g2"],
                            placements=placements,
                        )
                    ],
                )
            ],
        )

        result = validate_section_diversity(plan)
        assert result.is_valid is False
        assert any(e.code == "INSUFFICIENT_UNIQUE_TEMPLATES" for e in result.errors)

    def test_multiple_lanes(self):
        """Test validating plan with multiple lanes."""
        # BASE: Good diversity
        base_placements = [
            GroupPlacement(
                placement_id=f"base_p{i}",
                group_id=f"g{i}",
                template_id=f"base_template_{i}",
                start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=i * 2 + 1, beat=1),
                end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=i * 2 + 2, beat=1),
            )
            for i in range(6)
        ]

        # RHYTHM: Poor diversity (only 3 unique, need 9)
        rhythm_placements = [
            GroupPlacement(
                placement_id=f"rhythm_p{i}",
                group_id=f"g{i}",
                template_id=f"rhythm_template_{i % 3}",  # Only 3 unique
                start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=i * 2 + 1, beat=1),
                end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=i * 2 + 2, beat=1),
            )
            for i in range(10)
        ]

        plan = SectionCoordinationPlan(
            section_id="section1",
            theme=DEFAULT_THEME,
            lane_plans=[
                LanePlan(
                    lane=LaneKind.BASE,
                    target_roles=["all"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.UNIFIED,
                            group_ids=["g1", "g2"],
                            placements=base_placements,
                        )
                    ],
                ),
                LanePlan(
                    lane=LaneKind.RHYTHM,
                    target_roles=["all"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.UNIFIED,
                            group_ids=["g1", "g2"],
                            placements=rhythm_placements,
                        )
                    ],
                ),
            ],
        )

        result = validate_section_diversity(plan)
        assert result.is_valid is False
        # Should have error for RHYTHM lane only
        assert any(
            e.code == "INSUFFICIENT_UNIQUE_TEMPLATES" and "RHYTHM" in str(e.field_path)
            for e in result.errors
        )
