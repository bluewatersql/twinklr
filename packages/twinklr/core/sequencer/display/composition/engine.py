"""Composition engine: transforms GroupPlanSet into a RenderPlan.

The CompositionEngine is the core decision-making stage. It walks the
GroupPlanSet section by section, resolving targets, timing, layers,
and palettes to produce the intermediate RenderPlan.

Uses a ``TemplateCompiler`` (when provided) to translate each
``GroupPlacement`` into one or more ``CompiledEffect``s via the
template's ``LayerRecipe`` definitions.  Each ``CompiledEffect`` is
tagged with a ``VisualDepth`` so the engine can assign it to the
correct xLights layer.

Supports dual-layer rendering: when a placement has resolved_asset_ids
(from the asset resolution step), the engine emits both a procedural
effect event AND a Pictures overlay event on adjacent layers.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from twinklr.core.sequencer.display.composition.layer_allocator import (
    LayerAllocator,
)
from twinklr.core.sequencer.display.composition.models import (
    CompiledEffect,
)
from twinklr.core.sequencer.display.composition.palette_resolver import (
    PaletteResolver,
)
from twinklr.core.sequencer.display.composition.section_map import (
    SectionBarRange,
    build_section_bar_map,
)
from twinklr.core.sequencer.display.composition.target_resolver import (
    TargetResolver,
)
from twinklr.core.sequencer.display.composition.template_compiler import (
    TemplateCompileContext,
    TemplateCompiler,
)
from twinklr.core.sequencer.display.composition.timing_resolver import (
    TimingResolver,
)
from twinklr.core.sequencer.display.models.config import CompositionConfig
from twinklr.core.sequencer.display.models.palette import (
    ResolvedPalette,
    TransitionSpec,
)
from twinklr.core.sequencer.display.models.render_event import (
    RenderEvent,
    RenderEventSource,
)
from twinklr.core.sequencer.display.models.render_plan import (
    CompositionDiagnostic,
    RenderGroupPlan,
    RenderLayerPlan,
    RenderPlan,
)
from twinklr.core.sequencer.display.xlights_mapping import XLightsMapping
from twinklr.core.sequencer.planning.group_plan import (
    GroupPlanSet,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.planning.models import PaletteRef
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
)
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationConfig,
    CoordinationPlan,
    GroupPlacement,
    PlacementWindow,
    PlanTarget,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    EffectDuration,
    IntensityLevel,
    LaneKind,
    PlanningTimeRef,
    StepUnit,
)
from twinklr.core.sequencer.vocabulary.choreography import TargetType
from twinklr.core.sequencer.vocabulary.coordination import SpatialIntent

logger = logging.getLogger(__name__)


# IntensityLevel → normalized float, per lane
_INTENSITY_MAP: dict[LaneKind, dict[IntensityLevel, float]] = {
    LaneKind.BASE: {
        IntensityLevel.WHISPER: 0.15,
        IntensityLevel.SOFT: 0.30,
        IntensityLevel.MED: 0.50,
        IntensityLevel.STRONG: 0.70,
        IntensityLevel.PEAK: 0.85,
    },
    LaneKind.RHYTHM: {
        IntensityLevel.WHISPER: 0.25,
        IntensityLevel.SOFT: 0.45,
        IntensityLevel.MED: 0.65,
        IntensityLevel.STRONG: 0.80,
        IntensityLevel.PEAK: 0.95,
    },
    LaneKind.ACCENT: {
        IntensityLevel.WHISPER: 0.40,
        IntensityLevel.SOFT: 0.60,
        IntensityLevel.MED: 0.75,
        IntensityLevel.STRONG: 0.90,
        IntensityLevel.PEAK: 1.0,
    },
}


class CompositionEngine:
    """Transforms a GroupPlanSet into a RenderPlan.

    Walks the plan section by section, resolving each placement to
    concrete timing, target elements, layer indices, palettes, and
    effect types.

    Section-relative bar/beat references from the LLM planners are
    anchored to absolute song positions via the ``section_boundaries``
    parameter and the BeatGrid.  The BeatGrid is the sole timing
    authority — all ms values are derived from it.

    When an optional ``catalog_index`` is provided, placements with
    ``resolved_asset_ids`` produce dual-layer output: a procedural
    effect on the base layer and a Pictures overlay on the layer above.

    Args:
        beat_grid: Musical timing grid (source of truth for all timing).
        choreo_graph: Choreographic display configuration (spatial ordering).
        palette_resolver: Resolves PaletteRef → ResolvedPalette.
        section_boundaries: List of ``(section_id, start_ms, end_ms)``
            tuples from the audio profile / macro plan.  Used to build
            a section-to-bar mapping so section-relative bar/beat
            references resolve to the correct song position.
        config: Composition configuration.
        catalog_index: Optional mapping of asset_id → CatalogEntry
            for resolving asset file paths during overlay rendering.
        template_compiler: Optional ``TemplateCompiler`` for multi-layer
            template rendering.  Uses the compiler to produce
            ``CompiledEffect``s from template layer definitions.
        xlights_mapping: Mapping for resolving choreography IDs to
            xLights element names.  If None, creates an empty mapping
            (IDs fall back to themselves as element names).
    """

    def __init__(
        self,
        beat_grid: BeatGrid,
        choreo_graph: ChoreographyGraph,
        palette_resolver: PaletteResolver,
        section_boundaries: list[tuple[str, int, int]] | None = None,
        config: CompositionConfig | None = None,
        catalog_index: dict[str, object] | None = None,
        template_compiler: TemplateCompiler | None = None,
        xlights_mapping: XLightsMapping | None = None,
    ) -> None:
        self._beat_grid = beat_grid
        self._choreo_graph = choreo_graph
        self._config = config or CompositionConfig()
        self._xlights_mapping = xlights_mapping or XLightsMapping()
        self._target_resolver = TargetResolver(choreo_graph, self._xlights_mapping)
        self._layer_allocator = LayerAllocator()
        self._timing_resolver = TimingResolver(beat_grid)
        self._palette_resolver = palette_resolver
        self._catalog_index: dict[str, object] = catalog_index or {}
        self._layer_blend_modes: dict[tuple[str, int], str] = {}
        self._section_map: dict[str, SectionBarRange] = (
            build_section_bar_map(section_boundaries, beat_grid) if section_boundaries else {}
        )
        self._template_compiler: TemplateCompiler | None = template_compiler

    def compose(self, plan_set: GroupPlanSet) -> RenderPlan:
        """Compose a GroupPlanSet into a RenderPlan.

        Args:
            plan_set: Aggregated group plans for all sections.

        Returns:
            RenderPlan intermediate representation.
        """
        diagnostics: list[CompositionDiagnostic] = []

        # Accumulator: element_name → layer_index → list[RenderEvent]
        element_layers: dict[str, dict[int, list[RenderEvent]]] = {}

        for section in plan_set.section_plans:
            self._compose_section(
                section=section,
                element_layers=element_layers,
                diagnostics=diagnostics,
            )

        # Resolve overlaps per layer
        for element_name, layers in element_layers.items():
            for layer_idx, events in layers.items():
                events.sort(key=lambda e: e.start_ms)
                resolved = self._resolve_overlaps(events)
                element_layers[element_name][layer_idx] = resolved

        # Build RenderPlan from accumulated data
        groups = self._build_groups(element_layers)

        plan = RenderPlan(
            render_id=str(uuid4()),
            duration_ms=int(self._beat_grid.duration_ms),
            groups=groups,
            diagnostics=diagnostics,
        )

        logger.info(
            "Composed RenderPlan: %d elements, %d total events, %d diagnostics",
            len(plan.groups),
            plan.total_events,
            len(diagnostics),
        )

        return plan

    def _compose_section(
        self,
        section: SectionCoordinationPlan,
        element_layers: dict[str, dict[int, list[RenderEvent]]],
        diagnostics: list[CompositionDiagnostic],
    ) -> None:
        """Compose a single section into render events.

        Args:
            section: Section coordination plan.
            element_layers: Accumulator for element/layer/events.
            diagnostics: Accumulator for diagnostics.
        """
        # Resolve section palette
        section_palette = self._resolve_palette(section.palette)

        # Resolve section boundaries from the bar map (BeatGrid is
        # the timing authority).  Falls back to plan-level values for
        # backward compatibility, but those are expected to be None
        # in the normal pipeline flow.
        section_range = self._section_map.get(section.section_id)
        if section_range is not None:
            section_start_bar = section_range.start_bar
            section_end_ms: int | None = int(section_range.end_ms)
        else:
            section_start_bar = 0
            section_end_ms = section.end_ms

        for lane_plan in section.lane_plans:
            lane = lane_plan.lane
            layer_idx = self._layer_allocator.allocate(lane)
            blend_mode = LayerAllocator.resolve_blend_mode(lane_plan.blend_mode)

            # Track blend mode per element/layer
            for target_id in self._collect_target_ids(lane_plan.coordination_plans):
                element_name = self._target_resolver.resolve(target_id)
                key = (element_name, layer_idx)
                if key not in self._layer_blend_modes:
                    self._layer_blend_modes[key] = blend_mode

            for coord_plan in lane_plan.coordination_plans:
                self._compose_coordination(
                    coord_plan=coord_plan,
                    section=section,
                    lane=lane,
                    section_palette=section_palette,
                    section_start_bar=section_start_bar,
                    section_end_ms=section_end_ms,
                    element_layers=element_layers,
                    diagnostics=diagnostics,
                )

    def _compose_coordination(
        self,
        coord_plan: CoordinationPlan,
        section: SectionCoordinationPlan,
        lane: LaneKind,
        section_palette: ResolvedPalette,
        section_start_bar: int,
        section_end_ms: int | None,
        element_layers: dict[str, dict[int, list[RenderEvent]]],
        diagnostics: list[CompositionDiagnostic],
    ) -> None:
        """Compose a coordination plan into render events.

        Handles all coordination modes:
        - UNIFIED/COMPLEMENTARY: placements are pre-expanded.
        - SEQUENCED/CALL_RESPONSE/RIPPLE: window + config are expanded
          into staggered per-group placements.

        Uses the TemplateCompiler to resolve each placement into one or
        more CompiledEffects via the template's LayerRecipe definitions.

        Args:
            coord_plan: Coordination plan with placements.
            section: Parent section (for context).
            lane: Lane kind for intensity resolution.
            section_palette: Resolved palette for this section.
            section_start_bar: 0-indexed song bar where this section starts.
            section_end_ms: Section end boundary for clamping (None = no clamp).
            element_layers: Accumulator.
            diagnostics: Accumulator.

        Raises:
            RuntimeError: If no template compiler is configured.
        """
        if self._template_compiler is None:
            raise RuntimeError(
                "CompositionEngine requires a TemplateCompiler for rendering. "
                "Pass template_compiler to DisplayRenderer or CompositionEngine."
            )
        # Expand SEQUENCED/CALL_RESPONSE/RIPPLE windows into placements
        placements = list(coord_plan.placements)

        if (
            not placements
            and coord_plan.window is not None
            and coord_plan.config is not None
            and coord_plan.coordination_mode
            in {
                CoordinationMode.SEQUENCED,
                CoordinationMode.CALL_RESPONSE,
                CoordinationMode.RIPPLE,
            }
        ):
            placements = self._expand_window(
                window=coord_plan.window,
                config=coord_plan.config,
                coordination_mode=coord_plan.coordination_mode,
                section=section,
                lane=lane,
                diagnostics=diagnostics,
            )

        if not placements:
            return

        overlay_layer_idx = self._layer_allocator.allocate_overlay(lane)

        for idx, placement in enumerate(placements):
            compiled_effects = self._compose_placement_compiled(
                placement=placement,
                section=section,
                lane=lane,
                section_palette=section_palette,
                section_start_bar=section_start_bar,
                section_end_ms=section_end_ms,
                placement_index=idx,
                diagnostics=diagnostics,
            )
            element_name = self._target_resolver.resolve(placement.target.id)

            for ce in compiled_effects:
                sub_layer = self._layer_allocator.allocate_sub_layer(lane, ce.visual_depth)
                if element_name not in element_layers:
                    element_layers[element_name] = {}
                if sub_layer not in element_layers[element_name]:
                    element_layers[element_name][sub_layer] = []
                element_layers[element_name][sub_layer].append(ce.event)

            # Asset overlays — use the first compiled event as the
            # procedural reference for timing/palette.
            if compiled_effects:
                overlay_events = self._build_asset_overlay_events(
                    placement=placement,
                    procedural_event=compiled_effects[0].event,
                    section=section,
                    lane=lane,
                    section_palette=section_palette,
                    placement_index=idx,
                )
                if overlay_events:
                    if overlay_layer_idx not in element_layers.get(element_name, {}):
                        element_layers.setdefault(element_name, {})[overlay_layer_idx] = []
                    element_layers[element_name][overlay_layer_idx].extend(overlay_events)
                    overlay_key = (element_name, overlay_layer_idx)
                    if overlay_key not in self._layer_blend_modes:
                        self._layer_blend_modes[overlay_key] = "Normal"

    def _expand_window(
        self,
        window: PlacementWindow,
        config: CoordinationConfig,
        coordination_mode: CoordinationMode,
        section: SectionCoordinationPlan,
        lane: LaneKind,
        diagnostics: list[CompositionDiagnostic],
    ) -> list[GroupPlacement]:
        """Expand a window into per-group placements by coordination mode.

        Dispatches to mode-specific expansion logic:

        - **SEQUENCED**: non-overlapping time slots, one group at a time.
        - **RIPPLE**: overlapping wave propagation using ``phase_offset``.
        - **CALL_RESPONSE**: alternating A/B group teams.

        Args:
            window: Time window and template definition.
            config: Coordination config (group_order, step_unit, etc.).
            coordination_mode: How groups relate to each other.
            section: Parent section for context.
            lane: Lane kind.
            diagnostics: Accumulator.

        Returns:
            List of expanded GroupPlacement objects.
        """
        # Resolve window boundaries to ms (section-relative).
        # _compose_placement handles the section offset, so we
        # work in section-relative time here.
        window_start_ms = self._timing_resolver.resolve_start_ms(window.start)
        window_end_ms = self._timing_resolver.resolve_start_ms(window.end)

        if window_end_ms <= window_start_ms:
            diagnostics.append(
                CompositionDiagnostic(
                    level="warning",
                    message=(
                        f"Window has zero/negative duration "
                        f"(start={window_start_ms}, end={window_end_ms})"
                    ),
                    source_section=section.section_id,
                )
            )
            return []

        step_ms = self._resolve_step_ms(config.step_unit, config.step_duration)

        if len(config.group_order) == 0:
            return []

        # Apply spatial ordering when SpatialIntent is specified.
        # Reorders group_order based on categorical GroupPosition metadata
        # from the DisplayGraph so that e.g. L2R sweeps groups left-to-right
        # regardless of the planner-specified order.
        group_order = list(config.group_order)
        if config.spatial_intent != SpatialIntent.NONE:
            sorted_groups = self._choreo_graph.groups_sorted_by(config.spatial_intent)
            sorted_ids = [g.id for g in sorted_groups]
            order_set = set(group_order)
            reordered = [gid for gid in sorted_ids if gid in order_set]
            # Preserve any group_order entries not in the display graph
            remaining = [gid for gid in group_order if gid not in set(reordered)]
            group_order = reordered + remaining

        # Construct a config copy with the spatially-ordered group_order.
        # CoordinationConfig is frozen, so we create a new instance.
        effective_config = CoordinationConfig(
            group_order=group_order,
            step_unit=config.step_unit,
            step_duration=config.step_duration,
            phase_offset=config.phase_offset,
            spill_policy=config.spill_policy,
            spatial_intent=config.spatial_intent,
        )

        if coordination_mode == CoordinationMode.RIPPLE:
            return self._expand_ripple(
                window, effective_config, step_ms, window_start_ms, window_end_ms
            )
        if coordination_mode == CoordinationMode.CALL_RESPONSE:
            return self._expand_call_response(
                window, effective_config, step_ms, window_start_ms, window_end_ms
            )

        # Default: SEQUENCED
        return self._expand_sequenced(
            window, effective_config, step_ms, window_start_ms, window_end_ms
        )

    def _expand_sequenced(
        self,
        window: PlacementWindow,
        config: CoordinationConfig,
        step_ms: int,
        window_start_ms: int,
        window_end_ms: int,
    ) -> list[GroupPlacement]:
        """SEQUENCED: non-overlapping round-robin slots.

        Each group gets a time slot of ``step_ms``, then the next group
        takes over. Groups cycle through in order across the window.
        """
        placements: list[GroupPlacement] = []
        group_count = len(config.group_order)

        for group_idx, group_id in enumerate(config.group_order):
            group_offset_ms = group_idx * step_ms
            current_ms = window_start_ms + group_offset_ms
            slot_idx = 0

            while current_ms < window_end_ms:
                slot_duration_ms = step_ms * group_count
                slot_end_ms = min(current_ms + slot_duration_ms, window_end_ms)

                if slot_end_ms <= current_ms:
                    break

                start_ref = self._ms_to_planning_ref(current_ms)
                duration = self._ms_to_duration(slot_end_ms - current_ms)

                placements.append(
                    GroupPlacement(
                        placement_id=f"seq_{group_id}_{slot_idx}",
                        target=PlanTarget(type=TargetType.GROUP, id=group_id),
                        template_id=window.template_id,
                        start=start_ref,
                        duration=duration,
                        param_overrides=dict(window.param_overrides),
                        intensity=window.intensity,
                    )
                )

                current_ms += slot_duration_ms
                slot_idx += 1

        logger.debug(
            "Expanded SEQUENCED window: %d groups × %d step_ms → %d placements",
            group_count,
            step_ms,
            len(placements),
        )
        return placements

    def _expand_ripple(
        self,
        window: PlacementWindow,
        config: CoordinationConfig,
        step_ms: int,
        window_start_ms: int,
        window_end_ms: int,
    ) -> list[GroupPlacement]:
        """RIPPLE: overlapping wave propagation across groups.

        Each group plays the full ``step_ms`` duration, but starts
        ``phase_offset * step_ms`` after the previous group. When
        ``phase_offset`` < 1.0, groups overlap in time — creating
        a ripple/wave visual that propagates across the display.

        With ``phase_offset=0.0``, falls back to SEQUENCED spacing
        (one step per group, no overlap).
        """
        placements: list[GroupPlacement] = []
        group_count = len(config.group_order)

        # Phase offset between consecutive groups (in ms)
        offset_ms = int(config.phase_offset * step_ms)
        if offset_ms <= 0:
            # Fallback: no overlap → use SEQUENCED spacing
            offset_ms = step_ms

        # Wave period: time between the start of consecutive waves.
        # One wave = all groups staggered by offset_ms.
        wave_period_ms = max(step_ms, offset_ms * group_count)

        wave_idx = 0
        while True:
            wave_start_ms = window_start_ms + wave_idx * wave_period_ms
            if wave_start_ms >= window_end_ms:
                break

            for group_idx, group_id in enumerate(config.group_order):
                start_ms = wave_start_ms + group_idx * offset_ms

                if start_ms >= window_end_ms:
                    break

                end_ms = min(start_ms + step_ms, window_end_ms)
                if end_ms <= start_ms:
                    break

                start_ref = self._ms_to_planning_ref(start_ms)
                duration = self._ms_to_duration(end_ms - start_ms)

                placements.append(
                    GroupPlacement(
                        placement_id=f"rpl_{group_id}_{wave_idx}",
                        target=PlanTarget(type=TargetType.GROUP, id=group_id),
                        template_id=window.template_id,
                        start=start_ref,
                        duration=duration,
                        param_overrides=dict(window.param_overrides),
                        intensity=window.intensity,
                    )
                )

            wave_idx += 1

        logger.debug(
            "Expanded RIPPLE window: %d groups × %dms offset → %d placements",
            group_count,
            offset_ms,
            len(placements),
        )
        return placements

    def _expand_call_response(
        self,
        window: PlacementWindow,
        config: CoordinationConfig,
        step_ms: int,
        window_start_ms: int,
        window_end_ms: int,
    ) -> list[GroupPlacement]:
        """CALL_RESPONSE: alternating A/B group teams.

        Groups are split into two teams based on position in
        ``group_order``: even-indexed groups form team A ("call"),
        odd-indexed form team B ("response"). Teams take turns,
        each active for ``step_ms`` before the other team responds.
        """
        placements: list[GroupPlacement] = []

        a_groups = [g for i, g in enumerate(config.group_order) if i % 2 == 0]
        b_groups = [g for i, g in enumerate(config.group_order) if i % 2 == 1]

        current_ms = window_start_ms
        slot_idx = 0
        is_a_turn = True

        while current_ms < window_end_ms:
            active_groups = a_groups if is_a_turn else b_groups
            slot_end_ms = min(current_ms + step_ms, window_end_ms)

            if slot_end_ms <= current_ms:
                break

            start_ref = self._ms_to_planning_ref(current_ms)
            duration = self._ms_to_duration(slot_end_ms - current_ms)
            prefix = "cr_a" if is_a_turn else "cr_b"

            for group_id in active_groups:
                placements.append(
                    GroupPlacement(
                        placement_id=f"{prefix}_{group_id}_{slot_idx}",
                        target=PlanTarget(type=TargetType.GROUP, id=group_id),
                        template_id=window.template_id,
                        start=start_ref,
                        duration=duration,
                        param_overrides=dict(window.param_overrides),
                        intensity=window.intensity,
                    )
                )

            current_ms += step_ms
            is_a_turn = not is_a_turn
            slot_idx += 1

        logger.debug(
            "Expanded CALL_RESPONSE window: A=%d, B=%d groups → %d placements",
            len(a_groups),
            len(b_groups),
            len(placements),
        )
        return placements

    def _resolve_step_ms(self, step_unit: StepUnit, step_duration: int) -> int:
        """Resolve a step unit and duration to milliseconds.

        Args:
            step_unit: BEAT, BAR, or PHRASE.
            step_duration: Number of step units.

        Returns:
            Step size in milliseconds.
        """
        ms_per_beat = 60_000.0 / self._beat_grid.tempo_bpm
        beats_per_bar = self._beat_grid.beats_per_bar

        if step_unit == StepUnit.BEAT:
            return int(ms_per_beat * step_duration)
        elif step_unit == StepUnit.BAR:
            return int(ms_per_beat * beats_per_bar * step_duration)
        elif step_unit == StepUnit.PHRASE:
            # Phrase = 4 bars by convention
            return int(ms_per_beat * beats_per_bar * 4 * step_duration)
        else:
            return int(ms_per_beat * step_duration)

    def _ms_to_planning_ref(self, ms: float) -> PlanningTimeRef:
        """Convert milliseconds to a PlanningTimeRef (bar/beat).

        Args:
            ms: Time in milliseconds.

        Returns:
            PlanningTimeRef with 1-indexed bar and beat.
        """
        ms_per_beat = 60_000.0 / self._beat_grid.tempo_bpm
        beats_per_bar = self._beat_grid.beats_per_bar

        total_beats = ms / ms_per_beat
        bar_0 = int(total_beats // beats_per_bar)
        beat_in_bar = int(total_beats % beats_per_bar)

        return PlanningTimeRef(
            bar=bar_0 + 1,  # 1-indexed
            beat=beat_in_bar + 1,  # 1-indexed
        )

    def _ms_to_duration(self, duration_ms: float) -> EffectDuration:
        """Map a millisecond duration to the nearest EffectDuration category.

        Boundaries are aligned with the vocabulary ranges in
        ``DURATION_BEATS``, using midpoints between consecutive
        categories as thresholds:

        - HIT: 1-2 beats → <=3 beats
        - BURST: 4 beats → <=6 beats
        - PHRASE: 8-16 beats → <=16 beats
        - EXTENDED: 16-32 beats → <=32 beats
        - SECTION: anything longer

        Args:
            duration_ms: Duration in milliseconds.

        Returns:
            Closest EffectDuration category.
        """
        ms_per_beat = 60_000.0 / self._beat_grid.tempo_bpm

        beats = duration_ms / ms_per_beat

        if beats <= 3:
            return EffectDuration.HIT
        elif beats <= 6:
            return EffectDuration.BURST
        elif beats <= 16:
            return EffectDuration.PHRASE
        elif beats <= 32:
            return EffectDuration.EXTENDED
        else:
            return EffectDuration.SECTION

    def _compose_placement_compiled(
        self,
        placement: GroupPlacement,
        section: SectionCoordinationPlan,
        lane: LaneKind,
        section_palette: ResolvedPalette,
        section_start_bar: int,
        section_end_ms: int | None,
        placement_index: int,
        diagnostics: list[CompositionDiagnostic],
    ) -> list[CompiledEffect]:
        """Compose a placement via the TemplateCompiler (multi-layer path).

        Resolves timing, intensity, and transitions, then delegates to
        the compiler which reads the template's LayerRecipe list and
        returns one CompiledEffect per recipe.

        Raises ``TemplateCompileError`` on any template issue (no
        silent fallback).

        Args:
            placement: Group placement from the plan.
            section: Parent section.
            lane: Lane kind.
            section_palette: Resolved palette.
            section_start_bar: 0-indexed song bar where this section starts.
            section_end_ms: Section end boundary for clamping.
            placement_index: Index within the coordination plan.
            diagnostics: Accumulator.

        Returns:
            List of CompiledEffect (empty on zero-duration placement).

        Raises:
            TemplateCompileError: On missing template, empty recipes,
                or unrecognised motifs.
        """
        assert self._template_compiler is not None  # caller guarantees

        # Resolve timing
        start_ms = self._timing_resolver.resolve_start_ms(
            placement.start,
            section_start_bar=section_start_bar,
        )
        end_ms = self._timing_resolver.resolve_end_ms(
            start_ms=start_ms,
            duration=placement.duration,
            section_end_ms=section_end_ms,
        )

        if end_ms <= start_ms:
            diagnostics.append(
                CompositionDiagnostic(
                    level="warning",
                    message=(
                        f"Placement {placement.placement_id} has zero/negative "
                        f"duration (start={start_ms}, end={end_ms})"
                    ),
                    source_section=section.section_id,
                    source_group=placement.target.id,
                )
            )
            return []

        # Resolve intensity and transitions
        intensity = self._resolve_intensity(lane, placement.intensity)
        transition_in, transition_out = self._resolve_transitions(lane)

        # Build compile context
        ctx = TemplateCompileContext(
            section_id=section.section_id,
            lane=lane,
            palette=section_palette,
            start_ms=start_ms,
            end_ms=end_ms,
            intensity=intensity,
            placement_index=placement_index,
            transition_in=transition_in,
            transition_out=transition_out,
        )

        # Delegate to compiler — raises TemplateCompileError on failure
        return self._template_compiler.compile(placement, ctx)

    def _build_asset_overlay_events(
        self,
        placement: GroupPlacement,
        procedural_event: RenderEvent,
        section: SectionCoordinationPlan,
        lane: LaneKind,
        section_palette: ResolvedPalette,
        placement_index: int,
    ) -> list[RenderEvent]:
        """Build Pictures overlay events for a placement with resolved assets.

        Returns one RenderEvent per resolved asset ID.  If the placement
        has no ``resolved_asset_ids`` or no ``catalog_index`` is configured,
        returns an empty list.

        Args:
            placement: Group placement (may have resolved_asset_ids).
            procedural_event: The procedural RenderEvent for timing/palette.
            section: Parent section.
            lane: Lane kind.
            section_palette: Resolved palette.
            placement_index: Index within the coordination plan.

        Returns:
            List of Pictures overlay RenderEvents (may be empty).
        """
        if not placement.resolved_asset_ids or not self._catalog_index:
            return []

        # Use the first valid resolved asset (best match from resolver).
        # xLights cannot stack multiple Pictures effects on the same
        # layer at the same time, so we pick only one per placement.
        for asset_id in placement.resolved_asset_ids:
            entry = self._catalog_index.get(asset_id)
            if entry is None:
                logger.warning(
                    "Asset %s not found in catalog index, skipping",
                    asset_id,
                )
                continue

            # CatalogEntry has a file_path field with the generated file
            file_path = getattr(entry, "file_path", None)
            if not file_path:
                logger.warning(
                    "Asset %s has no file_path, skipping",
                    asset_id,
                )
                continue

            overlay_event = RenderEvent(
                event_id=f"{procedural_event.event_id}_overlay_{asset_id[:8]}",
                start_ms=procedural_event.start_ms,
                end_ms=procedural_event.end_ms,
                effect_type="Pictures",
                parameters={"filename": str(file_path)},
                buffer_style="Per Model Default",
                buffer_transform=None,
                palette=section_palette,
                intensity=procedural_event.intensity,
                transition_in=procedural_event.transition_in,
                transition_out=procedural_event.transition_out,
                source=RenderEventSource(
                    section_id=section.section_id,
                    lane=lane,
                    group_id=placement.target.id,
                    template_id=placement.template_id,
                    placement_index=placement_index,
                ),
            )

            logger.debug(
                "Emitted overlay event for placement %s (asset=%s)",
                placement.placement_id,
                asset_id,
            )
            return [overlay_event]

        logger.debug(
            "No valid catalog entry found for placement %s",
            placement.placement_id,
        )
        return []

    def _resolve_palette(self, palette_ref: PaletteRef | None) -> ResolvedPalette:
        """Resolve a PaletteRef to a ResolvedPalette.

        Delegates to the injected PaletteResolver which performs
        catalog lookup and color extraction.

        Args:
            palette_ref: Palette reference from the plan (may be None).

        Returns:
            ResolvedPalette with concrete color values.
        """
        return self._palette_resolver.resolve(palette_ref)

    def _resolve_intensity(self, lane: LaneKind, level: IntensityLevel) -> float:
        """Resolve categorical intensity to a normalized float.

        Respects the lane hierarchy guarantee:
        BASE < RHYTHM < ACCENT at every intensity level.

        Args:
            lane: Lane kind.
            level: Categorical intensity level.

        Returns:
            Normalized intensity (0.0-1.0).
        """
        lane_map = _INTENSITY_MAP.get(lane, _INTENSITY_MAP[LaneKind.BASE])
        return lane_map.get(level, 0.5)

    @staticmethod
    def _resolve_transitions(
        lane: LaneKind,
    ) -> tuple[TransitionSpec | None, TransitionSpec | None]:
        """Resolve fade-in / fade-out transitions based on lane.

        Policy:
        - BASE:   Long crossfade   (1.0 s in, 1.0 s out)
        - RHYTHM: Short crossfade  (0.3 s in, 0.3 s out)
        - ACCENT: No fade-in, short fade-out (0.2 s out)

        Args:
            lane: Lane kind (BASE/RHYTHM/ACCENT).

        Returns:
            Tuple of (transition_in, transition_out); either may be None.
        """
        if lane == LaneKind.BASE:
            return (
                TransitionSpec(type="Fade", duration_ms=1000),
                TransitionSpec(type="Fade", duration_ms=1000),
            )
        if lane == LaneKind.RHYTHM:
            return (
                TransitionSpec(type="Fade", duration_ms=300),
                TransitionSpec(type="Fade", duration_ms=300),
            )
        # ACCENT — punchy entrance, gentle exit
        return (
            None,
            TransitionSpec(type="Fade", duration_ms=200),
        )

    def _resolve_overlaps(self, events: list[RenderEvent]) -> list[RenderEvent]:
        """Resolve overlapping events within a single layer.

        Phase 1: TRIM policy — when events overlap, the earlier event's
        end time is trimmed to the later event's start time.

        Args:
            events: Sorted list of render events.

        Returns:
            List of non-overlapping events.
        """
        if len(events) <= 1:
            return events

        resolved: list[RenderEvent] = []

        for i, event in enumerate(events):
            if i + 1 < len(events):
                next_event = events[i + 1]
                if event.end_ms > next_event.start_ms:
                    # Trim current event to next event's start
                    trimmed_end = next_event.start_ms
                    if trimmed_end > event.start_ms:
                        # Create trimmed copy (frozen model, must reconstruct)
                        event = RenderEvent(
                            event_id=event.event_id,
                            start_ms=event.start_ms,
                            end_ms=trimmed_end,
                            effect_type=event.effect_type,
                            parameters=event.parameters,
                            buffer_style=event.buffer_style,
                            buffer_transform=event.buffer_transform,
                            palette=event.palette,
                            intensity=event.intensity,
                            transition_in=event.transition_in,
                            transition_out=event.transition_out,
                            source=event.source,
                        )
                    else:
                        # Event fully eclipsed, skip it
                        continue

            resolved.append(event)

        return resolved

    @staticmethod
    def _collect_target_ids(
        coordination_plans: list[CoordinationPlan],
    ) -> list[str]:
        """Collect all target IDs referenced in coordination plans.

        Args:
            coordination_plans: List of coordination plans.

        Returns:
            List of unique target IDs.
        """
        seen: set[str] = set()
        result: list[str] = []
        for cp in coordination_plans:
            for t in cp.targets:
                if t.id not in seen:
                    seen.add(t.id)
                    result.append(t.id)
        return result

    def _build_groups(
        self,
        element_layers: dict[str, dict[int, list[RenderEvent]]],
    ) -> list[RenderGroupPlan]:
        """Build RenderGroupPlan list from accumulated data.

        Args:
            element_layers: element_name → layer_index → events.

        Returns:
            List of RenderGroupPlan.
        """
        groups: list[RenderGroupPlan] = []

        for element_name in sorted(element_layers.keys()):
            layers_dict = element_layers[element_name]
            layers: list[RenderLayerPlan] = []

            for layer_idx in sorted(layers_dict.keys()):
                events = layers_dict[layer_idx]
                if not events:
                    continue

                # Infer layer role from events
                roles = {e.source.lane for e in events}
                layer_role = roles.pop() if len(roles) == 1 else LaneKind.BASE

                # Look up blend mode from tracked data
                blend_key = (element_name, layer_idx)
                blend_mode = self._layer_blend_modes.get(blend_key, "Normal")

                layers.append(
                    RenderLayerPlan(
                        layer_index=layer_idx,
                        layer_role=layer_role,
                        blend_mode=blend_mode,
                        events=events,
                    )
                )

            if layers:
                groups.append(
                    RenderGroupPlan(
                        element_name=element_name,
                        layers=layers,
                    )
                )

        return groups


__all__ = [
    "CompositionEngine",
]
