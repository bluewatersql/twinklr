"""XSQ writer: applies a RenderPlan to an XSequence.

Takes the RenderPlan (from CompositionEngine) and the rendered
EffectSettings (from EffectHandlers) and writes them into an
XSequence model. The XSequence can then be exported to .xsq
via the existing XSQExporter.
"""

from __future__ import annotations

import logging
from typing import TypedDict

from twinklr.core.formats.xlights.sequence.models.xsq import (
    ColorPalette,
    Effect,
    XSequence,
)
from twinklr.core.sequencer.display.effects.protocol import (
    RenderContext,
)
from twinklr.core.sequencer.display.effects.registry import HandlerRegistry
from twinklr.core.sequencer.display.effects.settings_builder import (
    SettingsStringBuilder,
)
from twinklr.core.sequencer.display.export.effectdb_registry import (
    EffectDBRegistry,
)
from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.display.models.render_event import RenderEvent
from twinklr.core.sequencer.display.models.render_plan import (
    RenderGroupPlan,
    RenderLayerPlan,
    RenderPlan,
)
from twinklr.core.sequencer.display.palette.builder import build_palette_string
from twinklr.core.sequencer.display.palette.registry import PaletteDBRegistry

logger = logging.getLogger(__name__)


class XSQTraceEntry(TypedDict):
    """Per-effect trace record for display XSQ sidecar metadata."""

    event_id: str
    placement_id: str | None
    placement_index: int
    section_id: str
    lane: str
    group_id: str
    template_id: str
    element_name: str
    layer_index: int
    effect_name: str
    start_ms: int
    end_ms: int


class WriteResult:
    """Result of writing a RenderPlan to an XSequence.

    Attributes:
        effects_written: Number of effects placed.
        elements_created: Number of elements created/used.
        effectdb_entries: Number of EffectDB entries registered.
        palette_entries: Number of palette entries registered.
        warnings: Non-fatal warnings from rendering.
        missing_assets: Asset paths that were not found.
    """

    def __init__(self) -> None:
        self.effects_written: int = 0
        self.elements_created: int = 0
        self.effectdb_entries: int = 0
        self.palette_entries: int = 0
        self.warnings: list[str] = []
        self.missing_assets: list[str] = []
        self.trace_entries: list[XSQTraceEntry] = []


class XSQWriter:
    """Writes a RenderPlan into an XSequence.

    Coordinates the EffectHandler dispatch, EffectDB/Palette
    registration, and Effect placement on elements.

    Args:
        handler_registry: Registry of effect handlers.
        render_context: Rendering context for handlers.
    """

    def __init__(
        self,
        handler_registry: HandlerRegistry,
        render_context: RenderContext,
    ) -> None:
        self._handlers = handler_registry
        self._ctx = render_context

    def write(
        self,
        render_plan: RenderPlan,
        sequence: XSequence,
    ) -> WriteResult:
        """Write a RenderPlan into an XSequence.

        For each event in the RenderPlan:
        1. Dispatch to the appropriate EffectHandler → EffectSettings
        2. Build palette string via PaletteBuilder
        3. Register settings/palette in dedup registries → get indices
        4. Create Effect and add to the element's layer

        Args:
            render_plan: Composed render plan.
            sequence: XSequence to mutate with effects.

        Returns:
            WriteResult with statistics and warnings.
        """
        result = WriteResult()
        effectdb_reg = EffectDBRegistry(reserve_zero=True)
        palette_reg = PaletteDBRegistry()

        # Process each element group
        for group_plan in render_plan.groups:
            self._write_group(
                group_plan=group_plan,
                sequence=sequence,
                effectdb_reg=effectdb_reg,
                palette_reg=palette_reg,
                result=result,
            )

        # Sync registries to XSequence
        self._sync_effectdb(effectdb_reg, sequence)
        self._sync_palettes(palette_reg, sequence)

        result.effectdb_entries = len(effectdb_reg)
        result.palette_entries = len(palette_reg)

        logger.info(
            "XSQWriter: wrote %d effects on %d elements (%d effectdb, %d palettes, %d warnings)",
            result.effects_written,
            result.elements_created,
            result.effectdb_entries,
            result.palette_entries,
            len(result.warnings),
        )

        return result

    def _write_group(
        self,
        group_plan: RenderGroupPlan,
        sequence: XSequence,
        effectdb_reg: EffectDBRegistry,
        palette_reg: PaletteDBRegistry,
        result: WriteResult,
    ) -> None:
        """Write a single element group into the sequence.

        Layers are compacted to sequential indices (0, 1, 2, ...)
        with no gaps. The original ``layer_plan.layer_index`` may have
        gaps (e.g., BASE=0, ACCENT=2 with no RHYTHM), but the XSQ
        output only emits layers that have effects. Relative ordering
        is preserved (lower original index → lower compact index).

        Args:
            group_plan: Render plan for one element.
            sequence: XSequence to mutate.
            effectdb_reg: EffectDB dedup registry.
            palette_reg: Palette dedup registry.
            result: Result accumulator.
        """
        element_name = group_plan.element_name
        sequence.ensure_element(element_name)
        result.elements_created += 1

        # Layers are already sorted by layer_index from the engine.
        # Compact indices: skip empty gaps, emit sequentially.
        for compact_idx, layer_plan in enumerate(group_plan.layers):
            for event in layer_plan.events:
                self._write_event(
                    event=event,
                    element_name=element_name,
                    layer_index=compact_idx,
                    layer_plan=layer_plan,
                    sequence=sequence,
                    effectdb_reg=effectdb_reg,
                    palette_reg=palette_reg,
                    result=result,
                )

    def _write_event(
        self,
        event: RenderEvent,
        element_name: str,
        layer_index: int,
        layer_plan: RenderLayerPlan,
        sequence: XSequence,
        effectdb_reg: EffectDBRegistry,
        palette_reg: PaletteDBRegistry,
        result: WriteResult,
    ) -> None:
        """Write a single render event as an xLights Effect.

        After the EffectHandler produces its E_/B_ settings, this method
        appends cross-cutting T_ keys:
        - ``T_CHOICE_LayerMethod`` for blend mode (layer > 0 only)
        - ``T_TEXTCTRL_Fadein/Fadeout`` + transition type/adjust for fades

        Args:
            event: Render event to write.
            element_name: Target element name.
            layer_index: Target layer index.
            layer_plan: Parent layer plan (carries blend_mode).
            sequence: XSequence to mutate.
            effectdb_reg: EffectDB dedup registry.
            palette_reg: Palette dedup registry.
            result: Result accumulator.
        """
        # 1. Dispatch to handler → E_/B_ keys
        settings = self._handlers.dispatch(event, self._ctx)

        # Collect warnings and missing assets
        result.warnings.extend(settings.warnings)
        result.missing_assets.extend(settings.requires_assets)

        # 2. Augment with cross-cutting T_ keys
        augmented = self._augment_settings(
            settings.settings_string,
            event=event,
            layer_index=layer_index,
            blend_mode=layer_plan.blend_mode,
        )

        # 3. Register augmented settings in EffectDB
        effectdb_idx = effectdb_reg.register(augmented)

        # 4. Build and register palette (with intensity-based brightness)
        palette = self._apply_intensity_brightness(
            event.palette, event.intensity, settings.effect_name
        )
        palette_string = build_palette_string(palette)
        palette_idx = palette_reg.register(palette_string)

        # 5. Create Effect and add to sequence
        effect = Effect(
            effect_type=settings.effect_name,
            start_time_ms=event.start_ms,
            end_time_ms=event.end_ms,
            palette=str(palette_idx),
            ref=effectdb_idx,
        )

        sequence.add_effect(element_name, effect, layer_index=layer_index)
        result.effects_written += 1
        self._append_trace_entry(
            result=result,
            event=event,
            element_name=element_name,
            layer_index=layer_index,
            effect_name=settings.effect_name,
        )

    @staticmethod
    def _append_trace_entry(
        *,
        result: WriteResult,
        event: RenderEvent,
        element_name: str,
        layer_index: int,
        effect_name: str,
    ) -> None:
        """Append a trace sidecar entry for a written effect."""
        source = event.source
        result.trace_entries.append(
            {
                "event_id": event.event_id,
                "placement_id": source.placement_id,
                "placement_index": source.placement_index,
                "section_id": source.section_id,
                "lane": source.lane.value,
                "group_id": source.group_id,
                "template_id": source.template_id,
                "element_name": element_name,
                "layer_index": layer_index,
                "effect_name": effect_name,
                "start_ms": event.start_ms,
                "end_ms": event.end_ms,
            }
        )

    @staticmethod
    def _augment_settings(
        base_settings: str,
        *,
        event: RenderEvent,
        layer_index: int,
        blend_mode: str,
    ) -> str:
        """Append transition and blend-mode T_ keys to a settings string.

        This keeps cross-cutting concerns out of individual EffectHandlers.

        Args:
            base_settings: Handler-produced settings string (E_/B_ keys).
            event: Render event (carries transition specs).
            layer_index: Compact layer index in the element.
            blend_mode: xLights blend mode for this layer.

        Returns:
            Settings string with T_ keys appended.
        """
        extra = SettingsStringBuilder()

        # Blend mode — only meaningful for layers above the base
        if layer_index > 0 and blend_mode != "Normal":
            extra.add_layer_method(blend_mode)

        # Fade-in transition
        if event.transition_in is not None:
            seconds = event.transition_in.duration_ms / 1000.0
            extra.add_fade_in(
                seconds=seconds,
                transition_type=event.transition_in.type,
                adjust=event.transition_in.adjust,
                reverse=event.transition_in.reverse,
            )

        # Fade-out transition
        if event.transition_out is not None:
            seconds = event.transition_out.duration_ms / 1000.0
            extra.add_fade_out(
                seconds=seconds,
                transition_type=event.transition_out.type,
                adjust=event.transition_out.adjust,
                reverse=event.transition_out.reverse,
            )

        # Value curves — animated parameters from template compilation
        if event.value_curves:
            extra.add_value_curves(event.value_curves)

        suffix = extra.build()
        if not suffix:
            return base_settings
        if not base_settings:
            return suffix
        return f"{base_settings},{suffix}"

    @staticmethod
    def _apply_intensity_brightness(
        palette: ResolvedPalette,
        intensity: float,
        effect_name: str,
    ) -> ResolvedPalette:
        """Map event intensity to xLights palette brightness.

        Applies intensity (0.0-1.0) as ``C_SLIDER_Brightness`` (0-100)
        on the palette.  This is a cross-cutting concern — like
        transitions — applied universally for all non-On effects.

        **On** effects are skipped because they handle intensity
        through their own ``E_TEXTCTRL_Eff_On_Start/End`` keys;
        applying palette brightness as well would double-attenuate.

        If the palette already carries a brightness value, intensity
        is composed (multiplied) with it.

        Args:
            palette: Resolved color palette.
            intensity: Event intensity (0.0-1.0).
            effect_name: xLights effect type name.

        Returns:
            Palette with brightness applied, or the original palette
            if no adjustment is needed.
        """
        # On effects handle intensity via their own E_ parameters
        if effect_name == "On":
            return palette

        # Full intensity needs no brightness override
        if intensity >= 1.0:
            return palette

        # Compose with any existing brightness
        base_brightness = palette.brightness if palette.brightness is not None else 100
        effective = max(0, min(100, int(base_brightness * intensity)))
        return palette.model_copy(update={"brightness": effective})

    def _sync_effectdb(
        self,
        effectdb_reg: EffectDBRegistry,
        sequence: XSequence,
    ) -> None:
        """Sync the EffectDB registry entries into the XSequence.

        Replaces the XSequence's EffectDB with the registry contents.

        Args:
            effectdb_reg: Populated EffectDB registry.
            sequence: XSequence to update.
        """
        from twinklr.core.formats.xlights.sequence.models.xsq import EffectDB

        sequence.effect_db = EffectDB(entries=effectdb_reg.get_entries())

    def _sync_palettes(
        self,
        palette_reg: PaletteDBRegistry,
        sequence: XSequence,
    ) -> None:
        """Sync the palette registry entries into the XSequence.

        Replaces the XSequence's color_palettes with registry contents.

        Args:
            palette_reg: Populated palette registry.
            sequence: XSequence to update.
        """
        sequence.color_palettes = [ColorPalette(settings=s) for s in palette_reg.get_entries()]


__all__ = [
    "WriteResult",
    "XSQTraceEntry",
    "XSQWriter",
]
