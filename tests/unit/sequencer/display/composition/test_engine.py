"""Unit tests for the CompositionEngine."""

from __future__ import annotations

from typing import Any

from twinklr.core.sequencer.display.composition.engine import (
    CompositionEngine,
)
from twinklr.core.sequencer.display.composition.palette_resolver import (
    PaletteResolver,
)
from twinklr.core.sequencer.display.models.palette import (
    ResolvedPalette,
    TransitionSpec,
)
from twinklr.core.sequencer.display.xlights_mapping import (
    XLightsGroupMapping,
    XLightsMapping,
)
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
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationPlan,
    GroupPlacement,
    PlanTarget,
)
from twinklr.core.sequencer.theming import PALETTE_REGISTRY, ThemeRef
from twinklr.core.sequencer.theming.enums import ThemeScope
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    EffectDuration,
    IntensityLevel,
    LaneKind,
    PlanningTimeRef,
)
from twinklr.core.sequencer.vocabulary.choreography import TargetType

# Ensure builtins are loaded once for all tests in this module
load_builtin_group_templates()


def _make_beat_grid() -> BeatGrid:
    """Create a 120 BPM, 4/4, 16-bar beat grid."""
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


def _make_choreo_graph() -> ChoreographyGraph:
    """Create a simple choreography graph with 3 groups."""
    return ChoreographyGraph(
        graph_id="test_display",
        groups=[
            ChoreoGroup(id="OUTLINE_1", role="OUTLINE"),
            ChoreoGroup(id="ARCHES_1", role="ARCHES"),
            ChoreoGroup(id="MEGA_TREE_1", role="MEGA_TREE"),
        ],
    )


def _make_xlights_mapping() -> XLightsMapping:
    """Map choreo group IDs to xLights element names."""
    return XLightsMapping(
        entries=[
            XLightsGroupMapping(choreo_id="OUTLINE_1", group_name="Outline 1"),
            XLightsGroupMapping(choreo_id="ARCHES_1", group_name="Arches 1"),
            XLightsGroupMapping(choreo_id="MEGA_TREE_1", group_name="Mega Tree 1"),
        ],
    )


def _make_palette_resolver() -> PaletteResolver:
    """Create a palette resolver backed by the global registry."""
    return PaletteResolver(
        catalog=PALETTE_REGISTRY,
        default=ResolvedPalette(colors=["#FF0000", "#00FF00"], active_slots=[1, 2]),
    )


def _make_engine(**kwargs: Any) -> CompositionEngine:
    """Create a CompositionEngine with sensible defaults.

    Accepts the same kwargs as ``CompositionEngine.__init__``.
    Always includes the builtin template registry.
    """
    defaults: dict[str, Any] = {
        "beat_grid": _make_beat_grid(),
        "choreo_graph": _make_choreo_graph(),
        "palette_resolver": _make_palette_resolver(),
        "template_registry": REGISTRY,
        "xlights_mapping": _make_xlights_mapping(),
    }
    defaults.update(kwargs)
    return CompositionEngine(**defaults)


def _make_plan_set(
    placements: list[GroupPlacement] | None = None,
    lane: LaneKind = LaneKind.BASE,
) -> GroupPlanSet:
    """Create a minimal GroupPlanSet for testing."""
    if placements is None:
        placements = [
            GroupPlacement(
                placement_id="p1",
                target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
                template_id="gtpl_base_wash_soft",
                start=PlanningTimeRef(bar=1, beat=1),
                duration=EffectDuration.PHRASE,
                intensity=IntensityLevel.MED,
            ),
        ]

    section = SectionCoordinationPlan(
        section_id="intro",
        theme=ThemeRef(theme_id="theme.holiday.traditional", scope=ThemeScope.SECTION),
        palette=PaletteRef(palette_id="core.christmas_traditional"),
        lane_plans=[
            LanePlan(
                lane=lane,
                target_roles=["OUTLINE"],
                coordination_plans=[
                    CoordinationPlan(
                        coordination_mode=CoordinationMode.UNIFIED,
                        targets=[PlanTarget(type=TargetType.GROUP, id="OUTLINE_1")],
                        placements=placements,
                    )
                ],
            )
        ],
    )

    return GroupPlanSet(
        plan_set_id="test_plan",
        section_plans=[section],
    )


class TestCompositionEngine:
    """Tests for the CompositionEngine."""

    def test_basic_composition(self) -> None:
        """Single placement produces one event on one element."""
        engine = _make_engine()
        plan_set = _make_plan_set()
        render_plan = engine.compose(plan_set)

        assert len(render_plan.groups) == 1
        assert render_plan.groups[0].element_name == "Outline 1"
        assert render_plan.total_events == 1

    def test_effect_type_resolved(self) -> None:
        """Template ID is resolved to xLights effect type."""
        engine = _make_engine()
        plan_set = _make_plan_set()
        render_plan = engine.compose(plan_set)

        event = render_plan.groups[0].layers[0].events[0]
        # gtpl_base_wash_soft → "Color Wash" via keyword heuristic
        assert event.effect_type == "Color Wash"

    def test_timing_resolved(self) -> None:
        """PlanningTimeRef is resolved to milliseconds."""
        engine = _make_engine()
        plan_set = _make_plan_set()
        render_plan = engine.compose(plan_set)

        event = render_plan.groups[0].layers[0].events[0]
        assert event.start_ms == 0  # bar=1, beat=1
        assert event.end_ms > 0

    def test_intensity_resolved(self) -> None:
        """IntensityLevel is resolved to a float."""
        engine = _make_engine()
        plan_set = _make_plan_set()
        render_plan = engine.compose(plan_set)

        event = render_plan.groups[0].layers[0].events[0]
        # MED intensity for BASE lane
        assert 0.0 < event.intensity < 1.0

    def test_multi_lane_layout(self) -> None:
        """BASE and RHYTHM placements go to different layers."""
        base_placement = GroupPlacement(
            placement_id="p_base",
            target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
            template_id="gtpl_base_wash_soft",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.SECTION,
        )
        rhythm_placement = GroupPlacement(
            placement_id="p_rhythm",
            target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
            template_id="gtpl_rhythm_chase_single",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.SECTION,
        )

        section = SectionCoordinationPlan(
            section_id="intro",
            theme=ThemeRef(theme_id="theme.holiday.traditional", scope=ThemeScope.SECTION),
            palette=PaletteRef(palette_id="core.christmas_traditional"),
            lane_plans=[
                LanePlan(
                    lane=LaneKind.BASE,
                    target_roles=["OUTLINE"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.UNIFIED,
                            targets=[PlanTarget(type=TargetType.GROUP, id="OUTLINE_1")],
                            placements=[base_placement],
                        )
                    ],
                ),
                LanePlan(
                    lane=LaneKind.RHYTHM,
                    target_roles=["OUTLINE"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.UNIFIED,
                            targets=[PlanTarget(type=TargetType.GROUP, id="OUTLINE_1")],
                            placements=[rhythm_placement],
                        )
                    ],
                ),
            ],
        )

        plan_set = GroupPlanSet(
            plan_set_id="test",
            section_plans=[section],
        )

        engine = _make_engine()
        render_plan = engine.compose(plan_set)

        # Should have 1 element with layers from both BASE (0-5) and
        # RHYTHM (6-11) lane ranges.
        assert len(render_plan.groups) == 1
        layer_indices = {ly.layer_index for ly in render_plan.groups[0].layers}
        # At least one layer in BASE range and one in RHYTHM range
        base_layers = {i for i in layer_indices if 0 <= i <= 5}
        rhythm_layers = {i for i in layer_indices if 6 <= i <= 11}
        assert len(base_layers) >= 1, f"Expected BASE layers in 0-5, got {layer_indices}"
        assert len(rhythm_layers) >= 1, f"Expected RHYTHM layers in 6-11, got {layer_indices}"

    def test_overlap_trim(self) -> None:
        """Overlapping events in same layer are trimmed."""
        p1 = GroupPlacement(
            placement_id="p1",
            target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
            template_id="gtpl_base_wash_soft",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.PHRASE,  # ~8000ms
        )
        p2 = GroupPlacement(
            placement_id="p2",
            target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
            template_id="gtpl_base_wash_split",
            start=PlanningTimeRef(bar=3, beat=1),  # 4000ms
            duration=EffectDuration.PHRASE,
        )

        plan_set = _make_plan_set(placements=[p1, p2])

        engine = _make_engine()
        render_plan = engine.compose(plan_set)

        events = render_plan.groups[0].layers[0].events
        assert len(events) == 2
        # First event should be trimmed: its end should not exceed second's start
        assert events[0].end_ms <= events[1].start_ms

    def test_palette_resolved(self) -> None:
        """Section palette reference is resolved to colors."""
        engine = _make_engine()
        plan_set = _make_plan_set()
        render_plan = engine.compose(plan_set)

        event = render_plan.groups[0].layers[0].events[0]
        # core.christmas_traditional palette from the catalog
        assert "#E53935" in event.palette.colors  # christmas_red
        assert "#43A047" in event.palette.colors  # christmas_green

    def test_source_traceability(self) -> None:
        """RenderEvent has source traceability."""
        engine = _make_engine()
        plan_set = _make_plan_set()
        render_plan = engine.compose(plan_set)

        event = render_plan.groups[0].layers[0].events[0]
        assert event.source.section_id == "intro"
        assert event.source.lane == LaneKind.BASE
        assert event.source.template_id == "gtpl_base_wash_soft"

    def test_diagnostics_on_zero_duration(self) -> None:
        """Zero-duration placements produce a diagnostic."""
        # Place at the very end of the sequence
        p = GroupPlacement(
            placement_id="p_end",
            target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
            template_id="gtpl_accent_hit_white",
            start=PlanningTimeRef(bar=16, beat=4),
            duration=EffectDuration.PHRASE,  # extends past sequence end
        )
        plan_set = _make_plan_set(placements=[p], lane=LaneKind.ACCENT)
        engine = _make_engine()
        render_plan = engine.compose(plan_set)

        # The placement should either produce an event clamped to
        # sequence end, or produce a diagnostic if zero-duration
        total = render_plan.total_events + len(render_plan.diagnostics)
        assert total >= 1  # Something was produced


class TestSectionBoundaryClamping:
    """Tests for section boundary clamping via start_ms/end_ms."""

    def test_effect_clamped_to_section_end(self) -> None:
        """An effect extending past section_end_ms should be clamped."""
        # Section ends at bar 4 (4000ms at 120 BPM, 4/4)
        section_end_ms = 4000

        # Place a PHRASE effect (16 beats = 8000ms) starting at bar 1
        # Without clamping it would end at 8000ms; with clamping → 4000ms
        p = GroupPlacement(
            placement_id="p1",
            target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
            template_id="gtpl_base_wash_soft",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.PHRASE,
            intensity=IntensityLevel.MED,
        )

        section = SectionCoordinationPlan(
            section_id="test_section",
            theme=ThemeRef(theme_id="theme.holiday.traditional", scope=ThemeScope.SECTION),
            palette=PaletteRef(palette_id="core.christmas_traditional"),
            start_ms=0,
            end_ms=section_end_ms,
            lane_plans=[
                LanePlan(
                    lane=LaneKind.BASE,
                    target_roles=["OUTLINE"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.UNIFIED,
                            targets=[PlanTarget(type=TargetType.GROUP, id="OUTLINE_1")],
                            placements=[p],
                        )
                    ],
                )
            ],
        )

        plan_set = GroupPlanSet(
            plan_set_id="test_clamp",
            section_plans=[section],
        )

        engine = _make_engine()
        render_plan = engine.compose(plan_set)

        assert render_plan.total_events == 1
        event = render_plan.groups[0].layers[0].events[0]
        # Effect should be clamped to section end (snapped to 20ms grid)
        assert event.end_ms <= section_end_ms

    def test_section_duration_fills_to_section_end(self) -> None:
        """SECTION duration should use section_end_ms, not sequence end."""
        section_end_ms = 6000

        p = GroupPlacement(
            placement_id="p1",
            target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
            template_id="gtpl_base_wash_soft",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.SECTION,
            intensity=IntensityLevel.MED,
        )

        section = SectionCoordinationPlan(
            section_id="test_section",
            theme=ThemeRef(theme_id="theme.holiday.traditional", scope=ThemeScope.SECTION),
            palette=PaletteRef(palette_id="core.christmas_traditional"),
            start_ms=0,
            end_ms=section_end_ms,
            lane_plans=[
                LanePlan(
                    lane=LaneKind.BASE,
                    target_roles=["OUTLINE"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.UNIFIED,
                            targets=[PlanTarget(type=TargetType.GROUP, id="OUTLINE_1")],
                            placements=[p],
                        )
                    ],
                )
            ],
        )

        plan_set = GroupPlanSet(
            plan_set_id="test_section_dur",
            section_plans=[section],
        )

        engine = _make_engine()
        render_plan = engine.compose(plan_set)

        assert render_plan.total_events == 1
        event = render_plan.groups[0].layers[0].events[0]
        # SECTION duration should use section_end_ms (snapped to 20ms)
        assert event.end_ms == 6000

    def test_no_section_timing_uses_sequence_end(self) -> None:
        """Without section timing, SECTION duration uses full sequence."""
        # This is the backward-compatible behavior
        plan_set = _make_plan_set(
            placements=[
                GroupPlacement(
                    placement_id="p1",
                    target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
                    template_id="gtpl_base_wash_soft",
                    start=PlanningTimeRef(bar=1, beat=1),
                    duration=EffectDuration.SECTION,
                    intensity=IntensityLevel.MED,
                ),
            ]
        )
        # plan_set sections have no start_ms/end_ms (defaults to None)

        engine = _make_engine()
        render_plan = engine.compose(plan_set)

        assert render_plan.total_events == 1
        event = render_plan.groups[0].layers[0].events[0]
        # Should fill to sequence end (16 bars at 120 BPM = 32000ms)
        assert event.end_ms == 32000


class TestTransitionPolicy:
    """Tests for per-lane fade-in / fade-out transition assignment."""

    def test_base_lane_has_long_fade(self) -> None:
        """BASE lane effects should have 1.0s fade-in and fade-out."""
        engine = _make_engine()
        plan_set = _make_plan_set(lane=LaneKind.BASE)
        render_plan = engine.compose(plan_set)

        event = render_plan.groups[0].layers[0].events[0]
        assert event.transition_in is not None
        assert event.transition_in.type == "Fade"
        assert event.transition_in.duration_ms == 1000
        assert event.transition_out is not None
        assert event.transition_out.type == "Fade"
        assert event.transition_out.duration_ms == 1000

    def test_rhythm_lane_has_short_fade(self) -> None:
        """RHYTHM lane effects should have 0.3s fade-in and fade-out."""
        engine = _make_engine()
        plan_set = _make_plan_set(lane=LaneKind.RHYTHM)
        render_plan = engine.compose(plan_set)

        event = render_plan.groups[0].layers[0].events[0]
        assert event.transition_in is not None
        assert event.transition_in.duration_ms == 300
        assert event.transition_out is not None
        assert event.transition_out.duration_ms == 300

    def test_accent_lane_no_fade_in(self) -> None:
        """ACCENT lane effects should have no fade-in (punchy entrance)."""
        engine = _make_engine()
        plan_set = _make_plan_set(lane=LaneKind.ACCENT)
        render_plan = engine.compose(plan_set)

        event = render_plan.groups[0].layers[0].events[0]
        assert event.transition_in is None

    def test_accent_lane_has_short_fade_out(self) -> None:
        """ACCENT lane effects should have 0.2s fade-out."""
        engine = _make_engine()
        plan_set = _make_plan_set(lane=LaneKind.ACCENT)
        render_plan = engine.compose(plan_set)

        event = render_plan.groups[0].layers[0].events[0]
        assert event.transition_out is not None
        assert event.transition_out.type == "Fade"
        assert event.transition_out.duration_ms == 200

    def test_resolve_transitions_static(self) -> None:
        """_resolve_transitions returns correct TransitionSpec objects."""
        t_in, t_out = CompositionEngine._resolve_transitions(LaneKind.BASE)
        assert isinstance(t_in, TransitionSpec)
        assert isinstance(t_out, TransitionSpec)
        assert t_in.duration_ms == 1000
        assert t_out.duration_ms == 1000

        t_in, t_out = CompositionEngine._resolve_transitions(LaneKind.ACCENT)
        assert t_in is None
        assert t_out is not None
        assert t_out.duration_ms == 200


class TestBlendModeAssignment:
    """Tests for blend mode assignment on RenderLayerPlan."""

    def test_base_layer_blend_mode_normal(self) -> None:
        """BASE layer should have 'Normal' blend mode."""
        engine = _make_engine()
        plan_set = _make_plan_set(lane=LaneKind.BASE)
        render_plan = engine.compose(plan_set)

        layer = render_plan.groups[0].layers[0]
        assert layer.blend_mode == "Normal"

    def test_multi_lane_blend_modes(self) -> None:
        """Multiple lanes get correct blend modes from the allocator."""
        base_p = GroupPlacement(
            placement_id="p_base",
            target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
            template_id="gtpl_base_wash_soft",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.SECTION,
            intensity=IntensityLevel.MED,
        )
        accent_p = GroupPlacement(
            placement_id="p_accent",
            target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
            template_id="gtpl_accent_hit_color",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.HIT,
            intensity=IntensityLevel.PEAK,
        )

        section = SectionCoordinationPlan(
            section_id="multi_lane",
            theme=ThemeRef(
                theme_id="theme.holiday.traditional",
                scope=ThemeScope.SECTION,
            ),
            palette=PaletteRef(palette_id="core.christmas_traditional"),
            lane_plans=[
                LanePlan(
                    lane=LaneKind.BASE,
                    target_roles=["OUTLINE"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.UNIFIED,
                            targets=[PlanTarget(type=TargetType.GROUP, id="OUTLINE_1")],
                            placements=[base_p],
                        )
                    ],
                ),
                LanePlan(
                    lane=LaneKind.ACCENT,
                    target_roles=["OUTLINE"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.UNIFIED,
                            targets=[PlanTarget(type=TargetType.GROUP, id="OUTLINE_1")],
                            placements=[accent_p],
                        )
                    ],
                ),
            ],
        )

        plan_set = GroupPlanSet(
            plan_set_id="blend_test",
            section_plans=[section],
        )

        engine = _make_engine()
        render_plan = engine.compose(plan_set)

        # Should have layers from both BASE (0-5) and ACCENT (12-17) ranges
        group = render_plan.groups[0]
        layer_indices = {ly.layer_index for ly in group.layers}
        base_layers = {i for i in layer_indices if 0 <= i <= 5}
        accent_layers = {i for i in layer_indices if 12 <= i <= 17}
        assert len(base_layers) >= 1, f"Expected BASE layers, got {layer_indices}"
        assert len(accent_layers) >= 1, f"Expected ACCENT layers, got {layer_indices}"
        # All layers have their blend mode set
        for layer in group.layers:
            assert isinstance(layer.blend_mode, str)
            assert len(layer.blend_mode) > 0


# ---------------------------------------------------------------------------
# Catalog-backed helpers for overlay tests
# ---------------------------------------------------------------------------


def _make_fake_catalog_entry(asset_id: str, file_path: str) -> object:
    """Create a minimal object that quacks like CatalogEntry for overlay tests."""

    class _FakeCatalogEntry:
        def __init__(self, aid: str, fp: str) -> None:
            self.asset_id = aid
            self.file_path = fp

    return _FakeCatalogEntry(asset_id, file_path)


class TestAssetOverlayRendering:
    """Tests for dual-layer asset overlay event emission."""

    def test_no_overlay_without_catalog(self) -> None:
        """Without a catalog_index, no overlay events are emitted."""
        placement = GroupPlacement(
            placement_id="p_asset",
            target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
            template_id="gtpl_base_wash_soft",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.PHRASE,
            resolved_asset_ids=["asset_abc"],
        )
        plan_set = _make_plan_set(placements=[placement])
        engine = _make_engine()
        render_plan = engine.compose(plan_set)

        # Only the procedural event, no overlay layer
        assert render_plan.total_events == 1
        assert len(render_plan.groups[0].layers) == 1

    def test_no_overlay_without_resolved_ids(self) -> None:
        """Placements without resolved_asset_ids produce no overlays."""
        plan_set = _make_plan_set()  # default placement has no assets
        catalog_index = {"x": _make_fake_catalog_entry("x", "x.png")}
        engine = _make_engine(catalog_index=catalog_index)
        render_plan = engine.compose(plan_set)

        assert render_plan.total_events == 1
        assert len(render_plan.groups[0].layers) == 1

    def test_overlay_emitted_with_catalog_and_ids(self) -> None:
        """Placement with resolved_asset_ids + catalog produces overlay events."""
        entry = _make_fake_catalog_entry("asset_001", "images/snowflake.png")
        catalog_index = {"asset_001": entry}

        placement = GroupPlacement(
            placement_id="p_asset",
            target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
            template_id="gtpl_base_wash_soft",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.PHRASE,
            resolved_asset_ids=["asset_001"],
        )
        plan_set = _make_plan_set(placements=[placement])
        engine = _make_engine(catalog_index=catalog_index)
        render_plan = engine.compose(plan_set)

        # 2 events: procedural + overlay
        assert render_plan.total_events == 2
        # 2 layers: procedural (0) and overlay (5 = BASE overlay)
        assert len(render_plan.groups[0].layers) == 2

        layer_indices = {ly.layer_index for ly in render_plan.groups[0].layers}
        assert 0 in layer_indices
        assert 5 in layer_indices  # BASE overlay in new sub-layer scheme

        # Find the overlay layer (layer index 5 = BASE overlay)
        overlay_layer = next(ly for ly in render_plan.groups[0].layers if ly.layer_index == 5)
        assert len(overlay_layer.events) == 1
        assert overlay_layer.events[0].effect_type == "Pictures"
        assert overlay_layer.events[0].parameters["filename"] == "images/snowflake.png"

    def test_overlay_timing_matches_procedural(self) -> None:
        """Overlay events share start/end with the procedural event."""
        entry = _make_fake_catalog_entry("asset_002", "images/star.png")
        catalog_index = {"asset_002": entry}

        placement = GroupPlacement(
            placement_id="p_timing",
            target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
            template_id="gtpl_base_wash_soft",
            start=PlanningTimeRef(bar=3, beat=1),
            duration=EffectDuration.PHRASE,
            resolved_asset_ids=["asset_002"],
        )
        plan_set = _make_plan_set(placements=[placement])
        engine = _make_engine(catalog_index=catalog_index)
        render_plan = engine.compose(plan_set)

        procedural = render_plan.groups[0].layers[0].events[0]
        overlay = next(ly for ly in render_plan.groups[0].layers if ly.layer_index == 5).events[0]

        assert overlay.start_ms == procedural.start_ms
        assert overlay.end_ms == procedural.end_ms

    def test_multiple_assets_uses_first_valid(self) -> None:
        """Multiple resolved_asset_ids uses the first valid entry (best match)."""
        entries = {
            "a1": _make_fake_catalog_entry("a1", "img/tree.png"),
            "a2": _make_fake_catalog_entry("a2", "img/present.png"),
        }

        placement = GroupPlacement(
            placement_id="p_multi",
            target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
            template_id="gtpl_base_wash_soft",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.PHRASE,
            resolved_asset_ids=["a1", "a2"],
        )
        plan_set = _make_plan_set(placements=[placement])
        engine = _make_engine(catalog_index=entries)
        render_plan = engine.compose(plan_set)

        # 2 events: 1 procedural + 1 overlay (first valid match)
        assert render_plan.total_events == 2
        overlay_layer = next(ly for ly in render_plan.groups[0].layers if ly.layer_index == 5)
        assert len(overlay_layer.events) == 1
        assert overlay_layer.events[0].parameters["filename"] == "img/tree.png"

    def test_missing_asset_falls_through_to_next(self) -> None:
        """Missing first asset falls through to the next valid one."""
        catalog_index = {
            "exists": _make_fake_catalog_entry("exists", "img/ok.png"),
        }

        placement = GroupPlacement(
            placement_id="p_skip",
            target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
            template_id="gtpl_base_wash_soft",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.PHRASE,
            resolved_asset_ids=["missing", "exists"],
        )
        plan_set = _make_plan_set(placements=[placement])
        engine = _make_engine(catalog_index=catalog_index)
        render_plan = engine.compose(plan_set)

        # 2 events: 1 procedural + 1 overlay (skipped missing, used exists)
        assert render_plan.total_events == 2
        overlay_layer = next(ly for ly in render_plan.groups[0].layers if ly.layer_index == 5)
        assert overlay_layer.events[0].parameters["filename"] == "img/ok.png"

    def test_all_assets_missing_no_overlay(self) -> None:
        """When all resolved_asset_ids are missing from catalog, no overlay."""
        catalog_index: dict[str, object] = {}

        placement = GroupPlacement(
            placement_id="p_all_missing",
            target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
            template_id="gtpl_base_wash_soft",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.PHRASE,
            resolved_asset_ids=["ghost_1", "ghost_2"],
        )
        plan_set = _make_plan_set(placements=[placement])
        engine = _make_engine(catalog_index=catalog_index)
        render_plan = engine.compose(plan_set)

        # Only the procedural event, no overlay
        assert render_plan.total_events == 1
        assert len(render_plan.groups[0].layers) == 1

    def test_overlay_source_traceability(self) -> None:
        """Overlay events carry the same source traceability as the procedural event."""
        entry = _make_fake_catalog_entry("trace_id", "img/trace.png")
        catalog_index = {"trace_id": entry}

        placement = GroupPlacement(
            placement_id="p_trace",
            target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
            template_id="gtpl_base_wash_soft",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.PHRASE,
            resolved_asset_ids=["trace_id"],
        )
        plan_set = _make_plan_set(placements=[placement])
        engine = _make_engine(catalog_index=catalog_index)
        render_plan = engine.compose(plan_set)

        overlay_event = next(
            ly for ly in render_plan.groups[0].layers if ly.layer_index == 5
        ).events[0]
        assert overlay_event.source.section_id == "intro"
        assert overlay_event.source.lane == LaneKind.BASE
        assert overlay_event.source.template_id == "gtpl_base_wash_soft"

    def test_rhythm_lane_overlay_on_correct_layer(self) -> None:
        """RHYTHM lane overlays go to layer 11 (RHYTHM overlay in sub-layer scheme)."""
        entry = _make_fake_catalog_entry("rhythm_asset", "img/pulse.png")
        catalog_index = {"rhythm_asset": entry}

        placement = GroupPlacement(
            placement_id="p_rhythm_overlay",
            target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
            template_id="gtpl_rhythm_chase_single",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.PHRASE,
            resolved_asset_ids=["rhythm_asset"],
        )
        plan_set = _make_plan_set(placements=[placement], lane=LaneKind.RHYTHM)
        engine = _make_engine(catalog_index=catalog_index)
        render_plan = engine.compose(plan_set)

        layer_indices = {ly.layer_index for ly in render_plan.groups[0].layers}
        # RHYTHM sub-layers are in range 6-10; overlay is at 11
        rhythm_sub = {i for i in layer_indices if 6 <= i <= 10}
        assert len(rhythm_sub) >= 1, f"Expected RHYTHM sub-layers, got {layer_indices}"
        assert 11 in layer_indices  # RHYTHM overlay in sub-layer scheme
