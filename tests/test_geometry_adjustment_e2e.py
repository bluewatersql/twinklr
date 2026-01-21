"""E2E test for geometry transformations.

Updated to test GeometryEngine from the new module.
"""

from __future__ import annotations

import pytest

from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.engine import GeometryEngine


class TestGeometryEngine:
    """Test geometry engine functionality."""

    @pytest.fixture
    def engine(self):
        """Create a geometry engine instance."""
        return GeometryEngine()

    def test_geometry_engine_initialization(self, engine):
        """Test that geometry engine initializes with transforms."""
        assert engine is not None
        assert len(engine.transforms) > 0

    def test_geometry_engine_has_common_types(self, engine):
        """Test that common geometry types are registered."""
        expected_types = ["fan", "mirror_lr", "wave_lr", "chevron_v"]
        for geo_type in expected_types:
            assert geo_type in engine.transforms, f"Missing geometry type: {geo_type}"

    def test_apply_geometry_basic(self, engine):
        """Test basic geometry application."""
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "sweep_lr", "amplitude_deg": 60}

        result = engine.apply_geometry(
            geometry_type="fan",
            targets=targets,
            base_movement=base_movement,
        )

        assert result is not None
        assert len(result) == len(targets)
