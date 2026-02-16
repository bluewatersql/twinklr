"""Tests for display rendering pipeline stages."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

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
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.pipeline.display_stages import (
    AssetResolutionStage,
    DisplayRenderStage,
)
from twinklr.core.sequencer.planning.group_plan import (
    GroupPlanSet,
    LanePlan,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.planning.models import PaletteRef
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationPlan,
    GroupPlacement,
)
from twinklr.core.sequencer.templates.group.models.display import (
    DisplayGraph,
    DisplayGroup,
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_beat_grid() -> BeatGrid:
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


def _make_display_graph() -> DisplayGraph:
    return DisplayGraph(
        display_id="test",
        display_name="Test",
        groups=[
            DisplayGroup(
                group_id="MEGA_TREE_1",
                role="MEGA_TREE",
                display_name="Mega Tree 1",
            ),
        ],
    )


def _make_plan_set(
    template_id: str = "gtpl_base_wash_soft",
    resolved_asset_ids: list[str] | None = None,
) -> GroupPlanSet:
    placement = GroupPlacement(
        placement_id="p1",
        group_id="MEGA_TREE_1",
        template_id=template_id,
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
                target_roles=["MEGA_TREE"],
                coordination_plans=[
                    CoordinationPlan(
                        coordination_mode=CoordinationMode.UNIFIED,
                        group_ids=["MEGA_TREE_1"],
                        placements=[placement],
                    )
                ],
            )
        ],
    )
    return GroupPlanSet(plan_set_id="test", section_plans=[section])


def _make_spec(motif_id: str = "sparkles") -> AssetSpec:
    return AssetSpec(
        spec_id=f"asset_{motif_id}",
        category=AssetCategory.IMAGE_TEXTURE,
        motif_id=motif_id,
        theme_id="theme.holiday.traditional",
        section_ids=["intro"],
        target_roles=["MEGA_TREE"],
        background=BackgroundMode.OPAQUE,
    )


def _make_catalog_entry(asset_id: str, file_path: str, motif_id: str = "sparkles") -> CatalogEntry:
    return CatalogEntry(
        asset_id=asset_id,
        spec=_make_spec(motif_id=motif_id),
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


def _make_catalog(entries: list[CatalogEntry] | None = None) -> AssetCatalog:
    return AssetCatalog(
        catalog_id="test_catalog",
        entries=entries or [],
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


def _make_context() -> PipelineContext:
    """Create a mock PipelineContext for stage testing."""
    mock_session = MagicMock()
    mock_session.app_config = MagicMock()
    mock_session.job_config = MagicMock()
    ctx = PipelineContext(session=mock_session)
    return ctx


# ---------------------------------------------------------------------------
# AssetResolutionStage tests
# ---------------------------------------------------------------------------


class TestAssetResolutionStage:
    """Tests for the AssetResolutionStage."""

    @pytest.mark.asyncio
    async def test_no_catalog_returns_original_plan(self) -> None:
        """No catalog → plan passes through unchanged."""
        stage = AssetResolutionStage()
        plan_set = _make_plan_set()
        context = _make_context()

        result = await stage.execute(
            {"plan_set": plan_set, "catalog": None},
            context,
        )

        assert result.success
        assert result.output is plan_set

    @pytest.mark.asyncio
    async def test_empty_catalog_returns_original_plan(self) -> None:
        """Empty catalog → plan passes through unchanged."""
        stage = AssetResolutionStage()
        plan_set = _make_plan_set()
        catalog = _make_catalog()
        context = _make_context()

        result = await stage.execute(
            {"plan_set": plan_set, "catalog": catalog},
            context,
        )

        assert result.success
        assert result.output is plan_set

    @pytest.mark.asyncio
    async def test_resolves_motif_placements(self) -> None:
        """Motif-based templates get resolved_asset_ids from catalog."""
        stage = AssetResolutionStage()
        # Template with motif pattern
        plan_set = _make_plan_set(template_id="gtpl_base_motif_sparkles_ambient")
        entry = _make_catalog_entry("asset_sparkles", "images/sparkles.png", motif_id="sparkles")
        catalog = _make_catalog(entries=[entry])
        context = _make_context()

        result = await stage.execute(
            {"plan_set": plan_set, "catalog": catalog},
            context,
        )

        assert result.success
        assert result.output is not None
        resolved_plan = result.output
        placement = resolved_plan.section_plans[0].lane_plans[0].coordination_plans[0].placements[0]
        assert len(placement.resolved_asset_ids) > 0

    @pytest.mark.asyncio
    async def test_tracks_metrics(self) -> None:
        """Resolved count is tracked in context metrics."""
        stage = AssetResolutionStage()
        plan_set = _make_plan_set(template_id="gtpl_base_motif_sparkles_ambient")
        entry = _make_catalog_entry("asset_sparkles", "images/sparkles.png", motif_id="sparkles")
        catalog = _make_catalog(entries=[entry])
        context = _make_context()

        await stage.execute(
            {"plan_set": plan_set, "catalog": catalog},
            context,
        )

        assert "assets_resolved" in context.metrics

    @pytest.mark.asyncio
    async def test_name_property(self) -> None:
        """Stage has correct name."""
        assert AssetResolutionStage().name == "asset_resolution"


# ---------------------------------------------------------------------------
# DisplayRenderStage tests
# ---------------------------------------------------------------------------


class TestDisplayRenderStage:
    """Tests for the DisplayRenderStage."""

    @pytest.mark.asyncio
    async def test_basic_render(self) -> None:
        """Renders plan to sequence with effects."""
        stage = DisplayRenderStage()
        plan_set = _make_plan_set()
        context = _make_context()

        result = await stage.execute(
            {
                "plan_set": plan_set,
                "beat_grid": _make_beat_grid(),
                "display_graph": _make_display_graph(),
            },
            context,
        )

        assert result.success
        assert result.output is not None
        output = result.output
        assert "sequence" in output
        assert "render_result" in output
        assert output["render_result"].effects_written > 0

    @pytest.mark.asyncio
    async def test_creates_sequence_if_not_provided(self) -> None:
        """Creates empty XSequence when none is provided."""
        stage = DisplayRenderStage()
        plan_set = _make_plan_set()
        context = _make_context()

        result = await stage.execute(
            {
                "plan_set": plan_set,
                "beat_grid": _make_beat_grid(),
                "display_graph": _make_display_graph(),
            },
            context,
        )

        assert result.success
        assert isinstance(result.output["sequence"], XSequence)

    @pytest.mark.asyncio
    async def test_uses_provided_sequence(self) -> None:
        """Uses existing XSequence when provided."""
        stage = DisplayRenderStage()
        plan_set = _make_plan_set()
        sequence = _make_sequence()
        context = _make_context()

        result = await stage.execute(
            {
                "plan_set": plan_set,
                "beat_grid": _make_beat_grid(),
                "display_graph": _make_display_graph(),
                "sequence": sequence,
            },
            context,
        )

        assert result.success
        assert result.output["sequence"] is sequence

    @pytest.mark.asyncio
    async def test_render_with_catalog_produces_overlays(self) -> None:
        """Catalog-backed render produces overlay events."""
        stage = DisplayRenderStage()
        entry = _make_catalog_entry("asset_sparkles", "images/sparkles.png")
        catalog = _make_catalog(entries=[entry])

        plan_set = _make_plan_set(resolved_asset_ids=["asset_sparkles"])
        context = _make_context()

        result = await stage.execute(
            {
                "plan_set": plan_set,
                "beat_grid": _make_beat_grid(),
                "display_graph": _make_display_graph(),
                "catalog": catalog,
            },
            context,
        )

        assert result.success
        render_result = result.output["render_result"]
        # 2 events: procedural + overlay
        assert render_result.render_plan.total_events == 2

    @pytest.mark.asyncio
    async def test_tracks_metrics(self) -> None:
        """Render metrics are tracked in context."""
        stage = DisplayRenderStage()
        plan_set = _make_plan_set()
        context = _make_context()

        await stage.execute(
            {
                "plan_set": plan_set,
                "beat_grid": _make_beat_grid(),
                "display_graph": _make_display_graph(),
            },
            context,
        )

        assert "effects_written" in context.metrics
        assert "elements_created" in context.metrics

    @pytest.mark.asyncio
    async def test_pipeline_mode_direct_plan_set(self) -> None:
        """Pipeline mode: accepts GroupPlanSet directly with deps in constructor."""
        stage = DisplayRenderStage(
            beat_grid=_make_beat_grid(),
            display_graph=_make_display_graph(),
        )
        plan_set = _make_plan_set()
        context = _make_context()

        # Pass GroupPlanSet directly (as pipeline executor would)
        result = await stage.execute(plan_set, context)

        assert result.success
        assert result.output["render_result"].effects_written > 0

    @pytest.mark.asyncio
    async def test_pipeline_mode_beat_grid_from_context_metrics(self) -> None:
        """Pipeline mode: builds BeatGrid from context metrics when not provided."""
        stage = DisplayRenderStage(display_graph=_make_display_graph())
        plan_set = _make_plan_set()
        context = _make_context()

        # Simulate what AudioAnalysisStage stores
        context.add_metric("audio_duration_ms", 32000)
        context.add_metric("tempo_bpm", 120.0)

        result = await stage.execute(plan_set, context)

        assert result.success
        assert result.output["render_result"].effects_written > 0

    @pytest.mark.asyncio
    async def test_pipeline_mode_beat_grid_uses_derived_beats_per_bar(self) -> None:
        """Pipeline mode: derived timing meter should flow into beat grid construction."""
        stage = DisplayRenderStage(display_graph=_make_display_graph())
        plan_set = _make_plan_set()
        context = _make_context()
        context.add_metric("audio_duration_ms", 32000)
        context.add_metric("tempo_bpm", 120.0)
        context.set_state("beats_per_bar", 3)

        result = await stage.execute(plan_set, context)

        assert result.success
        assert context.metrics.get("beat_grid_beats_per_bar") == 3

    @pytest.mark.asyncio
    async def test_pipeline_mode_beat_grid_warns_and_falls_back_to_4_4(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When derived timing is unavailable, a warning is emitted and 4/4 is used."""
        stage = DisplayRenderStage(display_graph=_make_display_graph())
        plan_set = _make_plan_set()
        context = _make_context()
        context.add_metric("audio_duration_ms", 32000)
        context.add_metric("tempo_bpm", 120.0)

        with caplog.at_level("WARNING"):
            result = await stage.execute(plan_set, context)

        assert result.success
        assert context.metrics.get("beat_grid_beats_per_bar") == 4
        assert "falling back to 4/4" in caplog.text

    @pytest.mark.asyncio
    async def test_pipeline_mode_missing_beat_grid_fails(self) -> None:
        """Pipeline mode: fails gracefully when beat_grid unavailable."""
        stage = DisplayRenderStage(display_graph=_make_display_graph())
        plan_set = _make_plan_set()
        context = _make_context()

        result = await stage.execute(plan_set, context)

        assert not result.success
        assert "beat_grid" in (result.error or "")

    @pytest.mark.asyncio
    async def test_pipeline_mode_zero_tempo_fails(self) -> None:
        """Pipeline mode: fails when tempo metric is invalid."""
        stage = DisplayRenderStage(display_graph=_make_display_graph())
        plan_set = _make_plan_set()
        context = _make_context()
        context.add_metric("audio_duration_ms", 32000)
        context.add_metric("tempo_bpm", 0.0)

        result = await stage.execute(plan_set, context)

        assert not result.success
        assert "tempo_bpm" in (result.error or "")

    @pytest.mark.asyncio
    async def test_asset_resolution_pipeline_mode(self) -> None:
        """AssetResolutionStage: pipeline mode with catalog in context state."""
        stage = AssetResolutionStage()
        plan_set = _make_plan_set(template_id="gtpl_base_motif_sparkles_ambient")
        entry = _make_catalog_entry("asset_sparkles", "images/sparkles.png", motif_id="sparkles")
        catalog = _make_catalog(entries=[entry])
        context = _make_context()
        context.set_state("asset_catalog", catalog)

        # Pass GroupPlanSet directly (pipeline mode)
        result = await stage.execute(plan_set, context)

        assert result.success
        placement = result.output.section_plans[0].lane_plans[0].coordination_plans[0].placements[0]
        assert len(placement.resolved_asset_ids) > 0

    @pytest.mark.asyncio
    async def test_asset_resolution_accepts_multi_input_payload(self) -> None:
        """Asset resolution should accept plan+asset stage payload shape from pipeline executor."""
        stage = AssetResolutionStage()
        plan_set = _make_plan_set()
        context = _make_context()

        result = await stage.execute({"aggregate": plan_set, "asset_creation": plan_set}, context)

        assert result.success
        assert result.output is plan_set

    @pytest.mark.asyncio
    async def test_name_property(self) -> None:
        """Stage has correct name."""
        assert DisplayRenderStage().name == "display_render"
