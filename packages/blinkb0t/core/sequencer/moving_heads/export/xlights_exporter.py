"""xLights Exporter for the moving head sequencer.

Converts IR segments (TemplateCompileResult) to xLights sequence format.
Handles conversion of curves to DMX values and generates xLights XML.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from blinkb0t.core.sequencer.moving_heads.compile.template_compiler import (
    TemplateCompileResult,
)
from blinkb0t.core.sequencer.moving_heads.export.dmx_converter import (
    convert_segment_to_dmx,
)
from blinkb0t.core.sequencer.moving_heads.export.xlights_models import (
    Effect,
    ElementEffects,
    SequenceHead,
    XLightsSequence,
)
from blinkb0t.core.sequencer.moving_heads.models.channel import ChannelName
from blinkb0t.core.sequencer.moving_heads.models.ir import ChannelSegment

# Default channel numbers for each channel type
DEFAULT_CHANNEL_NUMBERS = {
    ChannelName.PAN: 1,
    ChannelName.TILT: 2,
    ChannelName.DIMMER: 3,
}


def segment_to_effect(segment: ChannelSegment, channel_num: int) -> Effect:
    """Convert an IR segment to an xLights Effect.

    Converts the segment's curve to DMX values and formats as
    xLights value curve string.

    Args:
        segment: IR ChannelSegment to convert.
        channel_num: DMX channel number for value curve ID.

    Returns:
        xLights Effect with value curve.

    Example:
        >>> effect = segment_to_effect(segment, channel_num=11)
    """
    # Convert curve to DMX values
    dmx_curve = convert_segment_to_dmx(segment)

    # Generate xLights value curve string
    curve_str = dmx_curve.to_xlights_string(channel_num)

    # Create effect with value curve
    return Effect(
        effect_type="DMX",
        start_time_ms=segment.t0_ms,
        end_time_ms=segment.t1_ms,
        value_curves={f"DMX{channel_num}": curve_str},
        palette_ref=None,
        effectdb_ref=None,
    )


def segments_to_element(
    element_name: str,
    segments: list[ChannelSegment],
    channel_map: dict[ChannelName, int],
) -> ElementEffects:
    """Convert segments for a fixture to an xLights ElementEffects.

    Groups segments by time and creates effects with appropriate
    value curves.

    Args:
        element_name: Name of the xLights element (fixture name).
        segments: List of segments for this fixture.
        channel_map: Mapping of channel names to DMX channel numbers.

    Returns:
        ElementEffects with all effects.

    Example:
        >>> channel_map = {ChannelName.DIMMER: 12}
        >>> element = segments_to_element("MH_1", segments, channel_map)
    """
    element = ElementEffects(element_name=element_name)

    for segment in segments:
        # Get channel number (use default if not in map)
        channel_num = channel_map.get(
            segment.channel,
            DEFAULT_CHANNEL_NUMBERS.get(segment.channel, 1),
        )

        # Convert segment to effect
        effect = segment_to_effect(segment, channel_num)

        # Add to element
        element.add_effect(effect, layer_index=0)

    return element


def compile_result_to_sequence(
    result: TemplateCompileResult,
    head: SequenceHead,
    channel_map: dict[str, dict[ChannelName, int]],
) -> XLightsSequence:
    """Convert a TemplateCompileResult to an XLightsSequence.

    Groups segments by fixture and converts each to an element
    with effects.

    Args:
        result: Compiled template result with IR segments.
        head: Sequence header/metadata.
        channel_map: Nested mapping of fixture_id -> channel_name -> channel_num.

    Returns:
        XLightsSequence ready for export.

    Example:
        >>> channel_map = {
        ...     "fixture_1": {ChannelName.PAN: 11, ChannelName.DIMMER: 13},
        ... }
        >>> sequence = compile_result_to_sequence(result, head, channel_map)
    """
    sequence = XLightsSequence(head=head)

    # Group segments by fixture_id
    segments_by_fixture: dict[str, list[ChannelSegment]] = {}
    for segment in result.segments:
        if segment.fixture_id not in segments_by_fixture:
            segments_by_fixture[segment.fixture_id] = []
        segments_by_fixture[segment.fixture_id].append(segment)

    # Convert each fixture's segments to an element
    for fixture_id, segments in segments_by_fixture.items():
        fixture_channel_map = channel_map.get(fixture_id, {})
        element = segments_to_element(fixture_id, segments, fixture_channel_map)
        sequence.elements.append(element)

    return sequence


class XLightsExporter:
    """Exporter for xLights sequence files (.xsq).

    Converts XLightsSequence models to XML and writes to file.

    Example:
        >>> exporter = XLightsExporter()
        >>> exporter.export(sequence, "output.xsq")
    """

    def export(
        self,
        sequence: XLightsSequence,
        file_path: Path | str,
        pretty: bool = True,
    ) -> None:
        """Export XLightsSequence to file.

        Args:
            sequence: XLightsSequence model to export.
            file_path: Path to output .xsq file.
            pretty: Whether to format with indentation.
        """
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        tree = self._build_tree(sequence)

        if pretty:
            ET.indent(tree, space="  ", level=0)

        tree.write(str(file_path), encoding="UTF-8", xml_declaration=True)

    def _build_tree(self, sequence: XLightsSequence) -> ET.ElementTree:
        """Build XML tree from XLightsSequence."""
        root = ET.Element(
            "xsequence",
            {
                "BaseChannel": "0",
                "ChanCtrlBasic": "0",
                "ChanCtrlColor": "0",
                "FixedPointTiming": "1",
                "ModelBlending": "true",
            },
        )

        # Build head section
        head = self._build_head(sequence.head)
        root.append(head)

        # Build nextid
        ET.SubElement(root, "nextid").text = "1"

        # Build Jukebox (empty element)
        ET.SubElement(root, "Jukebox")

        # Build ColorPalettes
        if sequence.color_palettes:
            color_palettes = ET.SubElement(root, "ColorPalettes")
            for palette in sequence.color_palettes:
                ET.SubElement(color_palettes, "ColorPalette").text = palette.settings

        # Build EffectDB
        effect_db = ET.SubElement(root, "EffectDB")
        for entry in sequence.effect_db.entries:
            ET.SubElement(effect_db, "Effect").text = entry

        # Build DisplayElements
        display_elements = self._build_display_elements(sequence)
        root.append(display_elements)

        # Build ElementEffects
        element_effects = self._build_element_effects(sequence)
        root.append(element_effects)

        return ET.ElementTree(root)

    def _build_head(self, head: SequenceHead) -> ET.Element:
        """Build head section."""
        head_elem = ET.Element("head")

        ET.SubElement(head_elem, "version").text = head.version
        ET.SubElement(head_elem, "author").text = head.author
        ET.SubElement(head_elem, "author-email").text = head.author_email
        ET.SubElement(head_elem, "song").text = head.song
        ET.SubElement(head_elem, "artist").text = head.artist
        ET.SubElement(head_elem, "album").text = head.album
        ET.SubElement(head_elem, "comment").text = head.comment
        ET.SubElement(head_elem, "sequenceTiming").text = head.sequence_timing
        ET.SubElement(head_elem, "sequenceType").text = head.sequence_type

        duration_seconds = head.sequence_duration_ms / 1000.0
        ET.SubElement(head_elem, "sequenceDuration").text = f"{duration_seconds:.3f}"

        ET.SubElement(head_elem, "mediaFile").text = head.media_file

        return head_elem

    def _build_display_elements(self, sequence: XLightsSequence) -> ET.Element:
        """Build DisplayElements section."""
        display_elements = ET.Element("DisplayElements")

        # Add timing tracks
        for timing_track in sequence.timing_tracks:
            ET.SubElement(
                display_elements,
                "Element",
                {"type": "timing", "name": timing_track.name, "visible": "1"},
            )

        # Add element effects
        for element in sequence.elements:
            ET.SubElement(
                display_elements,
                "Element",
                {"type": element.element_type, "name": element.element_name, "visible": "1"},
            )

        return display_elements

    def _build_element_effects(self, sequence: XLightsSequence) -> ET.Element:
        """Build ElementEffects section."""
        element_effects = ET.Element("ElementEffects")

        # Add timing tracks
        for timing_track in sequence.timing_tracks:
            element = ET.SubElement(
                element_effects,
                "Element",
                {"type": "timing", "name": timing_track.name},
            )
            layer = ET.SubElement(element, "EffectLayer")
            for marker in timing_track.markers:
                end_time = marker.end_time_ms or (marker.time_ms + 1)
                ET.SubElement(
                    layer,
                    "Effect",
                    {
                        "label": marker.label,
                        "startTime": str(marker.time_ms),
                        "endTime": str(end_time),
                    },
                )

        # Add element effects
        for elem_effects in sequence.elements:
            xml_elem = ET.SubElement(
                element_effects,
                "Element",
                {"type": elem_effects.element_type, "name": elem_effects.element_name},
            )
            for effect_layer in elem_effects.layers:
                layer_elem = ET.SubElement(xml_elem, "EffectLayer")
                for effect in effect_layer.effects:
                    effect_attribs: dict[str, str] = {
                        "name": effect.effect_type,
                        "startTime": str(effect.start_time_ms),
                        "endTime": str(effect.end_time_ms),
                    }
                    if effect.settings:
                        effect_attribs["settings"] = effect.settings
                    # Add value curves as attributes
                    for curve_name, curve_str in effect.value_curves.items():
                        effect_attribs[curve_name] = curve_str
                    ET.SubElement(layer_elem, "Effect", effect_attribs)

        return element_effects
