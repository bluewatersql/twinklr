"""XSQ Parser - Parse xLights sequence files into Pydantic models.

This parser reads xLights .xsq (XML Sequence) files and converts them
into type-safe Pydantic models for manipulation and validation.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from twinklr.core.formats.xlights.sequence.models.xsq import (
    ColorPalette,
    Effect,
    EffectDB,
    EffectLayer,
    ElementEffects,
    SequenceHead,
    TimeMarker,
    TimingTrack,
    XSequence,
)
from twinklr.core.parsers.xml import XMLParser
from twinklr.core.utils.logging import get_logger

logger = get_logger(__name__)


class XSQParser:
    """Parser for xLights sequence files (.xsq).

    Parses XML-based xLights sequences into structured Pydantic models
    with full validation and type safety.

    Example:
        >>> parser = XSQParser()
        >>> sequence = parser.parse("show.xsq")
        >>> print(f"Duration: {sequence.sequence_duration_ms}ms")
        >>> print(f"Elements: {len(sequence.element_effects)}")
    """

    def __init__(self):
        """Initialize XSQ parser."""
        self._xml_parser = XMLParser()

    def parse(self, file_path: Path | str) -> XSequence:
        """Parse XSQ file from disk.

        Args:
            file_path: Path to .xsq file

        Returns:
            Parsed XSequence model

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If XML is invalid or missing required fields
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"XSQ file not found: {file_path}")

        logger.debug(f"Parsing XSQ file: {file_path}")

        try:
            tree = self._xml_parser.parse(file_path)
            return self._parse_tree(tree)
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML in {file_path}: {e}") from e

    def parse_string(self, xml_content: str) -> XSequence:
        """Parse XSQ from XML string.

        Args:
            xml_content: XML content as string

        Returns:
            Parsed XSequence model

        Raises:
            ValueError: If XML is invalid or missing required fields
        """
        logger.debug("Parsing XSQ from string")

        try:
            root = self._xml_parser.parse_string(xml_content)
            # Convert Element to ElementTree for consistent handling
            tree: ET.ElementTree[ET.Element[str]] = ET.ElementTree(root)
            return self._parse_tree(tree)
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML: {e}") from e

    def _parse_tree(self, tree: ET.ElementTree[ET.Element[str]]) -> XSequence:
        """Parse ElementTree into XSequence model.

        Args:
            tree: Parsed XML tree

        Returns:
            XSequence model

        Raises:
            ValueError: If required fields are missing
        """
        root = tree.getroot()
        if root is None:
            raise ValueError("XML tree has no root element")

        # Parse root attributes
        base_channel = int(root.get("BaseChannel", "0"))
        chan_ctrl_basic = int(root.get("ChanCtrlBasic", "0"))
        chan_ctrl_color = int(root.get("ChanCtrlColor", "0"))
        fixed_point_timing = root.get("FixedPointTiming", "1") == "1"
        model_blending = root.get("ModelBlending", "true").lower() == "true"

        # Parse head section
        head_elem = root.find("head")
        if head_elem is None:
            raise ValueError("Missing required <head> section")

        head = self._parse_head(head_elem)

        # Parse optional sections
        next_id = int(root.findtext("nextid", "1"))
        effect_db = self._parse_effectdb(root)
        color_palettes = self._parse_color_palettes(root)

        # Parse timing tracks and effects
        timing_tracks = self._parse_timing_tracks(root)
        element_effects = self._parse_element_effects(root)

        # Ensure all DisplayElements models are represented in element_effects
        # This preserves models from the template even if they have no effects
        element_effects = self._ensure_all_display_elements(root, element_effects)

        return XSequence(
            base_channel=base_channel,
            chan_ctrl_basic=chan_ctrl_basic,
            chan_ctrl_color=chan_ctrl_color,
            fixed_point_timing=fixed_point_timing,
            model_blending=model_blending,
            head=head,
            next_id=next_id,
            effect_db=effect_db,
            color_palettes=color_palettes,
            timing_tracks=timing_tracks,
            element_effects=element_effects,
        )

    def _parse_head(self, head_elem: ET.Element) -> SequenceHead:
        """Parse head section.

        Args:
            head_elem: Head XML element

        Returns:
            SequenceHead model

        Raises:
            ValueError: If required fields are missing
        """
        version = head_elem.findtext("version")
        if not version:
            raise ValueError("Missing required field: version")

        media_file = head_elem.findtext("mediaFile") or head_elem.findtext("MediaFile")
        if not media_file:
            raise ValueError("Missing required field: mediaFile/MediaFile")

        sequence_duration_text = head_elem.findtext("sequenceDuration")
        if not sequence_duration_text:
            raise ValueError("Missing required field: sequenceDuration")

        try:
            # Convert seconds to milliseconds
            sequence_duration_ms = int(float(sequence_duration_text) * 1000)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid sequenceDuration value: {sequence_duration_text}") from e

        return SequenceHead(
            version=version,
            author=head_elem.findtext("author", ""),
            author_email=head_elem.findtext("author-email", ""),
            author_website=head_elem.findtext("author-website", ""),
            song=head_elem.findtext("song", ""),
            artist=head_elem.findtext("artist", ""),
            album=head_elem.findtext("album", ""),
            music_url=head_elem.findtext("MusicURL", ""),
            comment=head_elem.findtext("comment", ""),
            sequence_timing=head_elem.findtext("sequenceTiming", "50 ms"),
            sequence_type=head_elem.findtext("sequenceType", "Media"),
            media_file=media_file,
            sequence_duration_ms=sequence_duration_ms,
            image_dir=head_elem.findtext("imageDir", ""),
        )

    def _parse_effectdb(self, root: ET.Element) -> EffectDB:
        """Parse EffectDB section.

        Args:
            root: Root XML element

        Returns:
            EffectDB model
        """
        effectdb_elem = root.find("EffectDB")
        if effectdb_elem is None:
            return EffectDB()

        entries = []
        for effect_elem in effectdb_elem.findall("Effect"):
            settings = effect_elem.text or ""
            entries.append(settings)

        return EffectDB(entries=entries)

    def _parse_color_palettes(self, root: ET.Element) -> list[ColorPalette]:
        """Parse ColorPalettes section.

        Args:
            root: Root XML element

        Returns:
            List of ColorPalette models
        """
        palettes_elem = root.find("ColorPalettes")
        if palettes_elem is None:
            return []

        palettes = []
        for palette_elem in palettes_elem.findall("ColorPalette"):
            settings = palette_elem.text or ""
            palettes.append(ColorPalette(settings=settings))

        return palettes

    def _parse_timing_tracks(self, root: ET.Element) -> list[TimingTrack]:
        """Parse timing tracks from ElementEffects.

        Args:
            root: Root XML element

        Returns:
            List of TimingTrack models
        """
        timing_tracks: list[TimingTrack] = []

        element_effects = root.find("ElementEffects")
        if element_effects is None:
            return timing_tracks

        for element in element_effects.findall("Element"):
            element_type = element.get("type")
            if element_type != "timing":
                continue

            element_name = element.get("name", "")
            markers = []

            # Parse effects as timing markers
            for layer in element.findall("EffectLayer"):
                for effect in layer.findall("Effect"):
                    marker = self._parse_timing_marker(effect)
                    if marker:
                        markers.append(marker)

            if element_name:  # Only add if has a name
                timing_track = TimingTrack(name=element_name, type="timing", markers=markers)
                timing_tracks.append(timing_track)

        return timing_tracks

    def _parse_timing_marker(self, effect: ET.Element) -> TimeMarker | None:
        """Parse timing marker from Effect element.

        Args:
            effect: Effect XML element

        Returns:
            TimeMarker or None if invalid
        """
        label = effect.get("label", "")
        start_time = effect.get("startTime")
        end_time = effect.get("endTime")

        if start_time is None:
            return None

        try:
            time_ms = int(start_time)
            # Position is normalized time (0.0 to 1.0)
            # We'll use time_ms directly since we don't know total duration here
            position = float(time_ms) / 1000.0  # Approximate

            # Parse end_time_ms if present
            end_time_ms = None
            if end_time is not None:
                end_time_ms = int(end_time)
                # Only store if different from default (start + 1ms)
                if end_time_ms == time_ms + 1:
                    end_time_ms = None  # Use default behavior

            return TimeMarker(
                name=label, time_ms=time_ms, position=position, end_time_ms=end_time_ms
            )
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping invalid timing marker: {start_time}, error: {e}")
            return None

    def _parse_element_effects(self, root: ET.Element) -> list[ElementEffects]:
        """Parse element effects (non-timing elements).

        Args:
            root: Root XML element

        Returns:
            List of ElementEffects models
        """
        element_effects_list: list[ElementEffects] = []

        element_effects_section = root.find("ElementEffects")
        if element_effects_section is None:
            return element_effects_list

        for element in element_effects_section.findall("Element"):
            element_type = element.get("type", "model")

            # Skip timing tracks (handled separately)
            if element_type == "timing":
                continue

            element_name = element.get("name", "")
            if not element_name:
                continue

            # Parse effect layers
            layers = self._parse_effect_layers(element)

            element_effects = ElementEffects(
                element_name=element_name, element_type=element_type, layers=layers
            )
            element_effects_list.append(element_effects)

        return element_effects_list

    def _ensure_all_display_elements(
        self, root: ET.Element, element_effects: list[ElementEffects]
    ) -> list[ElementEffects]:
        """Ensure all DisplayElements models are represented in element_effects.

        This preserves all models from the template, even if they have no effects.
        Models are added with empty effect layers if not already present.

        Args:
            root: Root XML element
            element_effects: Existing element effects list

        Returns:
            Updated element effects list with all display elements
        """
        # Get existing element names
        existing_names = {e.element_name for e in element_effects}

        # Parse DisplayElements section
        display_elements_section = root.find("DisplayElements")
        if display_elements_section is None:
            return element_effects

        # Add missing models from DisplayElements
        for element in display_elements_section.findall("Element"):
            element_type = element.get("type", "model")
            element_name = element.get("name", "")

            # Skip timing tracks and elements without names
            if element_type == "timing" or not element_name:
                continue

            # Add if not already present
            if element_name not in existing_names:
                element_effects.append(
                    ElementEffects(
                        element_name=element_name,
                        element_type=element_type,
                        layers=[EffectLayer(index=0, name="", effects=[])],
                    )
                )
                logger.debug(f"Preserved model from DisplayElements: {element_name}")

        return element_effects

    def _parse_effect_layers(self, element: ET.Element) -> list[EffectLayer]:
        """Parse effect layers from element.

        Args:
            element: Element XML element

        Returns:
            List of EffectLayer models
        """
        layers = []

        for layer_index, layer_elem in enumerate(element.findall("EffectLayer")):
            effects = []

            for effect_elem in layer_elem.findall("Effect"):
                effect = self._parse_effect(effect_elem)
                if effect:
                    effects.append(effect)

            # Create layer
            layer = EffectLayer(index=layer_index, name=layer_elem.get("name", ""), effects=effects)
            layers.append(layer)

        return layers

    def _parse_effect(self, effect_elem: ET.Element) -> Effect | None:
        """Parse effect from Effect element.

        Args:
            effect_elem: Effect XML element

        Returns:
            Effect model or None if invalid
        """
        effect_name = effect_elem.get("name", "")
        start_time = effect_elem.get("startTime")
        end_time = effect_elem.get("endTime")

        if not effect_name or start_time is None or end_time is None:
            logger.warning("Skipping effect with missing required fields")
            return None

        try:
            start_time_ms = int(start_time)
            end_time_ms = int(end_time)
        except (ValueError, TypeError):
            logger.warning(f"Skipping effect with invalid time values: {start_time}, {end_time}")
            return None

        # Parse optional fields
        palette = effect_elem.get("palette", "0")
        protected_str = effect_elem.get("protected", "0")
        protected = protected_str == "1"

        # Parse ref attribute (EffectDB reference)
        ref_str = effect_elem.get("ref")
        ref = int(ref_str) if ref_str is not None and ref_str.isdigit() else None

        # Parse label attribute
        label = effect_elem.get("label")

        # Parse all other attributes as parameters
        parameters = self._parse_effect_parameters(effect_elem)

        return Effect(
            effect_type=effect_name,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            palette=palette,
            protected=protected,
            ref=ref,
            label=label,
            parameters=parameters,
        )

    def _parse_effect_parameters(self, effect_elem: ET.Element) -> dict[str, Any]:
        """Parse effect parameters from element attributes.

        Args:
            effect_elem: Effect XML element

        Returns:
            Dictionary of parameters
        """
        # Standard attributes that are not parameters
        standard_attrs = {
            "name",
            "startTime",
            "endTime",
            "palette",
            "protected",
            "ref",
            "label",
        }

        parameters = {}
        for key, value in effect_elem.attrib.items():
            if key not in standard_attrs:
                parameters[key] = value

        return parameters
