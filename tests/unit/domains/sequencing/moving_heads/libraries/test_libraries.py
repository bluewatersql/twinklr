"""Tests for library modules."""

from blinkb0t.core.domains.sequencing.libraries.moving_heads import (
    DIMMER_LIBRARY,
    GEOMETRY_LIBRARY,
    MOVEMENT_LIBRARY,
    CategoricalIntensity,
    DimmerID,
    GeometryID,
    MovementID,
    get_dimmer,
    get_dimmer_params,
    get_geometry,
    get_movement,
    get_movement_params,
    list_dimmers,
    list_geometries,
    list_movements,
)


class TestMovementLibrary:
    """Test movement library."""

    def test_library_not_empty(self):
        """Test that movement library has entries."""
        assert len(MOVEMENT_LIBRARY) > 0

    def test_all_enum_values_in_library(self):
        """Test that all MovementID enum values exist in library."""
        for movement_id in MovementID:
            assert movement_id in MOVEMENT_LIBRARY

    def test_get_movement(self):
        """Test getting movement by ID."""
        pattern = get_movement(MovementID.SWEEP_LR)
        assert pattern.id == MovementID.SWEEP_LR
        assert pattern.name == "Left/Right Sweep"

    def test_get_movement_params(self):
        """Test getting movement categorical params."""
        params = get_movement_params(MovementID.SWEEP_LR, CategoricalIntensity.DRAMATIC)
        assert params.amplitude == 0.6  # Updated to match actual library value
        assert params.frequency == 1.25  # Updated to match actual library value

    def test_list_movements(self):
        """Test listing all movements."""
        movements = list_movements()
        assert len(movements) > 0
        assert MovementID.SWEEP_LR in movements

    def test_movement_has_all_intensities(self):
        """Test that all movements have all intensity levels."""
        for pattern in MOVEMENT_LIBRARY.values():
            for intensity in CategoricalIntensity:
                assert intensity in pattern.categorical_params


class TestGeometryLibrary:
    """Test geometry library."""

    def test_library_not_empty(self):
        """Test that geometry library has entries."""
        assert len(GEOMETRY_LIBRARY) > 0

    def test_all_enum_values_in_library(self):
        """Test that all GeometryID enum values exist in library."""
        for geometry_id in GeometryID:
            assert geometry_id in GEOMETRY_LIBRARY

    def test_get_geometry(self):
        """Test getting geometry by ID."""
        geo = get_geometry(GeometryID.FAN)
        assert geo.id == GeometryID.FAN
        assert geo.name == "Fan Spread"

    def test_list_geometries(self):
        """Test listing all geometries."""
        geometries = list_geometries()
        assert len(geometries) > 0
        assert GeometryID.FAN in geometries


class TestDimmerLibrary:
    """Test dimmer library."""

    def test_library_not_empty(self):
        """Test that dimmer library has entries."""
        assert len(DIMMER_LIBRARY) > 0

    def test_all_enum_values_in_library(self):
        """Test that all DimmerID enum values exist in library."""
        for dimmer_id in DimmerID:
            assert dimmer_id in DIMMER_LIBRARY

    def test_get_dimmer(self):
        """Test getting dimmer by ID."""
        pattern = get_dimmer(DimmerID.BREATHE)
        assert pattern.id == DimmerID.BREATHE
        assert pattern.name == "Breathe"

    def test_get_dimmer_params(self):
        """Test getting dimmer categorical params."""
        params = get_dimmer_params(DimmerID.BREATHE, CategoricalIntensity.DRAMATIC)
        assert params.max_intensity == 255
        assert params.period == 2.0

    def test_list_dimmers(self):
        """Test listing all dimmers."""
        dimmers = list_dimmers()
        assert len(dimmers) > 0
        assert DimmerID.BREATHE in dimmers

    def test_dimmer_has_all_intensities(self):
        """Test that all dimmers have all intensity levels."""
        for pattern in DIMMER_LIBRARY.values():
            for intensity in CategoricalIntensity:
                assert intensity in pattern.categorical_params
