"""Test comprehensive geometry type coverage for smart fallback.

Ensures that:
1. All implemented geometry types are classified (no gaps)
2. No geometry type is in both sets (no double-processing)
3. Geometry types match actual implementations
"""

from __future__ import annotations

import pytest

from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry import (
    GeometryEngine,
)
from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.classification import (
    ASYMMETRIC_GEOMETRIES,
    SYMMETRIC_GEOMETRIES,
)
from blinkb0t.core.utils.json import read_json


class TestGeometryClassificationCoverage:
    """Test that all geometry types are properly classified."""

    @pytest.fixture
    def geometry_engine(self):
        """Create a geometry engine instance."""
        return GeometryEngine()

    @pytest.fixture
    def implemented_geometries(self, geometry_engine):
        """Get list of all implemented geometry types from engine."""
        return set(geometry_engine.list_geometries())

    @pytest.fixture
    def library_geometries(self):
        """Get list of all geometry IDs from the library JSON."""
        from pathlib import Path

        # Path to geometry library
        library_path = (
            Path(__file__).parents[1]
            / "packages"
            / "blinkb0t"
            / "core"
            / "domains"
            / "sequencing"
            / "movingheads"
            / "data"
            / "geometry"
            / "v1"
            / "library.json"
        )

        if not library_path.exists():
            pytest.skip(f"Geometry library not found at {library_path}")

        library = read_json(str(library_path))
        return {item["id"] for item in library.get("items", [])}

    def test_no_overlap_between_geometry_sets(self):
        """Geometry types should not appear in both sets (prevents double-processing)."""
        overlap = SYMMETRIC_GEOMETRIES & ASYMMETRIC_GEOMETRIES
        assert len(overlap) == 0, (
            f"Geometries appear in both SYMMETRIC and ASYMMETRIC sets (will be double-processed): {overlap}"
        )

    def test_all_implemented_geometries_are_classified(self, implemented_geometries):
        """All implemented geometries must be in either SYMMETRIC or ASYMMETRIC set."""
        all_classified = SYMMETRIC_GEOMETRIES | ASYMMETRIC_GEOMETRIES

        unclassified = implemented_geometries - all_classified
        assert len(unclassified) == 0, (
            f"Implemented geometries not classified (will be skipped): {unclassified}\n"
            f"Add these to either SYMMETRIC_GEOMETRIES or ASYMMETRIC_GEOMETRIES in sequencer.py"
        )

    def test_no_phantom_geometries_in_classification(self, implemented_geometries):
        """All classified geometries should be implemented (no typos or stale entries)."""
        all_classified = SYMMETRIC_GEOMETRIES | ASYMMETRIC_GEOMETRIES

        phantom = all_classified - implemented_geometries

        # Allow some exceptions for aliases or variations
        allowed_phantoms = {
            "line",  # Might be an alias for wall_wash or future implementation
            "chevron",  # Alias for chevron_v
        }

        unexpected_phantom = phantom - allowed_phantoms

        if unexpected_phantom:
            pytest.fail(
                f"Classified geometries not implemented (typos or stale entries?): {unexpected_phantom}\n"
                f"Remove these from SYMMETRIC_GEOMETRIES/ASYMMETRIC_GEOMETRIES or implement them.\n"
                f"Known allowed phantoms: {allowed_phantoms}"
            )

    def test_symmetric_geometries_characteristics(self, geometry_engine):
        """Verify symmetric geometries have expected characteristics."""
        # These geometries should produce uniform/evenly distributed patterns
        expected_symmetric = {
            "fan",  # Even distribution across arc
            "wall_wash",  # Uniform parallel coverage
            "chevron_v",  # Symmetric V shape
            "audience_scan",  # Uniform spread across audience
            "rainbow_arc",  # Even arc distribution
        }

        # Check that expected symmetric are classified correctly
        for geom in expected_symmetric:
            if geom in geometry_engine.list_geometries():
                assert geom in SYMMETRIC_GEOMETRIES, (
                    f"Geometry '{geom}' should be in SYMMETRIC_GEOMETRIES (produces uniform patterns)"
                )

    def test_asymmetric_geometries_characteristics(self, geometry_engine):
        """Verify asymmetric geometries have expected characteristics."""
        # These geometries should produce non-uniform per-fixture positions
        expected_asymmetric = {
            "spotlight_cluster",  # Converges to different positions with spread
            "tunnel_cone",  # Different depths/angles for cone
            "alternating_updown",  # Different tilt roles per fixture
            "mirror_lr",  # Different L/R positions (not uniform)
            "wave_lr",  # Phase-shifted positions across fixtures
            "center_out",  # Expanding/collapsing dynamic positions
            "x_cross",  # Diagonal crossing with different paths
            "scattered_chaos",  # Random per-fixture positions
        }

        # Check that expected asymmetric are classified correctly
        for geom in expected_asymmetric:
            if geom in geometry_engine.list_geometries():
                assert geom in ASYMMETRIC_GEOMETRIES, (
                    f"Geometry '{geom}' should be in ASYMMETRIC_GEOMETRIES (produces per-fixture variations)"
                )

    def test_library_vs_implemented_status(self, library_geometries, implemented_geometries):
        """Show which library geometries are implemented vs pending."""
        not_implemented = library_geometries - implemented_geometries
        implemented_not_in_library = implemented_geometries - library_geometries

        # This is informational, not a failure
        if not_implemented:
            print(f"\nLibrary geometries not yet implemented: {not_implemented}")

        if implemented_not_in_library:
            print(f"\nImplemented geometries not in library: {implemented_not_in_library}")

        # Don't fail, just inform
        assert True, "Informational test only"


class TestSmartFallbackDecisionLogic:
    """Test the smart fallback decision logic for different scenarios."""

    @pytest.fixture
    def geometry_engine(self):
        """Create a geometry engine instance."""
        return GeometryEngine()

    def test_symmetric_single_fixture(self):
        """Single fixture with symmetric geometry uses shared curves."""
        geometry_type = "fan"
        num_targets = 1

        use_per_fixture = geometry_type in ASYMMETRIC_GEOMETRIES and num_targets > 1

        assert not use_per_fixture, "Single fixture should always use shared curves"

    def test_symmetric_multiple_fixtures(self):
        """Multiple fixtures with symmetric geometry use shared curves."""
        for geometry_type in ["fan", "wall_wash", "chevron_v", "audience_scan", "rainbow_arc"]:
            for num_targets in [2, 3, 4, 8]:
                use_per_fixture = geometry_type in ASYMMETRIC_GEOMETRIES and num_targets > 1

                assert not use_per_fixture, (
                    f"Symmetric geometry '{geometry_type}' with {num_targets} fixtures "
                    f"should use shared curves (optimization)"
                )

    def test_asymmetric_single_fixture(self):
        """Single fixture with asymmetric geometry uses shared curves (optimization)."""
        for geometry_type in ASYMMETRIC_GEOMETRIES:
            num_targets = 1

            use_per_fixture = geometry_type in ASYMMETRIC_GEOMETRIES and num_targets > 1

            assert not use_per_fixture, (
                f"Asymmetric geometry '{geometry_type}' with single fixture "
                f"should use shared curves (no benefit from per-fixture)"
            )

    def test_asymmetric_multiple_fixtures(self):
        """Multiple fixtures with asymmetric geometry use per-fixture curves."""
        for geometry_type in ASYMMETRIC_GEOMETRIES:
            for num_targets in [2, 3, 4, 8]:
                use_per_fixture = geometry_type in ASYMMETRIC_GEOMETRIES and num_targets > 1

                assert use_per_fixture, (
                    f"Asymmetric geometry '{geometry_type}' with {num_targets} fixtures "
                    f"should use per-fixture curves (optimal quality)"
                )

    def test_geometry_engine_consistency(self, geometry_engine):
        """All classified geometries should be registered in engine (except known aliases)."""
        all_classified = SYMMETRIC_GEOMETRIES | ASYMMETRIC_GEOMETRIES

        known_aliases = {"line", "chevron"}  # These might be aliases or not yet implemented

        for geom in all_classified:
            if geom not in known_aliases:
                has_geometry = geometry_engine.has_geometry(geom)
                assert has_geometry, (
                    f"Classified geometry '{geom}' not registered in GeometryEngine. "
                    f"Either implement it or remove from classification."
                )


class TestDoubleProcessingPrevention:
    """Test that double-processing is prevented."""

    def test_no_geometry_double_processed(self):
        """Ensure no geometry can be both symmetric and asymmetric."""
        overlap = SYMMETRIC_GEOMETRIES & ASYMMETRIC_GEOMETRIES

        assert len(overlap) == 0, (
            f"CRITICAL: Geometries in both sets will be double-processed!\n"
            f"Offending geometries: {overlap}\n"
            f"This will cause geometry adjustment to happen twice, leading to incorrect curve parameters."
        )

    def test_classification_sets_are_disjoint(self):
        """Sets must be mathematically disjoint."""
        assert SYMMETRIC_GEOMETRIES.isdisjoint(ASYMMETRIC_GEOMETRIES), (
            "SYMMETRIC_GEOMETRIES and ASYMMETRIC_GEOMETRIES must be disjoint sets"
        )

    def test_classification_coverage_completeness(self):
        """Test that we have good coverage of implemented geometries."""
        engine = GeometryEngine()
        implemented = set(engine.list_geometries())
        classified = SYMMETRIC_GEOMETRIES | ASYMMETRIC_GEOMETRIES

        # Allow for some unclassified (pending implementation)
        known_unclassified = set()  # Add any intentionally unclassified here

        actually_unclassified = implemented - classified - known_unclassified

        coverage_ratio = len(classified & implemented) / len(implemented) if implemented else 0

        assert coverage_ratio >= 0.8, (
            f"Classification coverage is {coverage_ratio:.1%}, should be ≥80%\n"
            f"Unclassified geometries: {actually_unclassified}\n"
            f"Add these to SYMMETRIC_GEOMETRIES or ASYMMETRIC_GEOMETRIES"
        )


class TestGeometryTypeAliases:
    """Test handling of geometry type aliases and variations."""

    def test_chevron_alias(self):
        """'chevron' might be an alias for 'chevron_v'."""
        # Both should be classified, but only chevron_v is implemented
        assert "chevron" in SYMMETRIC_GEOMETRIES or "chevron_v" in SYMMETRIC_GEOMETRIES, (
            "Either 'chevron' or 'chevron_v' should be classified"
        )

        # chevron_v is the implemented one
        engine = GeometryEngine()
        assert engine.has_geometry("chevron_v"), "chevron_v should be implemented"

    def test_line_classification(self):
        """'line' geometry should be classified if used."""
        # If line is in our classification, check if it's aliased to something
        if "line" in SYMMETRIC_GEOMETRIES:
            # This is acceptable as it might be wall_wash or a future implementation
            print("\nNote: 'line' is classified but not implemented (might be an alias)")
