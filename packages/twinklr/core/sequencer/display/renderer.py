"""Display renderer: top-level coordinator for the display rendering pipeline.

Orchestrates the full pipeline:
  GroupPlanSet → CompositionEngine → RenderPlan → XSQWriter → XSequence

This is the primary entry point for display (non-moving-head) rendering.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.formats.xlights.sequence.models.xsq import XSequence
from twinklr.core.sequencer.display.composition.engine import (
    CompositionEngine,
)
from twinklr.core.sequencer.display.composition.palette_resolver import (
    PaletteResolver,
)
from twinklr.core.sequencer.display.composition.template_compiler import (
    TemplateCompiler,
)
from twinklr.core.sequencer.display.effects.handlers import (
    load_builtin_handlers,
)
from twinklr.core.sequencer.display.effects.protocol import RenderContext
from twinklr.core.sequencer.display.effects.registry import HandlerRegistry
from twinklr.core.sequencer.display.export.writer import XSQTraceEntry, XSQWriter
from twinklr.core.sequencer.display.models.config import (
    RenderConfig,
)
from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.display.models.render_plan import RenderPlan
from twinklr.core.sequencer.display.xlights_mapping import XLightsMapping
from twinklr.core.sequencer.planning.group_plan import GroupPlanSet
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
)
from twinklr.core.sequencer.theming.catalog import PaletteCatalog
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

logger = logging.getLogger(__name__)


class RenderResult(BaseModel):
    """Result of the display rendering pipeline.

    Attributes:
        render_plan: The intermediate RenderPlan (for debugging/inspection).
        effects_written: Number of effects placed in the sequence.
        elements_created: Number of xLights elements used.
        effectdb_entries: Number of EffectDB entries.
        palette_entries: Number of palette entries.
        warnings: All warnings from composition and rendering.
        missing_assets: Asset paths that were not found.
        xsq_trace_entries: Per-effect trace metadata for XSQ sidecar generation.
    """

    model_config = ConfigDict(extra="forbid")

    render_plan: RenderPlan
    effects_written: int = 0
    elements_created: int = 0
    effectdb_entries: int = 0
    palette_entries: int = 0
    warnings: list[str] = Field(default_factory=list)
    missing_assets: list[str] = Field(default_factory=list)
    xsq_trace_entries: list[XSQTraceEntry] = Field(default_factory=list)


class DisplayRenderer:
    """Top-level display renderer.

    Orchestrates the full pipeline from GroupPlanSet to XSequence effects.

    Usage:
        >>> renderer = DisplayRenderer(beat_grid, display_graph)
        >>> result = renderer.render(plan_set, sequence)
        >>> # sequence now has effects; export with XSQExporter
    """

    # Default fallback palette when catalog lookup fails (Christmas red+green)
    _FALLBACK_PALETTE = ResolvedPalette(
        colors=["#FF0000", "#00FF00"],
        active_slots=[1, 2],
    )

    def __init__(
        self,
        beat_grid: BeatGrid,
        choreo_graph: ChoreographyGraph,
        palette_catalog: PaletteCatalog | None = None,
        config: RenderConfig | None = None,
        handler_registry: HandlerRegistry | None = None,
        template_compiler: TemplateCompiler | None = None,
        xlights_mapping: XLightsMapping | None = None,
    ) -> None:
        """Initialize the display renderer.

        Args:
            beat_grid: Musical timing grid for the sequence.
            choreo_graph: Choreographic display configuration.
            palette_catalog: Theming palette catalog for color resolution.
                If None, uses the global PALETTE_REGISTRY.
            config: Render configuration. Defaults to sensible defaults.
            handler_registry: Custom handler registry. If None, loads
                builtin handlers (On, Color Wash, Chase, Spirals, Pictures).
            template_compiler: TemplateCompiler (e.g. RecipeCompiler) for
                multi-layer rendering.  Required for production rendering.
            xlights_mapping: xLights element name resolution.  If None,
                creates an empty mapping (IDs used as element names).
        """
        self._beat_grid = beat_grid
        self._choreo_graph = choreo_graph
        self._xlights_mapping = xlights_mapping or XLightsMapping()
        self._config = config or RenderConfig()
        self._handlers = handler_registry or load_builtin_handlers()
        self._template_compiler = template_compiler

        # Build palette resolver from catalog
        if palette_catalog is None:
            from twinklr.core.sequencer.theming.catalog import PALETTE_REGISTRY

            palette_catalog = PALETTE_REGISTRY
        self._palette_resolver = PaletteResolver(
            catalog=palette_catalog,
            default=self._FALLBACK_PALETTE,
        )

    def render(
        self,
        plan_set: GroupPlanSet,
        sequence: XSequence,
        asset_base_path: Path | None = None,
        catalog_index: dict[str, object] | None = None,
        section_boundaries: list[tuple[str, int, int]] | None = None,
    ) -> RenderResult:
        """Render a GroupPlanSet into an XSequence.

        This is the main entry point. It:
        1. Runs the CompositionEngine to produce a RenderPlan
        2. Creates an XSQWriter with the handler registry
        3. Writes the RenderPlan into the XSequence

        The XSequence is mutated in-place. After this call, export
        it with XSQExporter.

        Args:
            plan_set: Aggregated group plans for all sections.
            sequence: XSequence to write effects into.
            asset_base_path: Base path for image/video assets.
            catalog_index: Optional mapping of asset_id → CatalogEntry
                for resolving asset overlay rendering. Build this from
                ``AssetCatalog.build_index()``. When provided, placements
                with ``resolved_asset_ids`` produce dual-layer output
                (procedural + Pictures overlay).
            section_boundaries: List of ``(section_id, start_ms, end_ms)``
                tuples from the audio profile / macro plan.  Anchors
                section-relative bar/beat references to absolute song
                positions via the BeatGrid.

        Returns:
            RenderResult with the plan, statistics, and diagnostics.
        """
        logger.info(
            "DisplayRenderer: rendering %d sections for '%s'",
            len(plan_set.section_plans),
            plan_set.plan_set_id,
        )

        # Stage 1: Composition
        composition_config = self._config.composition
        engine = CompositionEngine(
            beat_grid=self._beat_grid,
            choreo_graph=self._choreo_graph,
            palette_resolver=self._palette_resolver,
            section_boundaries=section_boundaries,
            config=composition_config,
            catalog_index=catalog_index,
            template_compiler=self._template_compiler,
            xlights_mapping=self._xlights_mapping,
        )
        render_plan = engine.compose(plan_set)

        # Stage 2: XSQ Writing (includes effect handler dispatch)
        render_ctx = RenderContext(
            sequence_duration_ms=int(self._beat_grid.duration_ms),
            asset_base_path=asset_base_path or Path(self._config.asset_base_path or "."),
            default_buffer_style=composition_config.default_buffer_style,
            frame_interval_ms=self._config.frame_interval_ms,
        )

        writer = XSQWriter(
            handler_registry=self._handlers,
            render_context=render_ctx,
        )
        write_result = writer.write(render_plan, sequence)

        # Collect all diagnostics
        all_warnings = [d.message for d in render_plan.diagnostics if d.level == "warning"]
        all_warnings.extend(write_result.warnings)

        result = RenderResult(
            render_plan=render_plan,
            effects_written=write_result.effects_written,
            elements_created=write_result.elements_created,
            effectdb_entries=write_result.effectdb_entries,
            palette_entries=write_result.palette_entries,
            warnings=all_warnings,
            missing_assets=write_result.missing_assets,
            xsq_trace_entries=write_result.trace_entries,
        )

        logger.info(
            "DisplayRenderer: complete — %d effects on %d elements (%d warnings)",
            result.effects_written,
            result.elements_created,
            len(result.warnings),
        )

        return result


def build_display_xsq_trace_sidecar_payload(render_result: RenderResult) -> dict[str, Any]:
    """Build JSON-serializable sidecar payload for display XSQ trace metadata."""
    return {
        "schema_version": "display-xsq-trace.v1",
        "entry_count": len(render_result.xsq_trace_entries),
        "entries": render_result.xsq_trace_entries,
    }


def write_display_xsq_trace_sidecar(xsq_path: Path, render_result: RenderResult) -> Path:
    """Write display XSQ trace sidecar next to an exported XSQ file."""
    sidecar_path = Path(f"{xsq_path}.trace.json")
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_text(
        json.dumps(build_display_xsq_trace_sidecar_payload(render_result), indent=2),
        encoding="utf-8",
    )
    return sidecar_path


__all__ = [
    "build_display_xsq_trace_sidecar_payload",
    "write_display_xsq_trace_sidecar",
    "DisplayRenderer",
    "RenderResult",
]
