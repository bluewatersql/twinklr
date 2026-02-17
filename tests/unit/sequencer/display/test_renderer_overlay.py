"""Tests for DisplayRenderer asset overlay wiring.

Validates that catalog_index flows through DisplayRenderer.render()
to the CompositionEngine and produces Pictures overlay events.
"""

from __future__ import annotations

from twinklr.core.agents.assets.models import (
    AssetCatalog,
    AssetCategory,
    AssetSpec,
    AssetStatus,
    CatalogEntry,
)
from twinklr.core.formats.xlights.sequence.models.xsq import (
    SequenceHead,
    XSequence,
)
from twinklr.core.sequencer.display.renderer import DisplayRenderer
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
from twinklr.core.sequencer.theming import ThemeRef
from twinklr.core.sequencer.theming.enums import ThemeScope
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.vocabulary import (
    BackgroundMode,
    CoordinationMode,
    EffectDuration,
    IntensityLevel,
    LaneKind,
    PlanningTimeRef,
)
from twinklr.core.sequencer.vocabulary.choreography import TargetType

# Ensure builtins are loaded once for all tests in this module
load_builtin_group_templates()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_beat_grid() -> BeatGrid:
    """120 BPM, 4/4, 16-bar beat grid."""
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
    return ChoreographyGraph(
        graph_id="test",
        groups=[ChoreoGroup(id="OUTLINE_1", role="OUTLINE")],
    )


def _make_xlights_mapping() -> XLightsMapping:
    return XLightsMapping(
        entries=[XLightsGroupMapping(choreo_id="OUTLINE_1", group_name="Outline 1")],
    )


def _make_sequence() -> XSequence:
    return XSequence(
        head=SequenceHead(
            version="2024.01",
            author="test",
            song="test",
            sequence_timing="20 ms",
            media_file="",
            sequence_duration_ms=32000,
        ),
    )


def _make_spec(motif_id: str = "sparkles") -> AssetSpec:
    return AssetSpec(
        spec_id=f"asset_{motif_id}",
        category=AssetCategory.IMAGE_TEXTURE,
        motif_id=motif_id,
        theme_id="theme.holiday.traditional",
        section_ids=["intro"],
        target_roles=["OUTLINE"],
        background=BackgroundMode.OPAQUE,
    )


def _make_catalog_entry(asset_id: str, file_path: str) -> CatalogEntry:
    return CatalogEntry(
        asset_id=asset_id,
        spec=_make_spec(),
        file_path=file_path,
        content_hash="sha256_test",
        status=AssetStatus.CREATED,
        width=1024,
        height=1024,
        has_alpha=False,
        file_size_bytes=2048,
        created_at="2026-02-13T12:00:00Z",
        source_plan_id="plan_test",
        generation_model="gpt-image-1.5",
        prompt_hash="hash_test",
    )


def _make_plan_set(
    resolved_asset_ids: list[str] | None = None,
) -> GroupPlanSet:
    placement = GroupPlacement(
        placement_id="p1",
        target=PlanTarget(type=TargetType.GROUP, id="OUTLINE_1"),
        template_id="gtpl_base_wash_soft",
        start=PlanningTimeRef(bar=1, beat=1),
        duration=EffectDuration.PHRASE,
        intensity=IntensityLevel.MED,
        resolved_asset_ids=resolved_asset_ids or [],
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
                        placements=[placement],
                    )
                ],
            )
        ],
    )
    return GroupPlanSet(plan_set_id="test", section_plans=[section])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDisplayRendererOverlayWiring:
    """Verify catalog_index flows through to overlay event emission."""

    def test_render_without_catalog_no_overlays(self) -> None:
        """Default render (no catalog) produces only procedural events."""
        renderer = DisplayRenderer(
            beat_grid=_make_beat_grid(),
            choreo_graph=_make_choreo_graph(),
            template_registry=REGISTRY,
            xlights_mapping=_make_xlights_mapping(),
        )
        plan_set = _make_plan_set(resolved_asset_ids=["asset_sparkles"])
        result = renderer.render(plan_set, _make_sequence())

        # No catalog → no overlays, just procedural
        assert result.render_plan.total_events == 1

    def test_render_with_catalog_index_emits_overlay(self) -> None:
        """Passing catalog_index produces a Pictures overlay event."""
        entry = _make_catalog_entry("asset_sparkles", "images/sparkles.png")
        catalog_index: dict[str, object] = {"asset_sparkles": entry}

        renderer = DisplayRenderer(
            beat_grid=_make_beat_grid(),
            choreo_graph=_make_choreo_graph(),
            template_registry=REGISTRY,
            xlights_mapping=_make_xlights_mapping(),
        )
        plan_set = _make_plan_set(resolved_asset_ids=["asset_sparkles"])
        result = renderer.render(plan_set, _make_sequence(), catalog_index=catalog_index)

        # 2 events: procedural + overlay
        assert result.render_plan.total_events == 2
        group = result.render_plan.groups[0]
        assert len(group.layers) == 2

        overlay_layer = next(ly for ly in group.layers if ly.layer_index == 5)
        assert overlay_layer.events[0].effect_type == "Pictures"

    def test_build_index_integration(self) -> None:
        """AssetCatalog.build_index() output works with DisplayRenderer."""
        entry = _make_catalog_entry("asset_sparkles", "images/sparkles.png")
        catalog = AssetCatalog(
            catalog_id="test_catalog",
            entries=[entry],
        )
        catalog_index = catalog.build_index()

        renderer = DisplayRenderer(
            beat_grid=_make_beat_grid(),
            choreo_graph=_make_choreo_graph(),
            template_registry=REGISTRY,
            xlights_mapping=_make_xlights_mapping(),
        )
        plan_set = _make_plan_set(resolved_asset_ids=["asset_sparkles"])
        result = renderer.render(plan_set, _make_sequence(), catalog_index=catalog_index)

        assert result.render_plan.total_events == 2
        overlay_layer = next(
            ly for ly in result.render_plan.groups[0].layers if ly.layer_index == 5
        )
        assert overlay_layer.events[0].parameters["filename"] == "images/sparkles.png"
