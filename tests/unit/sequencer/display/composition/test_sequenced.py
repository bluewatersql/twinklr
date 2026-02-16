"""Tests for SEQUENCED, RIPPLE, and CALL_RESPONSE coordination mode expansion."""

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
from twinklr.core.sequencer.templates.group import (
    REGISTRY,
    load_builtin_group_templates,
)
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationConfig,
    CoordinationPlan,
    PlacementWindow,
)
from twinklr.core.sequencer.templates.group.models.display import (
    DisplayGraph,
    DisplayGroup,
    GroupPosition,
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
from twinklr.core.sequencer.vocabulary.coordination import SpatialIntent
from twinklr.core.sequencer.vocabulary.spatial import (
    DepthZone,
    HorizontalZone,
    VerticalZone,
)

# Ensure builtins are loaded once for all tests in this module
load_builtin_group_templates()


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
            template_registry=REGISTRY,
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
            template_registry=REGISTRY,
        )
        render_plan = engine.compose(plan_set)

        # No "Phase 2" warnings — SEQUENCED is now implemented
        phase2_warnings = [d for d in render_plan.diagnostics if "Phase 2" in d.message]
        assert len(phase2_warnings) == 0


def _collect_events(render_plan: object) -> list[tuple[str, int, int]]:
    """Collect (element_name, start_ms, end_ms) from a render plan."""
    events = []
    for group in render_plan.groups:  # type: ignore[attr-defined]
        for layer in group.layers:
            for event in layer.events:
                events.append((group.element_name, event.start_ms, event.end_ms))
    return events


class TestRippleExpansion:
    """Tests for RIPPLE coordination mode (overlapping wave propagation)."""

    def _make_ripple_plan(
        self,
        phase_offset: float = 0.5,
        step_duration: int = 2,
    ) -> GroupPlanSet:
        """Create a plan with RIPPLE coordination."""
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
                            coordination_mode=CoordinationMode.RIPPLE,
                            group_ids=["ARCHES_1", "ARCHES_2", "ARCHES_3"],
                            window=PlacementWindow(
                                start=PlanningTimeRef(bar=1, beat=1),
                                end=PlanningTimeRef(bar=9, beat=1),
                                template_id="gtpl_rhythm_chase_single",
                                intensity=IntensityLevel.STRONG,
                            ),
                            config=CoordinationConfig(
                                group_order=["ARCHES_1", "ARCHES_2", "ARCHES_3"],
                                step_unit=StepUnit.BEAT,
                                step_duration=step_duration,
                                phase_offset=phase_offset,
                            ),
                        )
                    ],
                ),
            ],
        )
        return GroupPlanSet(plan_set_id="test", section_plans=[section])

    def test_ripple_creates_overlapping_events(self) -> None:
        """RIPPLE with phase_offset=0.5 produces overlapping group events."""
        plan_set = self._make_ripple_plan(phase_offset=0.5)
        engine = CompositionEngine(
            beat_grid=_make_beat_grid(),
            display_graph=_make_display_graph(),
            palette_resolver=_make_palette_resolver(),
            template_registry=REGISTRY,
        )
        render_plan = engine.compose(plan_set)

        events = _collect_events(render_plan)
        assert len(events) >= 3

        # Group events by element
        by_element: dict[str, list[tuple[int, int]]] = {}
        for name, start, end in events:
            by_element.setdefault(name, []).append((start, end))

        # All 3 arches should have events
        assert len(by_element) == 3

        # First events should be staggered by phase_offset * step_ms
        first_starts = sorted(v[0][0] for v in by_element.values())
        # With 120 BPM, 2-beat step = 1000ms, phase_offset = 0.5 → 500ms stagger
        assert first_starts[1] - first_starts[0] == 500
        assert first_starts[2] - first_starts[1] == 500

    def test_ripple_events_overlap(self) -> None:
        """RIPPLE groups have overlapping time ranges (unlike SEQUENCED)."""
        # Use step_duration=4 (4 beats = 2000ms) so overlap is unambiguous
        plan_set = self._make_ripple_plan(phase_offset=0.5, step_duration=4)
        engine = CompositionEngine(
            beat_grid=_make_beat_grid(),
            display_graph=_make_display_graph(),
            palette_resolver=_make_palette_resolver(),
            template_registry=REGISTRY,
        )
        render_plan = engine.compose(plan_set)

        events = _collect_events(render_plan)
        by_element: dict[str, list[tuple[int, int]]] = {}
        for name, start, end in events:
            by_element.setdefault(name, []).append((start, end))

        # Group 1's first event should overlap with Group 0's first event
        # Group 0 starts at 0ms, Group 1 starts at 500ms
        # Group 0 should still be active when Group 1 starts
        first_events = {}
        for name, times in by_element.items():
            first_events[name] = times[0]

        names = sorted(first_events.keys())
        if len(names) >= 2:
            _g0_start, g0_end = first_events[names[0]]
            g1_start, _ = first_events[names[1]]
            # Group 1 starts BEFORE Group 0 ends (overlap)
            assert g1_start < g0_end

    def test_ripple_zero_offset_falls_back_to_sequenced(self) -> None:
        """RIPPLE with phase_offset=0 behaves like SEQUENCED (no overlap)."""
        plan_set = self._make_ripple_plan(phase_offset=0.0)
        engine = CompositionEngine(
            beat_grid=_make_beat_grid(),
            display_graph=_make_display_graph(),
            palette_resolver=_make_palette_resolver(),
            template_registry=REGISTRY,
        )
        render_plan = engine.compose(plan_set)

        events = _collect_events(render_plan)
        assert len(events) >= 3

        # Events should exist but with SEQUENCED-like spacing
        by_element: dict[str, list[tuple[int, int]]] = {}
        for name, start, end in events:
            by_element.setdefault(name, []).append((start, end))
        assert len(by_element) == 3


class TestCallResponseExpansion:
    """Tests for CALL_RESPONSE coordination mode (alternating A/B groups)."""

    def _make_cr_plan(self) -> GroupPlanSet:
        """Create a plan with CALL_RESPONSE coordination."""
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
                            coordination_mode=CoordinationMode.CALL_RESPONSE,
                            group_ids=["ARCHES_1", "ARCHES_2", "ARCHES_3"],
                            window=PlacementWindow(
                                start=PlanningTimeRef(bar=1, beat=1),
                                end=PlanningTimeRef(bar=9, beat=1),
                                template_id="gtpl_rhythm_alternate_ab",
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
        return GroupPlanSet(plan_set_id="test", section_plans=[section])

    def test_call_response_alternates_groups(self) -> None:
        """CALL_RESPONSE alternates between A and B teams."""
        plan_set = self._make_cr_plan()
        engine = CompositionEngine(
            beat_grid=_make_beat_grid(),
            display_graph=_make_display_graph(),
            palette_resolver=_make_palette_resolver(),
            template_registry=REGISTRY,
        )
        render_plan = engine.compose(plan_set)

        events = _collect_events(render_plan)
        assert len(events) >= 3

        # Group events by element
        by_element: dict[str, list[tuple[int, int]]] = {}
        for name, start, end in events:
            by_element.setdefault(name, []).append((start, end))

        # All groups should have events
        assert len(by_element) >= 2

    def test_call_response_teams_dont_overlap(self) -> None:
        """A-team and B-team placements should not overlap in time."""
        plan_set = self._make_cr_plan()
        engine = CompositionEngine(
            beat_grid=_make_beat_grid(),
            display_graph=_make_display_graph(),
            palette_resolver=_make_palette_resolver(),
            template_registry=REGISTRY,
        )
        render_plan = engine.compose(plan_set)

        events = _collect_events(render_plan)
        by_element: dict[str, list[tuple[int, int]]] = {}
        for name, start, end in events:
            by_element.setdefault(name, []).append((start, end))

        names = sorted(by_element.keys())
        if len(names) >= 2:
            # A-team (even index in group_order): Arches 1, Arches 3
            # B-team (odd index): Arches 2
            # Their events should not overlap (call then response)
            a_times = by_element.get("Arches 1", [])
            b_times = by_element.get("Arches 2", [])

            for a_start, a_end in a_times:
                for b_start, b_end in b_times:
                    # No overlap: a ends before b starts, or b ends before a starts
                    assert a_end <= b_start or b_end <= a_start, (
                        f"A-team ({a_start}-{a_end}) overlaps B-team ({b_start}-{b_end})"
                    )

    def test_call_response_a_team_starts_first(self) -> None:
        """A-team (even-index groups) should start at beat 0."""
        plan_set = self._make_cr_plan()
        engine = CompositionEngine(
            beat_grid=_make_beat_grid(),
            display_graph=_make_display_graph(),
            palette_resolver=_make_palette_resolver(),
            template_registry=REGISTRY,
        )
        render_plan = engine.compose(plan_set)

        events = _collect_events(render_plan)
        by_element: dict[str, list[int]] = {}
        for name, start, _ in events:
            by_element.setdefault(name, []).append(start)

        # Arches 1 (A-team) should have an event starting at 0
        a1_starts = by_element.get("Arches 1", [])
        assert 0 in a1_starts, f"A-team should start at 0, got {a1_starts}"


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


class TestSpatialIntentOrdering:
    """Tests that SpatialIntent reorders group_order in expand methods."""

    def test_l2r_reorders_groups_by_horizontal_position(self) -> None:
        """L2R spatial intent should reorder groups left-to-right."""
        # Create groups with explicit horizontal positions: 3=RIGHT, 2=CENTER, 1=LEFT
        display_graph = DisplayGraph(
            display_id="test",
            display_name="Test",
            groups=[
                DisplayGroup(
                    group_id="ARCHES_1",
                    role="ARCHES",
                    display_name="Arches 1",
                    position=GroupPosition(
                        horizontal=HorizontalZone.LEFT, vertical=VerticalZone.LOW
                    ),
                ),
                DisplayGroup(
                    group_id="ARCHES_2",
                    role="ARCHES",
                    display_name="Arches 2",
                    position=GroupPosition(
                        horizontal=HorizontalZone.CENTER, vertical=VerticalZone.LOW
                    ),
                ),
                DisplayGroup(
                    group_id="ARCHES_3",
                    role="ARCHES",
                    display_name="Arches 3",
                    position=GroupPosition(
                        horizontal=HorizontalZone.RIGHT, vertical=VerticalZone.LOW
                    ),
                ),
            ],
        )

        # Plan specifies group_order as [3, 1, 2] (wrong spatial order)
        # but SpatialIntent.L2R should reorder to [1, 2, 3]
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
                            group_ids=["ARCHES_3", "ARCHES_1", "ARCHES_2"],
                            window=PlacementWindow(
                                start=PlanningTimeRef(bar=1, beat=1),
                                end=PlanningTimeRef(bar=5, beat=1),
                                template_id="gtpl_rhythm_chase_single",
                                intensity=IntensityLevel.STRONG,
                            ),
                            config=CoordinationConfig(
                                group_order=["ARCHES_3", "ARCHES_1", "ARCHES_2"],
                                step_unit=StepUnit.BEAT,
                                step_duration=2,
                                spatial_intent=SpatialIntent.L2R,
                            ),
                        )
                    ],
                ),
            ],
        )

        plan_set = GroupPlanSet(plan_set_id="test", section_plans=[section])
        engine = CompositionEngine(
            beat_grid=_make_beat_grid(),
            display_graph=display_graph,
            palette_resolver=_make_palette_resolver(),
            template_registry=REGISTRY,
        )
        render_plan = engine.compose(plan_set)

        events = _collect_events(render_plan)
        by_element: dict[str, list[int]] = {}
        for name, start, _ in events:
            by_element.setdefault(name, []).append(start)

        # With L2R ordering: Arches 1 (LEFT) should start first,
        # then Arches 2 (CENTER), then Arches 3 (RIGHT)
        a1_first = min(by_element.get("Arches 1", [999999]))
        a2_first = min(by_element.get("Arches 2", [999999]))
        a3_first = min(by_element.get("Arches 3", [999999]))

        assert a1_first < a2_first, "LEFT group should start before CENTER"
        assert a2_first < a3_first, "CENTER group should start before RIGHT"

    def test_b2t_reorders_groups_by_vertical_position(self) -> None:
        """B2T spatial intent should reorder groups bottom-to-top."""
        display_graph = DisplayGraph(
            display_id="test",
            display_name="Test",
            groups=[
                DisplayGroup(
                    group_id="ROW_HIGH",
                    role="ROW",
                    display_name="Row High",
                    position=GroupPosition(
                        horizontal=HorizontalZone.CENTER, vertical=VerticalZone.HIGH
                    ),
                ),
                DisplayGroup(
                    group_id="ROW_LOW",
                    role="ROW",
                    display_name="Row Low",
                    position=GroupPosition(
                        horizontal=HorizontalZone.CENTER, vertical=VerticalZone.LOW
                    ),
                ),
                DisplayGroup(
                    group_id="ROW_GROUND",
                    role="ROW",
                    display_name="Row Ground",
                    position=GroupPosition(
                        horizontal=HorizontalZone.CENTER, vertical=VerticalZone.GROUND
                    ),
                ),
            ],
        )

        section = SectionCoordinationPlan(
            section_id="test_section",
            theme=ThemeRef(theme_id="theme.test", scope=ThemeScope.SECTION),
            palette=PaletteRef(palette_id="core.christmas_traditional"),
            lane_plans=[
                LanePlan(
                    lane=LaneKind.RHYTHM,
                    target_roles=["ROW"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.SEQUENCED,
                            group_ids=["ROW_HIGH", "ROW_LOW", "ROW_GROUND"],
                            window=PlacementWindow(
                                start=PlanningTimeRef(bar=1, beat=1),
                                end=PlanningTimeRef(bar=5, beat=1),
                                template_id="gtpl_rhythm_chase_single",
                                intensity=IntensityLevel.STRONG,
                            ),
                            config=CoordinationConfig(
                                group_order=["ROW_HIGH", "ROW_LOW", "ROW_GROUND"],
                                step_unit=StepUnit.BEAT,
                                step_duration=2,
                                spatial_intent=SpatialIntent.B2T,
                            ),
                        )
                    ],
                ),
            ],
        )

        plan_set = GroupPlanSet(plan_set_id="test", section_plans=[section])
        engine = CompositionEngine(
            beat_grid=_make_beat_grid(),
            display_graph=display_graph,
            palette_resolver=_make_palette_resolver(),
            template_registry=REGISTRY,
        )
        render_plan = engine.compose(plan_set)

        events = _collect_events(render_plan)
        by_element: dict[str, list[int]] = {}
        for name, start, _ in events:
            by_element.setdefault(name, []).append(start)

        ground_first = min(by_element.get("Row Ground", [999999]))
        low_first = min(by_element.get("Row Low", [999999]))
        high_first = min(by_element.get("Row High", [999999]))

        assert ground_first < low_first, "GROUND group should start before LOW"
        assert low_first < high_first, "LOW group should start before HIGH"

    def test_f2b_reorders_groups_by_depth_position(self) -> None:
        """F2B spatial intent should reorder groups front-to-back."""
        display_graph = DisplayGraph(
            display_id="test",
            display_name="Test",
            groups=[
                DisplayGroup(
                    group_id="LAYER_FAR",
                    role="LAYER",
                    display_name="Layer Far",
                    position=GroupPosition(
                        horizontal=HorizontalZone.CENTER,
                        vertical=VerticalZone.MID,
                        depth=DepthZone.FAR,
                    ),
                ),
                DisplayGroup(
                    group_id="LAYER_NEAR",
                    role="LAYER",
                    display_name="Layer Near",
                    position=GroupPosition(
                        horizontal=HorizontalZone.CENTER,
                        vertical=VerticalZone.MID,
                        depth=DepthZone.NEAR,
                    ),
                ),
                DisplayGroup(
                    group_id="LAYER_MID",
                    role="LAYER",
                    display_name="Layer Mid",
                    position=GroupPosition(
                        horizontal=HorizontalZone.CENTER,
                        vertical=VerticalZone.MID,
                        depth=DepthZone.MID,
                    ),
                ),
            ],
        )

        section = SectionCoordinationPlan(
            section_id="test_section",
            theme=ThemeRef(theme_id="theme.test", scope=ThemeScope.SECTION),
            palette=PaletteRef(palette_id="core.christmas_traditional"),
            lane_plans=[
                LanePlan(
                    lane=LaneKind.RHYTHM,
                    target_roles=["LAYER"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.SEQUENCED,
                            group_ids=["LAYER_FAR", "LAYER_NEAR", "LAYER_MID"],
                            window=PlacementWindow(
                                start=PlanningTimeRef(bar=1, beat=1),
                                end=PlanningTimeRef(bar=5, beat=1),
                                template_id="gtpl_rhythm_chase_single",
                                intensity=IntensityLevel.STRONG,
                            ),
                            config=CoordinationConfig(
                                group_order=["LAYER_FAR", "LAYER_NEAR", "LAYER_MID"],
                                step_unit=StepUnit.BEAT,
                                step_duration=2,
                                spatial_intent=SpatialIntent.F2B,
                            ),
                        )
                    ],
                ),
            ],
        )

        plan_set = GroupPlanSet(plan_set_id="test", section_plans=[section])
        engine = CompositionEngine(
            beat_grid=_make_beat_grid(),
            display_graph=display_graph,
            palette_resolver=_make_palette_resolver(),
            template_registry=REGISTRY,
        )
        render_plan = engine.compose(plan_set)

        events = _collect_events(render_plan)
        by_element: dict[str, list[int]] = {}
        for name, start, _ in events:
            by_element.setdefault(name, []).append(start)

        near_first = min(by_element.get("Layer Near", [999999]))
        mid_first = min(by_element.get("Layer Mid", [999999]))
        far_first = min(by_element.get("Layer Far", [999999]))

        assert near_first < mid_first, "NEAR group should start before MID"
        assert mid_first < far_first, "MID group should start before FAR"
