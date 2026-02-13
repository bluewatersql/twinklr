"""Display rendering pipeline stages.

Wraps the asset resolution and display rendering steps as pipeline stages
that can be composed with the existing sequencer pipeline.

Stages:
- AssetResolutionStage: Resolves plan assets against an AssetCatalog
- DisplayRenderStage: Renders a GroupPlanSet into an XSequence via DisplayRenderer
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from twinklr.core.agents.assets.models import AssetCatalog
from twinklr.core.agents.assets.resolver import resolve_plan_assets
from twinklr.core.formats.xlights.sequence.models.xsq import (
    SequenceHead,
    XSequence,
)
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.pipeline.result import StageResult, failure_result, success_result
from twinklr.core.sequencer.display.renderer import DisplayRenderer, RenderResult
from twinklr.core.sequencer.planning.group_plan import GroupPlanSet
from twinklr.core.sequencer.templates.group.models.display import DisplayGraph
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

logger = logging.getLogger(__name__)


class AssetResolutionStage:
    """Stage: Resolve plan assets against an AssetCatalog.

    Populates ``resolved_asset_ids`` on GroupPlacement objects by matching
    motif-based template IDs to catalog entries.

    Input (two modes):
        - Pipeline mode: ``GroupPlanSet`` directly (catalog from context state)
        - Direct mode: dict with ``plan_set`` and ``catalog`` keys

    Output: GroupPlanSet (with resolved_asset_ids populated)
    """

    @property
    def name(self) -> str:
        """Stage name."""
        return "asset_resolution"

    async def execute(
        self,
        input: Any,
        context: PipelineContext,
    ) -> StageResult[GroupPlanSet]:
        """Resolve plan assets against the catalog.

        Args:
            input: GroupPlanSet directly, or dict with ``plan_set``
                and ``catalog`` keys.
            context: Pipeline context (catalog may be in ``context.state``).

        Returns:
            StageResult containing GroupPlanSet with resolved asset IDs.
        """
        try:
            # Accept both GroupPlanSet directly and dict input
            if isinstance(input, GroupPlanSet):
                plan_set = input
                catalog = context.get_state("asset_catalog")
            elif isinstance(input, dict):
                plan_set = input["plan_set"]
                catalog = input.get("catalog") or context.get_state("asset_catalog")
            else:
                return failure_result(
                    f"Unexpected input type: {type(input).__name__}",
                    stage_name=self.name,
                )

            if catalog is None or not catalog.entries:
                logger.info("No asset catalog available — skipping resolution")
                return success_result(plan_set, stage_name=self.name)

            resolved = resolve_plan_assets(plan_set, catalog)

            # Count resolved placements for metrics
            resolved_count = sum(
                1
                for sp in resolved.section_plans
                for lp in sp.lane_plans
                for cp in lp.coordination_plans
                for p in cp.placements
                if p.resolved_asset_ids
            )
            context.add_metric("assets_resolved", resolved_count)

            logger.info(
                "Asset resolution complete: %d placements resolved",
                resolved_count,
            )

            return success_result(resolved, stage_name=self.name)

        except Exception as e:
            logger.exception("Asset resolution failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)


class DisplayRenderStage:
    """Stage: Render a GroupPlanSet into an XSequence.

    Wraps DisplayRenderer to produce xLights-compatible output.
    Supports optional asset overlay rendering via catalog_index.

    Input (two modes):
        - Pipeline mode: ``GroupPlanSet`` directly (beat_grid, display_graph,
          catalog, sequence from context state)
        - Direct mode: dict with all keys explicitly provided

    Dict keys (direct mode):
        - ``plan_set``: GroupPlanSet (optionally with resolved_asset_ids)
        - ``beat_grid``: BeatGrid
        - ``display_graph``: DisplayGraph
        - ``catalog``: AssetCatalog (optional, for overlay rendering)
        - ``sequence``: XSequence (optional, creates new if absent)
        - ``asset_base_path``: Path (optional, for Pictures handler)

    Output: dict with keys:
        - ``sequence``: XSequence (with effects rendered)
        - ``render_result``: RenderResult (statistics and diagnostics)
    """

    def __init__(
        self,
        beat_grid: BeatGrid | None = None,
        display_graph: DisplayGraph | None = None,
    ) -> None:
        """Initialize the stage with optional pre-configured dependencies.

        Args:
            beat_grid: Pre-configured beat grid (overrides context/input).
            display_graph: Pre-configured display graph (overrides context/input).
        """
        self._beat_grid = beat_grid
        self._display_graph = display_graph

    @property
    def name(self) -> str:
        """Stage name."""
        return "display_render"

    async def execute(
        self,
        input: Any,
        context: PipelineContext,
    ) -> StageResult[dict[str, Any]]:
        """Render GroupPlanSet to XSequence.

        Args:
            input: GroupPlanSet directly, or dict with required/optional keys.
            context: Pipeline context (dependencies may be in ``context.state``).

        Returns:
            StageResult containing dict with ``sequence`` and ``render_result``.
        """
        try:
            # Accept both GroupPlanSet directly and dict input
            if isinstance(input, GroupPlanSet):
                plan_set = input
                beat_grid = self._beat_grid or context.get_state("beat_grid")
                display_graph = self._display_graph or context.get_state("display_graph")
                catalog: AssetCatalog | None = context.get_state("asset_catalog")
                sequence: XSequence | None = context.get_state("sequence")
                asset_base_path: Path | None = context.get_state("asset_base_path")
            elif isinstance(input, dict):
                plan_set = input["plan_set"]
                beat_grid = input.get("beat_grid") or self._beat_grid or context.get_state("beat_grid")
                display_graph = (
                    input.get("display_graph")
                    or self._display_graph
                    or context.get_state("display_graph")
                )
                catalog = input.get("catalog") or context.get_state("asset_catalog")
                sequence = input.get("sequence") or context.get_state("sequence")
                asset_base_path = input.get("asset_base_path") or context.get_state("asset_base_path")
            else:
                return failure_result(
                    f"Unexpected input type: {type(input).__name__}",
                    stage_name=self.name,
                )

            if beat_grid is None:
                # Try to build from context metrics (set by AudioAnalysisStage)
                beat_grid = self._build_beat_grid_from_context(context)
            if beat_grid is None:
                return failure_result(
                    "beat_grid is required (via input, constructor, or context state)",
                    stage_name=self.name,
                )
            if display_graph is None:
                return failure_result(
                    "display_graph is required (via input, constructor, or context state)",
                    stage_name=self.name,
                )

            # Build catalog index for overlay rendering
            catalog_index: dict[str, object] | None = None
            if catalog is not None and catalog.entries:
                raw_index = catalog.build_index()
                catalog_index = dict(raw_index)  # Widen type for engine
                logger.info(
                    "Built catalog index with %d entries for overlay rendering",
                    len(raw_index),
                )

            # Create empty sequence if not provided
            if sequence is None:
                sequence = XSequence(
                    head=SequenceHead(
                        version="2024.01",
                        author="Twinklr Display Renderer",
                        song="",
                        sequence_timing="20 ms",
                        media_file="",
                        sequence_duration_ms=int(beat_grid.duration_ms),
                    ),
                )

            # Create renderer and render
            renderer = DisplayRenderer(
                beat_grid=beat_grid,
                display_graph=display_graph,
            )

            result: RenderResult = renderer.render(
                plan_set=plan_set,
                sequence=sequence,
                asset_base_path=asset_base_path,
                catalog_index=catalog_index,
            )

            # Track metrics
            context.add_metric("effects_written", result.effects_written)
            context.add_metric("elements_created", result.elements_created)
            context.add_metric("render_warnings", len(result.warnings))

            logger.info(
                "Display render complete: %d effects on %d elements (%d warnings)",
                result.effects_written,
                result.elements_created,
                len(result.warnings),
            )

            return success_result(
                {"sequence": sequence, "render_result": result},
                stage_name=self.name,
            )

        except Exception as e:
            logger.exception("Display rendering failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)


    @staticmethod
    def _build_beat_grid_from_context(context: PipelineContext) -> BeatGrid | None:
        """Attempt to build a BeatGrid from context metrics.

        Uses ``audio_duration_ms`` and ``tempo_bpm`` metrics that are
        set by ``AudioAnalysisStage``.

        Args:
            context: Pipeline context.

        Returns:
            BeatGrid or None if metrics are unavailable.
        """
        duration_ms = context.metrics.get("audio_duration_ms")
        tempo_bpm = context.metrics.get("tempo_bpm")

        if duration_ms is None or tempo_bpm is None:
            return None

        duration_ms = float(duration_ms)
        tempo_bpm = float(tempo_bpm)
        beats_per_bar = 4  # Default 4/4 time

        ms_per_beat = 60_000.0 / tempo_bpm
        ms_per_bar = ms_per_beat * beats_per_bar
        num_bars = int(duration_ms / ms_per_bar) + 1
        total_beats = num_bars * beats_per_bar

        logger.info(
            "Built BeatGrid from context: %.0f BPM, %d bars, %.1fs",
            tempo_bpm,
            num_bars,
            duration_ms / 1000,
        )

        return BeatGrid(
            bar_boundaries=[i * ms_per_bar for i in range(num_bars + 1)],
            beat_boundaries=[i * ms_per_beat for i in range(total_beats + 1)],
            eighth_boundaries=[
                i * ms_per_beat / 2 for i in range(total_beats * 2 + 1)
            ],
            sixteenth_boundaries=[
                i * ms_per_beat / 4 for i in range(total_beats * 4 + 1)
            ],
            tempo_bpm=tempo_bpm,
            beats_per_bar=beats_per_bar,
            duration_ms=duration_ms,
        )


__all__ = [
    "AssetResolutionStage",
    "DisplayRenderStage",
]
