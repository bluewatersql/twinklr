"""Tests for SEQUENCED coordination mode expansion and blend modes."""

from __future__ import annotations

from twinklr.core.sequencer.display.composition.engine import (
    CompositionEngine,
)
from twinklr.core.sequencer.display.composition.layer_allocator import (
    LayerAllocator,
)
from twinklr.core.sequencer.display.composition.palette_resolver import (
    PaletteResolver,
)
from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.planning.group_plan import (
    GroupPlanSet,
    LanePlan,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.planning.models import PaletteRef
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationConfig,
    CoordinationPlan,
    PlacementWindow,
)
from twinklr.core.sequencer.templates.group.models.display import (
    DisplayGraph,
    DisplayGroup,
)
from twinklr.core.sequencer.theming import PALETTE_REGISTRY, ThemeRef
from twinklr.core.sequencer.theming.enums import ThemeScope
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    GPBlendMode,
    IntensityLevel,
    LaneKind,
    PlanningTimeRef,
    StepUnit,
)


def _make_beat_grid() -> BeatGrid:
    """120 BPM, 4/4, 16 bars."""
    tempo = 120.0
    bpb = 4
    num_bars = 16
    ms_per_beat = 60_000.0 / tempo
    ms_per_bar = ms_per_beat * bpb
    total_beats = num_bars * bpb

    return BeatGrid(
        bar_boundaries=[i * ms_per_bar for i in range(num_bars + 1)],
        beat_boundaries=[i * ms_per_beat for i in range(total_beats + 1)],
        eighth_boundaries=[i * ms_per_beat / 2 for i in range(total_beats * 2 + 1)],
        sixteenth_boundaries=[i * ms_per_beat / 4 for i in range(total_beats * 4 + 1)],
        tempo_bpm=tempo,
        beats_per_bar=bpb,
        duration_ms=num_bars * ms_per_bar,
    )


def _make_palette_resolver() -> PaletteResolver:
    """Create a palette resolver backed by the global registry."""
    return PaletteResolver(
        catalog=PALETTE_REGISTRY,
        default=ResolvedPalette(colors=["#FF0000", "#00FF00"], active_slots=[1, 2]),
    )


def _make_display_graph() -> DisplayGraph:
    return DisplayGraph(
        display_id="test",
        display_name="Test",
        groups=[
            DisplayGroup(group_id="ARCHES_1", role="ARCHES", display_name="Arches 1"),
            DisplayGroup(group_id="ARCHES_2", role="ARCHES", display_name="Arches 2"),
            DisplayGroup(group_id="ARCHES_3", role="ARCHES", display_name="Arches 3"),
        ],
    )


class TestSequencedExpansion:
    """Tests for SEQUENCED coordination mode."""

    def test_sequenced_creates_staggered_placements(self) -> None:
        """SEQUENCED with 3 groups and 2-beat step creates staggered events."""
        section = SectionCoordinationPlan(
            section_id="test_section",
            theme=ThemeRef(theme_id="theme.test", scope=ThemeScope.SECTION),
            palette=PaletteRef(palette_id="core.christmas_traditional"),
            lane_plans=[
                LanePlan(
                    lane=LaneKind.RHYTHM,
                    target_roles=["ARCHES"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.SEQUENCED,
                            group_ids=["ARCHES_1", "ARCHES_2", "ARCHES_3"],
                            window=PlacementWindow(
                                start=PlanningTimeRef(bar=1, beat=1),
                                end=PlanningTimeRef(bar=5, beat=1),
                                template_id="gtpl_rhythm_chase_single",
                                intensity=IntensityLevel.STRONG,
                            ),
                            config=CoordinationConfig(
                                group_order=["ARCHES_1", "ARCHES_2", "ARCHES_3"],
                                step_unit=StepUnit.BEAT,
                                step_duration=2,
                            ),
                        )
                    ],
                ),
            ],
        )

        plan_set = GroupPlanSet(
            plan_set_id="test",
            section_plans=[section],
        )

        engine = CompositionEngine(
            beat_grid=_make_beat_grid(),
            display_graph=_make_display_graph(),
            palette_resolver=_make_palette_resolver(),
        )
        render_plan = engine.compose(plan_set)

        # Should have events on all 3 arch elements
        element_names = render_plan.element_names
        assert "Arches 1" in element_names
        assert "Arches 2" in element_names
        assert "Arches 3" in element_names

        # Should have staggered start times
        all_events = []
        for group in render_plan.groups:
            for layer in group.layers:
                for event in layer.events:
                    all_events.append((group.element_name, event.start_ms))

        # Events should exist (at least one per group)
        assert len(all_events) >= 3

        # Verify staggering: events for different groups should have
        # different start times (offset by step_duration beats)
        starts_by_element: dict[str, list[int]] = {}
        for name, start in all_events:
            starts_by_element.setdefault(name, []).append(start)

        # Each element should have its own start time pattern
        first_starts = [starts[0] for starts in starts_by_element.values()]
        # All first starts should be different (staggered)
        assert len(set(first_starts)) == len(first_starts)

    def test_sequenced_no_warnings(self) -> None:
        """SEQUENCED with valid window+config should not produce warnings."""
        section = SectionCoordinationPlan(
            section_id="test",
            theme=ThemeRef(theme_id="theme.test", scope=ThemeScope.SECTION),
            palette=PaletteRef(palette_id="core.christmas_traditional"),
            lane_plans=[
                LanePlan(
                    lane=LaneKind.RHYTHM,
                    target_roles=["ARCHES"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.SEQUENCED,
                            group_ids=["ARCHES_1", "ARCHES_2"],
                            window=PlacementWindow(
                                start=PlanningTimeRef(bar=1, beat=1),
                                end=PlanningTimeRef(bar=5, beat=1),
                                template_id="gtpl_rhythm_alternate_ab",
                            ),
                            config=CoordinationConfig(
                                group_order=["ARCHES_1", "ARCHES_2"],
                                step_unit=StepUnit.BEAT,
                                step_duration=1,
                            ),
                        )
                    ],
                ),
            ],
        )

        plan_set = GroupPlanSet(plan_set_id="test", section_plans=[section])
        engine = CompositionEngine(
            beat_grid=_make_beat_grid(),
            display_graph=_make_display_graph(),
            palette_resolver=_make_palette_resolver(),
        )
        render_plan = engine.compose(plan_set)

        # No "Phase 2" warnings — SEQUENCED is now implemented
        phase2_warnings = [
            d for d in render_plan.diagnostics
            if "Phase 2" in d.message
        ]
        assert len(phase2_warnings) == 0


class TestBlendModeMapping:
    """Tests for GPBlendMode → xLights layer method."""

    def test_add_maps_to_normal(self) -> None:
        result = LayerAllocator.resolve_blend_mode(GPBlendMode.ADD)
        assert result == "Normal"

    def test_max_maps_to_max(self) -> None:
        result = LayerAllocator.resolve_blend_mode(GPBlendMode.MAX)
        assert result == "Max"

    def test_alpha_over_maps_to_reveals(self) -> None:
        result = LayerAllocator.resolve_blend_mode(GPBlendMode.ALPHA_OVER)
        assert result == "1 reveals 2"
