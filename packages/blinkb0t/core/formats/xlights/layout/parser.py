from pathlib import Path
from typing import Any

from blinkb0t.core.formats.xlights.layout.models.rgb_effects import (
    Layout,
    ModelGroups,
    Models,
    Settings,
    Viewpoints,
)
from blinkb0t.core.utils.logging import get_logger
from blinkb0t.core.utils.xml import XMLParser

logger = get_logger(__name__)


class LayoutParser:
    """Parser that only parses known semantic models.

    Unknown XML elements are silently skipped. If you want to parse
    something, add a Pydantic model for it above.

    Example:
        >>> parser = LayoutParser()
        >>> layout = parser.parse("xlights_rgbeffects.xml")
        >>> # Only models, modelGroups, settings, viewpoints are parsed
        >>> # Everything else (colors, perspectives, etc.) is ignored
    """

    # Define which XML elements map to which Pydantic models
    KNOWN_TYPES = {
        "models": Models,
        "modelGroups": ModelGroups,
        "settings": Settings,
        "Viewpoints": Viewpoints,
        # Add more here as you create models for them
        # "colors": Colors,
        # "perspectives": Perspectives,
        # etc.
    }

    def __init__(self) -> None:
        """Initialize the parser."""
        self.xml_parser = XMLParser()

    def parse(self, file_path: Path | str) -> Layout:
        """Parse an xLights RGB Effects XML file.

        Only parses elements with defined Pydantic models.
        Unknown elements are silently ignored.

        Args:
            file_path: Path to xlights_rgbeffects.xml file

        Returns:
            Parsed Layout model (with only known sections populated)

        Example:
            >>> parser = LayoutParser()
            >>> layout = parser.parse("xlights_rgbeffects.xml")
            >>> print(len(layout.models.model))  # Works
            >>> print(layout.colors)  # None - not defined in KNOWN_TYPES
        """
        logger.debug(f"Parsing xLights layout from: {file_path}")
        tree = self.xml_parser.parse(file_path)
        root = tree.getroot()

        if root.tag != "xrgb":
            raise ValueError(f"Expected root element 'xrgb', got '{root.tag}'")

        # Only parse known elements
        layout_data = self._parse_root(root)
        layout = Layout(**layout_data)

        logger.debug(
            f"Successfully parsed layout with "
            f"{len(layout.models.model) if layout.models else 0} models"
        )
        return layout

    def _parse_root(self, root: Any) -> dict[str, Any]:
        """Parse only known top-level elements from root.

        Args:
            root: XML root element

        Returns:
            Dictionary with only known sections
        """
        result: dict[str, Any] = {}

        for child in root:
            # Only parse if we have a model for it
            if child.tag in self.KNOWN_TYPES:
                logger.debug(f"Parsing known section: {child.tag}")
                child_data = self._parse_element(child)
                result[child.tag] = child_data
            else:
                # Unknown element - skip it
                logger.debug(f"Skipping unknown section: {child.tag}")

        return result

    def _parse_element(self, element: Any) -> dict[str, Any]:
        """Recursively parse an XML element into a dictionary.

        Args:
            element: XML element to parse

        Returns:
            Dictionary representation of the element
        """
        result: dict[str, Any] = {}

        # Add attributes
        if element.attrib:
            result.update(element.attrib)

        # Process child elements
        for child in element:
            child_data = self._parse_element(child)

            # Handle collections (multiple elements with same tag)
            if child.tag in result:
                # Convert to list if not already
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                # Check if there are siblings with the same tag
                siblings = [c for c in element if c.tag == child.tag and c is not child]
                if siblings:
                    # Start a list
                    result[child.tag] = [child_data]
                else:
                    # Single element
                    result[child.tag] = child_data

        # If element has text content and no children, store the text
        if element.text and element.text.strip() and not list(element):
            return element.text.strip()

        # If element has no attributes or children, return empty dict
        if not result:
            return {}

        return result


def load_layout(file_path: Path | str) -> Layout:
    """Load an xLights layout from file.

    Only parses known semantic models. Unknown elements are ignored.

    Args:
        file_path: Path to xlights_rgbeffects.xml file

    Returns:
        Parsed Layout model
    """
    parser = LayoutParser()
    return parser.parse(file_path)
