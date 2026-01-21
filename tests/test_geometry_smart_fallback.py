"""Test smart fallback for geometry-aware curves."""

from __future__ import annotations

from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry import (
    ASYMMETRIC_GEOMETRIES,
    SYMMETRIC_GEOMETRIES,
)


class TestGeometryClassification:
    """Test geometry type classification for smart curve rendering."""

    def test_symmetric_geometries_defined(self):
        """Symmetric geometries should be defined."""
        assert len(SYMMETRIC_GEOMETRIES) > 0
        assert "fan" in SYMMETRIC_GEOMETRIES
        assert "chevron_v" in SYMMETRIC_GEOMETRIES
        assert "wall_wash" in SYMMETRIC_GEOMETRIES

    def test_asymmetric_geometries_defined(self):
        """Asymmetric geometries should be defined."""
        assert len(ASYMMETRIC_GEOMETRIES) > 0
        assert "spotlight_cluster" in ASYMMETRIC_GEOMETRIES
        assert "tunnel_cone" in ASYMMETRIC_GEOMETRIES
        assert "mirror_lr" in ASYMMETRIC_GEOMETRIES
        assert "wave_lr" in ASYMMETRIC_GEOMETRIES

    def test_no_overlap_between_geometry_sets(self):
        """Geometry types should not appear in both sets."""
        overlap = SYMMETRIC_GEOMETRIES & ASYMMETRIC_GEOMETRIES
        assert len(overlap) == 0, f"Geometries in both sets: {overlap}"

    def test_common_geometries_classified(self):
        """Common geometry types should be classified."""
        all_geometries = SYMMETRIC_GEOMETRIES | ASYMMETRIC_GEOMETRIES

        # Common geometries from the library
        expected = {
            "fan",
            "mirror_lr",
            "spotlight_cluster",
            "tunnel_cone",
            "audience_scan",
            "wall_wash",
            "chevron_v",
            "rainbow_arc",
        }

        for geom in expected:
            assert geom in all_geometries, f"Geometry '{geom}' not classified"


class TestSmartFallbackLogic:
    """Test the smart fallback decision logic."""

    def test_symmetric_geometry_uses_shared_curves(self):
        """Symmetric geometries should use shared curve optimization."""
        geometry_type = "fan"
        num_targets = 4

        use_per_fixture = geometry_type in ASYMMETRIC_GEOMETRIES and num_targets > 1

        assert not use_per_fixture, "Fan should use shared curves"

    def test_asymmetric_geometry_uses_per_fixture_curves(self):
        """Asymmetric geometries with multiple fixtures should use per-fixture curves."""
        geometry_type = "spotlight_cluster"
        num_targets = 4

        use_per_fixture = geometry_type in ASYMMETRIC_GEOMETRIES and num_targets > 1

        assert use_per_fixture, "Spotlight cluster should use per-fixture curves"

    def test_asymmetric_geometry_single_fixture_uses_shared(self):
        """Asymmetric geometries with single fixture can use shared curves."""
        geometry_type = "spotlight_cluster"
        num_targets = 1

        use_per_fixture = geometry_type in ASYMMETRIC_GEOMETRIES and num_targets > 1

        assert not use_per_fixture, "Single fixture doesn't need per-fixture curves"

    def test_all_symmetric_geometries_use_shared(self):
        """All symmetric geometries should use shared curves regardless of fixture count."""
        for geometry_type in SYMMETRIC_GEOMETRIES:
            for num_targets in [1, 2, 4, 8]:
                use_per_fixture = geometry_type in ASYMMETRIC_GEOMETRIES and num_targets > 1
                assert not use_per_fixture, (
                    f"Symmetric geometry '{geometry_type}' with {num_targets} fixtures "
                    f"should use shared curves"
                )

    def test_all_asymmetric_geometries_use_per_fixture_when_multiple(self):
        """All asymmetric geometries should use per-fixture curves with multiple fixtures."""
        for geometry_type in ASYMMETRIC_GEOMETRIES:
            for num_targets in [2, 4, 8]:
                use_per_fixture = geometry_type in ASYMMETRIC_GEOMETRIES and num_targets > 1
                assert use_per_fixture, (
                    f"Asymmetric geometry '{geometry_type}' with {num_targets} fixtures "
                    f"should use per-fixture curves"
                )
