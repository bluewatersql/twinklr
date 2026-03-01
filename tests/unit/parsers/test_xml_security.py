"""Security tests for XML parsing — SEC-02.

Verifies that the XMLParser blocks XXE and billion-laughs attacks
by using defusedxml instead of stdlib xml.etree.ElementTree.
"""

from __future__ import annotations

from defusedxml import DTDForbidden, EntitiesForbidden
import pytest

from twinklr.core.parsers.xml import XMLParser

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def parser() -> XMLParser:
    """Return a fresh XMLParser instance."""
    return XMLParser()


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_parse_valid_xml_file(tmp_path, parser: XMLParser) -> None:
    """Valid XML files are parsed correctly."""
    xml_file = tmp_path / "valid.xml"
    xml_file.write_text("<root><child attr='value'>text</child></root>")

    tree = parser.parse(xml_file)
    root = tree.getroot()

    assert root.tag == "root"
    child = root.find("child")
    assert child is not None
    assert child.text == "text"
    assert child.get("attr") == "value"


def test_parse_string_valid_xml(parser: XMLParser) -> None:
    """Valid XML strings are parsed correctly."""
    xml_str = "<root><item>Value</item></root>"
    root = parser.parse_string(xml_str)

    assert root.tag == "root"
    item = root.find("item")
    assert item is not None
    assert item.text == "Value"


def test_parse_string_returns_root_element(parser: XMLParser) -> None:
    """parse_string returns the root Element directly."""
    root = parser.parse_string("<data><a/><b/></data>")
    assert root.tag == "data"
    assert len(list(root)) == 2


# ---------------------------------------------------------------------------
# Malformed XML tests
# ---------------------------------------------------------------------------


def test_parse_malformed_xml_raises_value_error(tmp_path, parser: XMLParser) -> None:
    """Malformed XML file raises ValueError."""
    bad = tmp_path / "bad.xml"
    bad.write_text("<unclosed>")

    with pytest.raises(ValueError, match="Malformed XML"):
        parser.parse(bad)


def test_parse_string_malformed_raises_value_error(parser: XMLParser) -> None:
    """Malformed XML string raises ValueError."""
    with pytest.raises(ValueError, match="Malformed XML string"):
        parser.parse_string("<unclosed>")


def test_parse_missing_file_raises_file_not_found(tmp_path, parser: XMLParser) -> None:
    """Missing file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        parser.parse(tmp_path / "nonexistent.xml")


# ---------------------------------------------------------------------------
# SEC-02: XXE attack tests
# ---------------------------------------------------------------------------

XXE_FILE_PAYLOAD = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<root><data>&xxe;</data></root>
"""

XXE_HTTP_PAYLOAD = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "http://evil.example.com/attack">
]>
<root><data>&xxe;</data></root>
"""


def test_xxe_file_entity_is_blocked(tmp_path, parser: XMLParser) -> None:
    """XXE attack using file:// SYSTEM entity raises an error (not silently loaded)."""
    xml_file = tmp_path / "xxe.xml"
    xml_file.write_text(XXE_FILE_PAYLOAD)

    with pytest.raises(
        (DTDForbidden, EntitiesForbidden)
    ):  # defusedxml raises DTDForbidden or similar
        parser.parse(xml_file)


def test_xxe_string_file_entity_is_blocked(parser: XMLParser) -> None:
    """XXE attack via parse_string raises an error."""
    with pytest.raises((DTDForbidden, EntitiesForbidden)):
        parser.parse_string(XXE_FILE_PAYLOAD)


def test_xxe_http_entity_is_blocked(tmp_path, parser: XMLParser) -> None:
    """XXE attack using http:// SYSTEM entity raises an error."""
    xml_file = tmp_path / "xxe_http.xml"
    xml_file.write_text(XXE_HTTP_PAYLOAD)

    with pytest.raises((DTDForbidden, EntitiesForbidden)):
        parser.parse(xml_file)


# ---------------------------------------------------------------------------
# SEC-02: Billion-laughs (entity expansion) attack tests
# ---------------------------------------------------------------------------

BILLION_LAUGHS_PAYLOAD = """\
<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
  <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
]>
<root>&lol4;</root>
"""


def test_billion_laughs_is_blocked_from_string(parser: XMLParser) -> None:
    """Billion-laughs entity expansion attack is blocked when parsing strings."""
    with pytest.raises((DTDForbidden, EntitiesForbidden)):
        parser.parse_string(BILLION_LAUGHS_PAYLOAD)


def test_billion_laughs_is_blocked_from_file(tmp_path, parser: XMLParser) -> None:
    """Billion-laughs entity expansion attack is blocked when parsing files."""
    xml_file = tmp_path / "laughs.xml"
    xml_file.write_text(BILLION_LAUGHS_PAYLOAD)

    with pytest.raises((DTDForbidden, EntitiesForbidden)):
        parser.parse(xml_file)
