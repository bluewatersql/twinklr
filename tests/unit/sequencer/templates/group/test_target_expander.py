"""Tests for TargetExpander — resolves typed targets to concrete group IDs.

Tests target expansion for group, zone, and split target types,
plus plan-level expansion for UNIFIED and SEQUENCED coordination modes.
"""

import pytest

from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationConfig,
    CoordinationPlan,
    GroupPlacement,
    PlacementWindow,
    PlanTarget,
)
from twinklr.core.sequencer.templates.group.models.display import GroupPosition
from twinklr.core.sequencer.templates.group.target_expander import TargetExpander
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    EffectDuration,
    IntensityLevel,
    PlanningTimeRef,
    SplitDimension,
    StepUnit,
    TargetType,
)
from twinklr.core.sequencer.vocabulary.choreography import ChoreoTag
from twinklr.core.sequencer.vocabulary.display import (
    DetailCapability,
    DisplayElementKind,
    DisplayProminence,
    GroupArrangement,
)
from twinklr.core.sequencer.vocabulary.spatial import (
    DepthZone,
    DisplayZone,
    HorizontalZone,
    VerticalZone,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_group(
    id: str,
    *,
    role: str | None = None,
    tags: list[ChoreoTag] | None = None,
    splits: list[SplitDimension] | None = None,
    detail: DetailCapability = DetailCapability.MEDIUM,
    zone: DisplayZone | None = None,
) -> ChoreoGroup:
    return ChoreoGroup(
        id=id,
        role=role or id,
        element_kind=DisplayElementKind.STRING,
        prominence=DisplayProminence.ANCHOR,
        detail_capability=detail,
        arrangement=GroupArrangement.HORIZONTAL_ROW,
        position=GroupPosition(
            horizontal=HorizontalZone.CENTER,
            vertical=VerticalZone.MID,
            depth=DepthZone.NEAR,
            zone=zone,
        ),
        fixture_count=1,
        pixel_fraction=0.1,
        tags=tags or [],
        split_membership=splits or [],
    )


def _make_graph(*groups: ChoreoGroup) -> ChoreographyGraph:
    return ChoreographyGraph(graph_id="test", groups=list(groups))


def _group_target(id: str) -> PlanTarget:
    return PlanTarget(type=TargetType.GROUP, id=id)


def _zone_target(id: str) -> PlanTarget:
    return PlanTarget(type=TargetType.ZONE, id=id)


def _split_target(id: str) -> PlanTarget:
    return PlanTarget(type=TargetType.SPLIT, id=id)


def _start() -> PlanningTimeRef:
    return PlanningTimeRef(bar=1, beat=1)


# ---------------------------------------------------------------------------
# expand_target — GROUP
# ---------------------------------------------------------------------------


class TestExpandTargetGroup:
    """Tests for group target expansion."""

    def test_valid_group(self) -> None:
        graph = _make_graph(_make_group("ARCHES"))
        expander = TargetExpander(graph)
        assert expander.expand_target(_group_target("ARCHES")) == ["ARCHES"]

    def test_unknown_group_raises(self) -> None:
        graph = _make_graph(_make_group("ARCHES"))
        expander = TargetExpander(graph)
        with pytest.raises(ValueError, match="Unknown group target"):
            expander.expand_target(_group_target("NONEXISTENT"))


# ---------------------------------------------------------------------------
# expand_target — ZONE
# ---------------------------------------------------------------------------


class TestExpandTargetZone:
    """Tests for zone target expansion."""

    def test_zone_resolves_to_tagged_groups(self) -> None:
        graph = _make_graph(
            _make_group("OUTLINE", tags=[ChoreoTag.HOUSE]),
            _make_group("WINDOWS", tags=[ChoreoTag.HOUSE]),
            _make_group("ARCHES", tags=[ChoreoTag.YARD]),
        )
        expander = TargetExpander(graph)
        result = expander.expand_target(_zone_target("HOUSE"))
        assert set(result) == {"OUTLINE", "WINDOWS"}

    def test_empty_zone_returns_empty(self) -> None:
        graph = _make_graph(_make_group("ARCHES", tags=[ChoreoTag.YARD]))
        expander = TargetExpander(graph)
        assert expander.expand_target(_zone_target("HOUSE")) == []

    def test_invalid_zone_raises(self) -> None:
        graph = _make_graph(_make_group("ARCHES"))
        expander = TargetExpander(graph)
        with pytest.raises(ValueError, match="Unknown zone target"):
            expander.expand_target(_zone_target("INVALID_ZONE"))


# ---------------------------------------------------------------------------
# expand_target — SPLIT
# ---------------------------------------------------------------------------


class TestExpandTargetSplit:
    """Tests for split target expansion."""

    def test_split_resolves_to_groups_with_membership(self) -> None:
        graph = _make_graph(
            _make_group("ARCHES", splits=[SplitDimension.HALVES_LEFT, SplitDimension.ODD]),
            _make_group("MEGA_TREE", splits=[SplitDimension.HALVES_RIGHT]),
            _make_group("CANDY_CANES", splits=[SplitDimension.HALVES_LEFT]),
        )
        expander = TargetExpander(graph)
        result = expander.expand_target(_split_target("HALVES_LEFT"))
        assert set(result) == {"ARCHES", "CANDY_CANES"}

    def test_odd_split(self) -> None:
        graph = _make_graph(
            _make_group("ARCHES", splits=[SplitDimension.ODD, SplitDimension.EVEN]),
            _make_group("SNOWFLAKES", splits=[SplitDimension.ODD, SplitDimension.EVEN]),
        )
        expander = TargetExpander(graph)
        result = expander.expand_target(_split_target("ODD"))
        assert set(result) == {"ARCHES", "SNOWFLAKES"}

    def test_empty_split_returns_empty(self) -> None:
        graph = _make_graph(_make_group("ARCHES"))
        expander = TargetExpander(graph)
        assert expander.expand_target(_split_target("HALVES_LEFT")) == []

    def test_invalid_split_raises(self) -> None:
        graph = _make_graph(_make_group("ARCHES"))
        expander = TargetExpander(graph)
        with pytest.raises(ValueError, match="Unknown split target"):
            expander.expand_target(_split_target("INVALID_SPLIT"))


# ---------------------------------------------------------------------------
# expand_targets (multiple)
# ---------------------------------------------------------------------------


class TestExpandTargets:
    """Tests for expanding multiple targets with deduplication."""

    def test_deduplicates_across_targets(self) -> None:
        graph = _make_graph(
            _make_group("ARCHES", tags=[ChoreoTag.YARD], splits=[SplitDimension.HALVES_LEFT]),
            _make_group("MEGA_TREE", tags=[ChoreoTag.YARD]),
        )
        expander = TargetExpander(graph)
        result = expander.expand_targets(
            [
                _zone_target("YARD"),
                _split_target("HALVES_LEFT"),
            ]
        )
        # ARCHES appears in both but should only appear once
        assert result.count("ARCHES") == 1
        assert "MEGA_TREE" in result


# ---------------------------------------------------------------------------
# expand_plan — UNIFIED
# ---------------------------------------------------------------------------


class TestExpandPlanUnified:
    """Tests for expanding UNIFIED coordination plans."""

    def test_zone_target_expands_placements(self) -> None:
        graph = _make_graph(
            _make_group("OUTLINE", tags=[ChoreoTag.HOUSE]),
            _make_group("WINDOWS", tags=[ChoreoTag.HOUSE]),
        )
        expander = TargetExpander(graph)

        plan = CoordinationPlan(
            coordination_mode=CoordinationMode.UNIFIED,
            targets=[_zone_target("HOUSE")],
            placements=[
                GroupPlacement(
                    placement_id="base_house_glow",
                    target=_zone_target("HOUSE"),
                    template_id="gtpl_base_glow_warm",
                    start=_start(),
                    duration=EffectDuration.SECTION,
                    intensity=IntensityLevel.SOFT,
                ),
            ],
        )

        expanded = expander.expand_plan(plan)
        assert {t.id for t in expanded.targets} == {"OUTLINE", "WINDOWS"}
        assert len(expanded.placements) == 2
        placement_group_ids = {p.target.id for p in expanded.placements}
        assert placement_group_ids == {"OUTLINE", "WINDOWS"}

    def test_group_target_passthrough(self) -> None:
        graph = _make_graph(_make_group("ARCHES"))
        expander = TargetExpander(graph)

        plan = CoordinationPlan(
            coordination_mode=CoordinationMode.UNIFIED,
            targets=[_group_target("ARCHES")],
            placements=[
                GroupPlacement(
                    placement_id="rhythm_arches",
                    target=_group_target("ARCHES"),
                    template_id="gtpl_rhythm_chase",
                    start=_start(),
                ),
            ],
        )

        expanded = expander.expand_plan(plan)
        assert [t.id for t in expanded.targets] == ["ARCHES"]
        assert len(expanded.placements) == 1
        assert expanded.placements[0].target.id == "ARCHES"


# ---------------------------------------------------------------------------
# expand_plan — SEQUENCED
# ---------------------------------------------------------------------------


class TestExpandPlanSequenced:
    """Tests for expanding SEQUENCED coordination plans."""

    def test_populates_group_order_from_targets(self) -> None:
        graph = _make_graph(
            _make_group("ARCHES", tags=[ChoreoTag.YARD]),
            _make_group("MEGA_TREE", tags=[ChoreoTag.YARD]),
        )
        expander = TargetExpander(graph)

        plan = CoordinationPlan(
            coordination_mode=CoordinationMode.SEQUENCED,
            targets=[_zone_target("YARD")],
            window=PlacementWindow(
                start=_start(),
                end=PlanningTimeRef(bar=4, beat=1),
                template_id="gtpl_rhythm_chase",
                intensity=IntensityLevel.STRONG,
            ),
            config=CoordinationConfig(
                step_unit=StepUnit.BEAT,
                step_duration=2,
            ),
        )

        expanded = expander.expand_plan(plan)
        assert {t.id for t in expanded.targets} == {"ARCHES", "MEGA_TREE"}
        assert expanded.config is not None
        assert set(expanded.config.group_order) == {"ARCHES", "MEGA_TREE"}

    def test_preserves_explicit_group_order(self) -> None:
        graph = _make_graph(
            _make_group("A", tags=[ChoreoTag.YARD]),
            _make_group("B", tags=[ChoreoTag.YARD]),
        )
        expander = TargetExpander(graph)

        plan = CoordinationPlan(
            coordination_mode=CoordinationMode.SEQUENCED,
            targets=[_zone_target("YARD")],
            window=PlacementWindow(
                start=_start(),
                end=PlanningTimeRef(bar=4, beat=1),
                template_id="gtpl_rhythm_chase",
            ),
            config=CoordinationConfig(
                group_order=["B", "A"],
                step_unit=StepUnit.BEAT,
                step_duration=2,
            ),
        )

        expanded = expander.expand_plan(plan)
        assert expanded.config is not None
        assert expanded.config.group_order == ["B", "A"]
