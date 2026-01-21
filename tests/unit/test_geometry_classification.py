"""Test geometry classification for per-fixture curve optimization."""

from __future__ import annotations

import pytest

from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.classification import (
    ASYMMETRIC_GEOMETRIES,
    SYMMETRIC_GEOMETRIES,
    GeometryClass,
    get_geometry_class,
    is_asymmetric,
    is_symmetric,
    should_use_per_fixture_curves,
)


class TestGeometryClassification:
    """Test geometry classification functions."""

    def test_symmetric_geometries_are_immutable(self):
        """Symmetric geometries should be a frozenset."""
        assert isinstance(SYMMETRIC_GEOMETRIES, frozenset)
        with pytest.raises(AttributeError):
            SYMMETRIC_GEOMETRIES.add("new_geometry")  # type: ignore

    def test_asymmetric_geometries_are_immutable(self):
        """Asymmetric geometries should be a frozenset."""
        assert isinstance(ASYMMETRIC_GEOMETRIES, frozenset)
        with pytest.raises(AttributeError):
            ASYMMETRIC_GEOMETRIES.add("new_geometry")  # type: ignore

    def test_no_overlap_between_sets(self):
        """No geometry should be in both sets."""
        overlap = SYMMETRIC_GEOMETRIES & ASYMMETRIC_GEOMETRIES
        assert len(overlap) == 0, f"Geometries in both sets: {overlap}"

    def test_get_geometry_class_symmetric(self):
        """get_geometry_class should return SYMMETRIC for symmetric geometries."""
        for geom in SYMMETRIC_GEOMETRIES:
            assert get_geometry_class(geom) == GeometryClass.SYMMETRIC

    def test_get_geometry_class_asymmetric(self):
        """get_geometry_class should return ASYMMETRIC for asymmetric geometries."""
        for geom in ASYMMETRIC_GEOMETRIES:
            assert get_geometry_class(geom) == GeometryClass.ASYMMETRIC

    def test_get_geometry_class_none(self):
        """get_geometry_class should return SYMMETRIC for None."""
        assert get_geometry_class(None) == GeometryClass.SYMMETRIC

    def test_get_geometry_class_unknown(self):
        """get_geometry_class should raise ValueError for unknown geometry."""
        with pytest.raises(ValueError, match="Unknown geometry type"):
            get_geometry_class("unknown_geometry")

    def test_is_symmetric_true(self):
        """is_symmetric should return True for symmetric geometries."""
        assert is_symmetric("fan") is True
        assert is_symmetric("chevron_v") is True

    def test_is_symmetric_false(self):
        """is_symmetric should return False for asymmetric geometries."""
        assert is_symmetric("mirror_lr") is False
        assert is_symmetric("wave_lr") is False

    def test_is_symmetric_none(self):
        """is_symmetric should return True for None."""
        assert is_symmetric(None) is True

    def test_is_asymmetric_true(self):
        """is_asymmetric should return True for asymmetric geometries."""
        assert is_asymmetric("mirror_lr") is True
        assert is_asymmetric("wave_lr") is True

    def test_is_asymmetric_false(self):
        """is_asymmetric should return False for symmetric geometries."""
        assert is_asymmetric("fan") is False
        assert is_asymmetric("chevron_v") is False

    def test_is_asymmetric_none(self):
        """is_asymmetric should return False for None."""
        assert is_asymmetric(None) is False


class TestPerFixtureCurveDecision:
    """Test should_use_per_fixture_curves logic."""

    def test_single_fixture_always_shared(self):
        """Single fixture should always use shared curves."""
        assert should_use_per_fixture_curves("mirror_lr", 1) is False
        assert should_use_per_fixture_curves("fan", 1) is False
        assert should_use_per_fixture_curves(None, 1) is False

    def test_zero_fixtures_always_shared(self):
        """Zero fixtures should return False."""
        assert should_use_per_fixture_curves("mirror_lr", 0) is False
        assert should_use_per_fixture_curves("fan", 0) is False

    def test_symmetric_multiple_fixtures_uses_shared(self):
        """Symmetric geometries with multiple fixtures use shared curves."""
        for geom in SYMMETRIC_GEOMETRIES:
            assert should_use_per_fixture_curves(geom, 2) is False
            assert should_use_per_fixture_curves(geom, 4) is False
            assert should_use_per_fixture_curves(geom, 8) is False

    def test_asymmetric_multiple_fixtures_uses_per_fixture(self):
        """Asymmetric geometries with multiple fixtures use per-fixture curves."""
        for geom in ASYMMETRIC_GEOMETRIES:
            assert should_use_per_fixture_curves(geom, 2) is True
            assert should_use_per_fixture_curves(geom, 4) is True
            assert should_use_per_fixture_curves(geom, 8) is True

    def test_no_geometry_uses_shared(self):
        """No geometry should use shared curves."""
        assert should_use_per_fixture_curves(None, 4) is False

    def test_unknown_geometry_uses_shared(self):
        """Unknown geometry should default to shared curves (safe fallback)."""
        assert should_use_per_fixture_curves("unknown_geometry", 4) is False


class TestGeometryClassEnum:
    """Test GeometryClass enum."""

    def test_enum_values(self):
        """GeometryClass should have SYMMETRIC and ASYMMETRIC values."""
        assert GeometryClass.SYMMETRIC.value == "symmetric"
        assert GeometryClass.ASYMMETRIC.value == "asymmetric"

    def test_enum_string_equality(self):
        """GeometryClass should support string comparison."""
        assert GeometryClass.SYMMETRIC == "symmetric"
        assert GeometryClass.ASYMMETRIC == "asymmetric"

    def test_enum_membership(self):
        """All enum values should be accessible."""
        assert "SYMMETRIC" in GeometryClass.__members__
        assert "ASYMMETRIC" in GeometryClass.__members__
        assert len(GeometryClass.__members__) == 2


class TestComprehensiveCoverage:
    """Test that all known geometries are classified."""

    def test_all_known_geometries_covered(self):
        """All implemented geometries should be classified."""
        # This is the union of all known geometries from the engine
        known_geometries = [
            "mirror_lr",
            "wave_lr",
            "fan",
            "chevron_v",
            "audience_scan",
            "wall_wash",
            "spotlight_cluster",
            "rainbow_arc",
            "alternating_updown",
            "tunnel_cone",
            "center_out",
            "x_cross",
            "scattered_chaos",
        ]

        all_classified = SYMMETRIC_GEOMETRIES | ASYMMETRIC_GEOMETRIES
        for geom in known_geometries:
            assert geom in all_classified, (
                f"Geometry '{geom}' is not classified. "
                f"Add it to either SYMMETRIC_GEOMETRIES or ASYMMETRIC_GEOMETRIES."
            )
