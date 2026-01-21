"""xLights sequence format provider.

Converts RenderedEffect objects to xLights XSQ file format.
Handles both Native curves (ValueCurveSpec) and Custom curves (point arrays).

Architecture:
    RenderedEffect (Native specs or rendered points)
        ↓
    XlightsProvider
        ↓
    xLights XSQ file

Key responsibilities:
- Convert RenderedEffect → EffectPlacement
- Handle both ValueCurveSpec (Native) and list[CurvePoint] (Custom)
- Use existing XlightsAdapter for curve formatting
- Use existing XSQParser/XSQExporter for file I/O
"""

from __future__ import annotations

import logging
from pathlib import Path

from blinkb0t.core.domains.sequencing.infrastructure.curves.xlights_adapter import (
    XLightsAdapter,
)
from blinkb0t.core.domains.sequencing.infrastructure.xsq import (
    EffectPlacement,
    XSequence,
    XSQExporter,
    XSQParser,
)
from blinkb0t.core.domains.sequencing.infrastructure.xsq.compat import (
    effect_placement_to_effect,
)
from blinkb0t.core.domains.sequencing.models.curves import (
    ValueCurveSpec,
)
from blinkb0t.core.domains.sequencing.models.xsq import SequenceHead, TimeMarker, TimingTrack
from blinkb0t.core.domains.sequencing.rendering.models import RenderedEffect

logger = logging.getLogger(__name__)


class XlightsProvider:
    """Convert rendered effects to xLights XSQ format.

    Handles both Native curves (ValueCurveSpec) and Custom curves (point arrays).
    Uses existing XlightsAdapter for curve formatting.

    Examples:
        >>> provider = XlightsProvider()
        >>> rendered = [RenderedEffect(...), ...]
        >>> fixtures = {"MH1": {"pan": 11, "tilt": 13, "dimmer": 15}}
        >>> provider.write_to_xsq(
        ...     rendered_effects=rendered,
        ...     output_path="output.xsq",
        ...     fixture_definitions=fixtures,
        ... )
    """

    def __init__(self):
        """Initialize XlightsProvider with existing adapters.

        Uses existing infrastructure:
        - XLightsAdapter: Formats Native/Custom curves to xLights strings
        - XSQParser: Reads xLights XSQ files
        - XSQExporter: Writes xLights XSQ files
        """
        self.adapter = XLightsAdapter()
        self.parser = XSQParser()
        self.exporter = XSQExporter()
        logger.debug("XlightsProvider initialized")

    def _convert_to_placements(
        self,
        rendered_effects: list[RenderedEffect],
        fixture_definitions: dict[str, dict],
        xsq: XSequence,
    ) -> list[EffectPlacement]:
        """Convert RenderedEffect objects to xLights EffectPlacement objects.

        Handles both Native curves (ValueCurveSpec) and Custom curves (point arrays).
        Builds DMX settings strings and adds them to EffectDB.

        Args:
            rendered_effects: List of rendered effects
            fixture_definitions: Map of fixture_id to DMX channel assignments
                Example: {
                    "MH1": {"pan": 11, "tilt": 13, "dimmer": 15, ...},
                    "MH2": {"pan": 21, "tilt": 23, "dimmer": 25, ...}
                }
            xsq: XSequence to add EffectDB entries to

        Returns:
            List of EffectPlacement objects for xLights

        Examples:
            >>> fixtures = {"MH1": {"pan": 11, "tilt": 13, "dimmer": 15}}
            >>> placements = provider._convert_to_placements(rendered, fixtures, xsq)
        """
        placements = []

        for effect in rendered_effects:
            fixture_id = effect.fixture_id

            # Get DMX channels for this fixture
            if fixture_id not in fixture_definitions:
                logger.warning(f"No fixture definition for {fixture_id}, skipping")
                continue

            channels_map = fixture_definitions[fixture_id]

            # Build DMX settings string for this effect
            settings_str = self._build_settings_string(effect, channels_map)

            # Add to EffectDB and get ref
            ref = xsq.append_effectdb(settings_str)

            # Get xLights model name (assume same as fixture_id for now)
            xlights_name = f"Dmx {fixture_id}"

            # Create EffectPlacement
            placement = EffectPlacement(
                element_name=xlights_name,
                effect_name="DMX",
                start_ms=effect.start_ms,
                end_ms=effect.end_ms,
                effect_label=effect.label or "",
                ref=ref,
                palette=0,
            )

            placements.append(placement)

        return placements

    def _build_settings_string(
        self,
        effect: RenderedEffect,
        channels_map: dict[str, int],
    ) -> str:
        """Build xLights DMX settings string from rendered effect.

        Similar to DmxSettingsBuilder but for RenderedEffect.

        Args:
            effect: Rendered effect with curve data
            channels_map: Map of channel names to DMX channel numbers

        Returns:
            Settings string like "B_CHOICE_BufferStyle=...,E_SLIDER_DMX11=0,E_VALUECURVE_DMX11=..."
        """
        # Collect channel curves and static values
        channel_curves: dict[int, str] = {}
        channel_sliders: dict[int, int] = {}  # For static values

        for channel_name in ["pan", "tilt", "dimmer", "shutter", "color", "gobo"]:
            channel_data = getattr(effect.rendered_channels, channel_name, None)
            if channel_data is None:
                continue

            dmx_channel = channels_map.get(channel_name)
            if dmx_channel is None:
                continue

            # Handle different channel data types
            if isinstance(channel_data, int):
                # Static value → use slider
                channel_sliders[dmx_channel] = channel_data
            elif isinstance(channel_data, ValueCurveSpec):
                # Native curve
                curve_str = self.adapter.native_to_xlights(channel_data, dmx_channel)
                channel_curves[dmx_channel] = curve_str
            elif isinstance(channel_data, list):
                # Custom curve (points)
                curve_str = self.adapter.custom_to_xlights(channel_data, dmx_channel)
                channel_curves[dmx_channel] = curve_str
            else:
                logger.warning(f"Unknown channel data type: {type(channel_data)}")
                continue

        # Determine max channel
        all_channels = set(channel_curves.keys()) | set(channel_sliders.keys())
        max_channel = max(all_channels) if all_channels else 16
        max_channel = ((max_channel + 15) // 16) * 16  # Round to nearest 16

        # Build settings parts
        parts: list[str] = []

        # 1. Buffer style
        parts.append("B_CHOICE_BufferStyle=Per Model Default")

        # 2. Inversion flags (all 0 for now - can be configured later)
        for ch in range(1, max_channel + 1):
            parts.append(f"E_CHECKBOX_INVDMX{ch}=0")

        # 3. Notebook
        parts.append("E_NOTEBOOK1=Channels 1-16")

        # 4. Sliders (static value for fixed channels, 0 for curve channels)
        for ch in range(1, max_channel + 1):
            if ch in channel_sliders:
                # Static value
                parts.append(f"E_SLIDER_DMX{ch}={channel_sliders[ch]}")
            else:
                # Curve or unused channel
                parts.append(f"E_SLIDER_DMX{ch}=0")

        # 5. Value curves (only for channels with curves, not static values)
        for ch, curve_str in channel_curves.items():
            parts.append(f"E_VALUECURVE_DMX{ch}={curve_str}")

        return ",".join(parts)

    def write_to_xsq(
        self,
        rendered_effects: list[RenderedEffect],
        output_path: str | Path,
        fixture_definitions: dict[str, dict],
        template_xsq: str | Path | None = None,
    ) -> None:
        """Write rendered effects to xLights XSQ file.

        Args:
            rendered_effects: List of rendered effects
            output_path: Path to output XSQ file
            fixture_definitions: Map of fixture_id to DMX channels
            template_xsq: Optional template XSQ file to extend

        Raises:
            FileNotFoundError: If template_xsq doesn't exist
            ValueError: If rendered_effects is empty

        Examples:
            >>> provider = XlightsProvider()
            >>> fixtures = {"MH1": {"pan": 11, "tilt": 13, "dimmer": 15}}
            >>> provider.write_to_xsq(
            ...     rendered_effects=rendered,
            ...     output_path="output.xsq",
            ...     fixture_definitions=fixtures,
            ...     template_xsq="template.xsq"
            ... )
        """
        if not rendered_effects:
            raise ValueError("Cannot write XSQ with empty rendered_effects list")

        output_path = Path(output_path)

        # Load template or create new sequence
        if template_xsq:
            template_path = Path(template_xsq)
            if not template_path.exists():
                raise FileNotFoundError(f"Template XSQ not found: {template_path}")

            logger.info(f"Loading template XSQ: {template_path}")
            sequence = self.parser.parse(template_path)
        else:
            logger.info("Creating new XSQ sequence")
            # Create minimal empty sequence
            # Calculate sequence duration from effects
            max_end_ms = max((e.end_ms for e in rendered_effects), default=0)
            head = SequenceHead(
                version="2024.10",
                media_file="rendered.wav",  # Placeholder media file
                sequence_duration_ms=max_end_ms,
            )
            sequence = XSequence(head=head)

        # Convert effects to placements
        logger.info(f"Converting {len(rendered_effects)} effects to placements")
        placements = self._convert_to_placements(rendered_effects, fixture_definitions, sequence)

        logger.info(f"Generated {len(placements)} effect placements")

        # Add placements to sequence
        for placement in placements:
            effect = effect_placement_to_effect(placement)
            sequence.add_effect(placement.element_name, effect, layer_index=0)

        # Add timing metadata track
        timing_track = self._create_timing_track(rendered_effects)
        if timing_track:
            sequence.timing_tracks.append(timing_track)
            logger.info(
                f"Added timing track '{timing_track.name}' with {len(timing_track.markers)} markers"
            )

        # Write to file
        logger.info(f"Writing XSQ to: {output_path}")
        self.exporter.export(sequence, output_path)

        logger.info(f"Successfully wrote {len(placements)} effects to {output_path}")

    def _create_timing_track(self, rendered_effects: list[RenderedEffect]) -> TimingTrack | None:
        """Create timing track with markers for sections and segments.

        Creates a "blinkb0t MH Timing" track with TimeMarkers for:
        - Section boundaries (start and end)
        - Segment boundaries (from effect metadata)

        Args:
            rendered_effects: List of rendered effects with metadata

        Returns:
            TimingTrack with markers, or None if no metadata available
        """
        if not rendered_effects:
            return None

        # Collect unique sections and segments from metadata
        sections: dict[str, tuple[int, int]] = {}  # section_id -> (start_ms, end_ms)

        for effect in rendered_effects:
            metadata = effect.metadata or {}

            print(f"Metadata: {metadata}")
            section_parts = metadata.get("segment_id", "").split("__")
            section_name = section_parts[0]

            if section_name:
                # Track section boundaries
                if section_name not in sections:
                    sections[section_name] = (effect.start_ms, effect.end_ms)
                else:
                    # Expand section boundaries
                    existing_start, existing_end = sections[section_name]
                    sections[section_name] = (
                        min(existing_start, effect.start_ms),
                        max(existing_end, effect.end_ms),
                    )

        # Create markers
        markers: list[TimeMarker] = []

        max_duration = max((e.end_ms for e in rendered_effects), default=1)

        # Add section markers with start and end times
        for section_id, (start_ms, end_ms) in sorted(sections.items()):
            # Section marker with full duration
            markers.append(
                TimeMarker(
                    name=section_id,
                    time_ms=int(start_ms),
                    position=start_ms / max_duration if max_duration > 0 else 0.0,
                    end_time_ms=int(end_ms),  # End time as offset from start
                )
            )

        print(f"Number of markers: {len(markers)}")
        # Sort markers by time
        markers.sort(key=lambda m: m.time_ms)

        if not markers:
            return None

        return TimingTrack(name="blinkb0t MH Timing", type="timing", markers=markers)

    def convert_to_placements(
        self,
        rendered_effects: list[RenderedEffect],
        fixture_definitions: dict[str, dict],
        xsq: XSequence,
    ) -> list[EffectPlacement]:
        """Public API: Convert rendered effects to xLights placements.

        Wrapper around _convert_to_placements for external use.

        Args:
            rendered_effects: List of rendered effects
            fixture_definitions: Map of fixture_id to DMX channels
            xsq: XSequence to add EffectDB entries to

        Returns:
            List of EffectPlacement objects

        Examples:
            >>> provider = XlightsProvider()
            >>> fixtures = {"MH1": {"pan": 11, "tilt": 13, "dimmer": 15}}
            >>> placements = provider.convert_to_placements(rendered, fixtures, xsq)
        """
        return self._convert_to_placements(rendered_effects, fixture_definitions, xsq)
