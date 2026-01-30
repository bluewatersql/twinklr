"""Generic XML parsing utilities with error handling.

This module provides a simple, robust XML parser wrapper around
ElementTree with consistent error handling and validation.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from twinklr.core.utils.logging import get_logger

logger = get_logger(__name__)


class XMLParser:
    """Generic XML parser with error handling.

    Wraps Python's ElementTree with:
    - File existence validation
    - Clear error messages for malformed XML
    - Support for both file paths and strings
    - Path object support

    Example:
        >>> parser = XMLParser()
        >>> tree = parser.parse("config.xml")
        >>> root = tree.getroot()

        >>> # Or parse from string
        >>> root = parser.parse_string("<root><element>Text</element></root>")
    """

    def parse(self, file_path: Path | str) -> ET.ElementTree[ET.Element[str]]:
        """Parse XML file.

        Args:
            file_path: Path to XML file (Path object or string)

        Returns:
            Parsed ElementTree

        Raises:
            FileNotFoundError: If file does not exist
            ValueError: If XML is malformed

        Example:
            >>> parser = XMLParser()
            >>> tree = parser.parse("layout.xml")
            >>> root = tree.getroot()
            >>> print(root.tag)
        """
        path = Path(file_path)

        # Validate file exists
        if not path.exists():
            raise FileNotFoundError(f"XML file does not exist: {path}")

        try:
            logger.debug(f"Parsing XML file: {path}")
            tree: ET.ElementTree[ET.Element[str]] = ET.parse(path)
            logger.debug(f"Successfully parsed XML file: {path}")
            return tree
        except ET.ParseError as e:
            raise ValueError(f"Malformed XML in {path}: {e}") from e

    def parse_string(self, xml_str: str) -> ET.Element:
        """Parse XML from string.

        Args:
            xml_str: XML content as string

        Returns:
            Parsed Element (root element)

        Raises:
            ValueError: If XML is malformed

        Example:
            >>> parser = XMLParser()
            >>> root = parser.parse_string('<root><item>Value</item></root>')
            >>> print(root.find("item").text)
            Value
        """
        try:
            return ET.fromstring(xml_str)
        except ET.ParseError as e:
            raise ValueError(f"Malformed XML string: {e}") from e
