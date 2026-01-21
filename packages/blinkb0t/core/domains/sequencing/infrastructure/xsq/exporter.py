"""XSQ Exporter - Write XSequence models to xLights sequence files.

This exporter converts type-safe Pydantic XSequence models back into
xLights .xsq (XML Sequence) files with proper formatting.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from blinkb0t.core.domains.sequencing.models.xsq import (
    Effect,
    EffectLayer,
    ElementEffects,
    SequenceHead,
    TimeMarker,
    TimingTrack,
    XSequence,
)
from blinkb0t.core.utils.logging import get_logger

logger = get_logger(__name__)


class XSQExporter:
    """Exporter for xLights sequence files (.xsq).

    Converts XSequence Pydantic models into XML-based xLights sequences
    with proper structure and formatting.

    Example:
        >>> exporter = XSQExporter()
        >>> exporter.export(sequence, "output.xsq", pretty=True)
    """

    def export(self, sequence: XSequence, file_path: Path | str, pretty: bool = True) -> None:
        """Export XSequence to file.

        Args:
            sequence: XSequence model to export
            file_path: Path to output .xsq file
            pretty: Whether to format with indentation (default: True)
        """
        file_path = Path(file_path)

        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Exporting XSequence to: {file_path}")

        # Build XML tree
        tree = self._build_tree(sequence)

        # Pretty print if requested
        if pretty:
            try:
                ET.indent(tree, space="  ", level=0)
            except AttributeError:
                # Fallback for Python < 3.9
                pass

        # Write to file
        tree.write(str(file_path), encoding="UTF-8", xml_declaration=True)

        logger.debug(f"Successfully exported XSequence to {file_path}")

    def _build_tree(self, sequence: XSequence) -> ET.ElementTree:
        """Build XML tree from XSequence.

        Args:
            sequence: XSequence model

        Returns:
            ElementTree
        """
        # Create root element with attributes
        root = ET.Element(
            "xsequence",
            {
                "BaseChannel": str(sequence.base_channel),
                "ChanCtrlBasic": str(sequence.chan_ctrl_basic),
                "ChanCtrlColor": str(sequence.chan_ctrl_color),
                "FixedPointTiming": "1" if sequence.fixed_point_timing else "0",
                "ModelBlending": "true" if sequence.model_blending else "false",
            },
        )

        # Build head section
        head = self._build_head(sequence.head)
        root.append(head)

        # Build nextid
        ET.SubElement(root, "nextid").text = str(sequence.next_id)

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
        """Build head section of XSQ.

        Args:
            head: SequenceHead model

        Returns:
            Head element
        """
        head_elem = ET.Element("head")

        # Add all fields
        ET.SubElement(head_elem, "version").text = head.version
        ET.SubElement(head_elem, "author").text = head.author
        ET.SubElement(head_elem, "author-email").text = head.author_email
        ET.SubElement(head_elem, "author-website").text = head.author_website
        ET.SubElement(head_elem, "song").text = head.song
        ET.SubElement(head_elem, "artist").text = head.artist
        ET.SubElement(head_elem, "album").text = head.album
        ET.SubElement(head_elem, "MusicURL").text = head.music_url
        ET.SubElement(head_elem, "comment").text = head.comment
        ET.SubElement(head_elem, "sequenceTiming").text = head.sequence_timing
        ET.SubElement(head_elem, "sequenceType").text = head.sequence_type

        # Convert milliseconds to seconds (3 decimal places)
        duration_seconds = head.sequence_duration_ms / 1000.0
        ET.SubElement(head_elem, "sequenceDuration").text = f"{duration_seconds:.3f}"

        ET.SubElement(head_elem, "imageDir").text = head.image_dir
        ET.SubElement(head_elem, "mediaFile").text = head.media_file

        return head_elem

    def _build_display_elements(self, sequence: XSequence) -> ET.Element:
        """Build DisplayElements section.

        Args:
            sequence: XSequence model

        Returns:
            DisplayElements element
        """
        display_elements = ET.Element("DisplayElements")

        # Add timing tracks
        for timing_track in sequence.timing_tracks:
            ET.SubElement(
                display_elements,
                "Element",
                {"type": "timing", "name": timing_track.name, "visible": "1", "collapsed": "0"},
            )

        # Add element effects
        for element_effect in sequence.element_effects:
            ET.SubElement(
                display_elements,
                "Element",
                {
                    "type": element_effect.element_type,
                    "name": element_effect.element_name,
                    "visible": "1",
                    "collapsed": "0",
                },
            )

        return display_elements

    def _build_element_effects(self, sequence: XSequence) -> ET.Element:
        """Build ElementEffects section.

        Args:
            sequence: XSequence model

        Returns:
            ElementEffects element
        """
        element_effects = ET.Element("ElementEffects")

        # Add timing tracks first
        for timing_track in sequence.timing_tracks:
            element = self._build_timing_track_element(timing_track)
            element_effects.append(element)

        # Add element effects
        for element_effect in sequence.element_effects:
            element = self._build_element_effect(element_effect)
            element_effects.append(element)

        return element_effects

    def _build_timing_track_element(self, timing_track: TimingTrack) -> ET.Element:
        """Build timing track element.

        Args:
            timing_track: TimingTrack model

        Returns:
            Element
        """
        element = ET.Element("Element", {"type": "timing", "name": timing_track.name})

        # Create single effect layer with timing markers as effects
        layer = ET.SubElement(element, "EffectLayer")

        for marker in timing_track.markers:
            self._add_timing_marker_effect(layer, marker)

        return element

    def _add_timing_marker_effect(self, layer: ET.Element, marker: TimeMarker) -> None:
        """Add timing marker as an effect.

        Args:
            layer: EffectLayer element
            marker: TimeMarker model
        """
        # Timing markers are stored as effects with start/end times
        # Use end_time_ms if provided, otherwise default to start + 1ms
        if marker.end_time_ms is not None:
            end_time = marker.end_time_ms
        else:
            end_time = marker.time_ms + 1  # 1ms duration for point markers

        attribs = {
            "label": marker.name,
            "startTime": str(marker.time_ms),
            "endTime": str(end_time),
        }

        ET.SubElement(layer, "Effect", attribs)

    def _build_element_effect(self, element_effect: ElementEffects) -> ET.Element:
        """Build element effect.

        Args:
            element_effect: ElementEffects model

        Returns:
            Element
        """
        element = ET.Element(
            "Element", {"type": element_effect.element_type, "name": element_effect.element_name}
        )

        # Add effect layers
        for layer in element_effect.layers:
            layer_elem = self._build_effect_layer(layer)
            element.append(layer_elem)

        return element

    def _build_effect_layer(self, layer: EffectLayer) -> ET.Element:
        """Build effect layer.

        Args:
            layer: EffectLayer model

        Returns:
            EffectLayer element
        """
        layer_attribs = {}
        if layer.name:
            layer_attribs["name"] = layer.name

        layer_elem = ET.Element("EffectLayer", layer_attribs)

        # Add effects
        for effect in layer.effects:
            effect_elem = self._build_effect(effect)
            layer_elem.append(effect_elem)

        return layer_elem

    def _build_effect(self, effect: Effect) -> ET.Element:
        """Build effect element.

        Args:
            effect: Effect model

        Returns:
            Effect element
        """
        # Build attributes
        attribs = {
            "name": effect.effect_type,
            "startTime": str(effect.start_time_ms),
            "endTime": str(effect.end_time_ms),
        }

        # Add palette if not default
        if effect.palette and effect.palette != "0":
            attribs["palette"] = effect.palette

        # Add protected flag if True
        if effect.protected:
            attribs["protected"] = "1"

        # Add ref if present
        if effect.ref is not None:
            attribs["ref"] = str(effect.ref)

        # Add label if present
        if effect.label is not None:
            attribs["label"] = effect.label

        # Add custom parameters
        for key, value in effect.parameters.items():
            attribs[key] = str(value)

        return ET.Element("Effect", attribs)
