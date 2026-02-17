"""Tests for XLightsMapping resolution logic.

Tests group-first resolution with model-level fallback:
- Direct group name resolution
- Model fallback when no group exists
- Unknown choreo_id handling
- Bulk resolution
"""

from twinklr.core.sequencer.display.xlights_mapping import (
    XLightsGroupMapping,
    XLightsMapping,
)

# ---------------------------------------------------------------------------
# XLightsMapping - Resolution
# ---------------------------------------------------------------------------


class TestXLightsMappingResolution:
    """Tests for XLightsMapping.resolve method."""

    def test_resolve_to_group_name(self) -> None:
        """When group_name exists, resolve returns it."""
        mapping = XLightsMapping(
            entries=[
                XLightsGroupMapping(
                    choreo_id="ARCHES",
                    group_name="61 - Arches",
                ),
            ],
        )
        assert mapping.resolve("ARCHES") == ["61 - Arches"]

    def test_resolve_falls_back_to_models(self) -> None:
        """When no group_name, resolve returns individual model names."""
        mapping = XLightsMapping(
            entries=[
                XLightsGroupMapping(
                    choreo_id="CANDY_CANES",
                    model_names=["Cane 1", "Cane 2", "Cane 3"],
                ),
            ],
        )
        assert mapping.resolve("CANDY_CANES") == ["Cane 1", "Cane 2", "Cane 3"]

    def test_resolve_unknown_falls_back_to_id(self) -> None:
        """Unknown choreo_id returns the id itself as fallback."""
        mapping = XLightsMapping(entries=[])
        assert mapping.resolve("UNKNOWN") == ["UNKNOWN"]

    def test_resolve_group_preferred_over_models(self) -> None:
        """When both group_name and model_names exist, group_name wins."""
        mapping = XLightsMapping(
            entries=[
                XLightsGroupMapping(
                    choreo_id="ARCHES",
                    group_name="61 - Arches",
                    model_names=["Arch 1", "Arch 2"],
                ),
            ],
        )
        assert mapping.resolve("ARCHES") == ["61 - Arches"]

    def test_resolve_no_group_no_models_falls_back_to_id(self) -> None:
        """Entry with no group_name and no model_names falls back to choreo_id."""
        mapping = XLightsMapping(
            entries=[
                XLightsGroupMapping(choreo_id="EMPTY"),
            ],
        )
        assert mapping.resolve("EMPTY") == ["EMPTY"]


class TestXLightsMappingBulk:
    """Tests for bulk resolution methods."""

    def test_resolve_all_returns_mapping(self) -> None:
        """resolve_all returns choreo_id -> element names for all entries."""
        mapping = XLightsMapping(
            entries=[
                XLightsGroupMapping(choreo_id="ARCHES", group_name="Arches"),
                XLightsGroupMapping(
                    choreo_id="CANES",
                    model_names=["Cane 1", "Cane 2"],
                ),
            ],
        )
        resolved = mapping.resolve_all()
        assert resolved["ARCHES"] == ["Arches"]
        assert resolved["CANES"] == ["Cane 1", "Cane 2"]

    def test_has_entry(self) -> None:
        """has_entry returns True for known, False for unknown choreo_ids."""
        mapping = XLightsMapping(
            entries=[XLightsGroupMapping(choreo_id="ARCHES", group_name="Arches")],
        )
        assert mapping.has_entry("ARCHES") is True
        assert mapping.has_entry("UNKNOWN") is False
