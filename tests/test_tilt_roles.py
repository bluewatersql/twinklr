"""Tests for Phase 0: Tilt Role Support in Geometry System.

Tests that geometry transforms can assign tilt roles (above_horizon, up, zero)
and that the sequencer correctly applies these roles to per-fixture tilt positions.
"""

from __future__ import annotations

from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.base import VALID_TILT_ROLES
from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.engine import GeometryEngine


class TestTiltRoleHelpers:
    """Test base class tilt role helper methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = GeometryEngine()
        # Use mirror_lr as representative transform
        self.transform = self.engine.transforms["mirror_lr"]

    def test_valid_tilt_roles_constant(self):
        """Test that VALID_TILT_ROLES contains expected values."""
        assert "above_horizon" in VALID_TILT_ROLES
        assert "up" in VALID_TILT_ROLES
        assert "zero" in VALID_TILT_ROLES
        assert len(VALID_TILT_ROLES) == 3

    def test_validate_tilt_role_valid(self):
        """Test validation of valid tilt roles."""
        assert self.transform._validate_tilt_role("above_horizon") is True
        assert self.transform._validate_tilt_role("up") is True
        assert self.transform._validate_tilt_role("zero") is True

    def test_validate_tilt_role_invalid(self):
        """Test validation of invalid tilt roles."""
        assert self.transform._validate_tilt_role("invalid") is False
        assert self.transform._validate_tilt_role("middle") is False
        assert self.transform._validate_tilt_role("") is False

    def test_assign_tilt_role(self):
        """Test assigning tilt role to movement."""
        movement = {"pattern": "sweep_lr", "amplitude_deg": 60}

        # Assign valid role
        self.transform._assign_tilt_role(movement, "up")
        assert movement["tilt_role"] == "up"

        # Assign another valid role
        self.transform._assign_tilt_role(movement, "zero")
        assert movement["tilt_role"] == "zero"

    def test_assign_tilt_role_default(self):
        """Test assigning default tilt role when None provided."""
        movement = {"pattern": "sweep_lr"}
        self.transform._assign_tilt_role(movement, None)
        assert movement["tilt_role"] == "above_horizon"

    def test_assign_tilt_role_invalid_fallback(self):
        """Test that invalid roles fall back to default."""
        movement = {"pattern": "sweep_lr"}
        self.transform._assign_tilt_role(movement, "invalid_role")
        assert movement["tilt_role"] == "above_horizon"

    def test_get_tilt_role_from_params(self):
        """Test extracting tilt role from params dict."""
        # Using 'tilt' key
        params = {"tilt": "up", "pan_spread_deg": 30}
        role = self.transform._get_tilt_role_from_params(params)
        assert role == "up"

        # Using 'tilt_role' key
        params = {"tilt_role": "zero"}
        role = self.transform._get_tilt_role_from_params(params)
        assert role == "zero"

        # No tilt specified - use default
        params = {"pan_spread_deg": 30}
        role = self.transform._get_tilt_role_from_params(params)
        assert role == "above_horizon"

        # None params - use default
        role = self.transform._get_tilt_role_from_params(None)
        assert role == "above_horizon"

    def test_get_tilt_role_from_params_custom_default(self):
        """Test custom default for tilt role extraction."""
        params = {}
        role = self.transform._get_tilt_role_from_params(params, default="up")
        assert role == "up"


class TestGeometryTiltRoles:
    """Test tilt role assignment in geometry transforms."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = GeometryEngine()
        self.targets = ["MH1", "MH2", "MH3", "MH4"]
        self.base_movement = {"pattern": "sweep_lr", "amplitude_deg": 60}

    def test_mirror_lr_with_tilt_role(self):
        """Test mirror_lr assigns tilt role to all fixtures."""
        params = {"pan_spread_deg": 30, "tilt": "up"}
        result = self.engine.apply_geometry(
            geometry_type="mirror_lr",
            targets=self.targets,
            base_movement=self.base_movement,
            params=params,
        )

        # All fixtures should have tilt_role assigned
        for target in self.targets:
            assert "tilt_role" in result[target]
            assert result[target]["tilt_role"] == "up"

    def test_mirror_lr_no_tilt_role(self):
        """Test mirror_lr without tilt param uses default."""
        params = {"pan_spread_deg": 30}
        result = self.engine.apply_geometry(
            geometry_type="mirror_lr",
            targets=self.targets,
            base_movement=self.base_movement,
            params=params,
        )

        # Should have default tilt_role
        for target in self.targets:
            assert "tilt_role" in result[target]
            assert result[target]["tilt_role"] == "above_horizon"

    def test_chevron_v_with_tilt_role(self):
        """Test chevron_v assigns tilt role."""
        params = {"tightness": 0.7, "tilt": "up"}
        result = self.engine.apply_geometry(
            geometry_type="chevron_v",
            targets=self.targets,
            base_movement=self.base_movement,
            params=params,
        )

        for target in self.targets:
            assert "tilt_role" in result[target]
            assert result[target]["tilt_role"] == "up"

    def test_audience_scan_with_tilt_role(self):
        """Test audience_scan assigns tilt role."""
        params = {"coverage_width": "wide", "tilt": "above_horizon"}
        result = self.engine.apply_geometry(
            geometry_type="audience_scan",
            targets=self.targets,
            base_movement=self.base_movement,
            params=params,
        )

        for target in self.targets:
            assert "tilt_role" in result[target]
            assert result[target]["tilt_role"] == "above_horizon"

    def test_wall_wash_with_tilt_role(self):
        """Test wall_wash assigns tilt role."""
        params = {"spacing": "medium", "tilt": "zero"}
        result = self.engine.apply_geometry(
            geometry_type="wall_wash",
            targets=self.targets,
            base_movement=self.base_movement,
            params=params,
        )

        for target in self.targets:
            assert "tilt_role" in result[target]
            assert result[target]["tilt_role"] == "zero"

    def test_wave_lr_with_tilt_role(self):
        """Test wave_lr assigns tilt role."""
        params = {"phase_spacing": "auto", "tilt": "up"}
        result = self.engine.apply_geometry(
            geometry_type="wave_lr",
            targets=self.targets,
            base_movement=self.base_movement,
            params=params,
        )

        for target in self.targets:
            assert "tilt_role" in result[target]
            assert result[target]["tilt_role"] == "up"

    def test_fan_with_tilt_role(self):
        """Test fan assigns tilt role."""
        params = {"total_spread_deg": 60, "tilt": "above_horizon"}
        result = self.engine.apply_geometry(
            geometry_type="fan",
            targets=self.targets,
            base_movement=self.base_movement,
            params=params,
        )

        for target in self.targets:
            assert "tilt_role" in result[target]
            assert result[target]["tilt_role"] == "above_horizon"

    def test_tilt_role_coexists_with_tilt_offset(self):
        """Test that tilt_role and tilt_offset_deg can coexist."""
        # Chevron_v has inner_tilt_lift_deg which creates tilt_offset_deg
        params = {"tightness": 0.7, "inner_tilt_lift_deg": 6, "tilt": "up"}
        result = self.engine.apply_geometry(
            geometry_type="chevron_v",
            targets=self.targets,
            base_movement=self.base_movement,
            params=params,
        )

        # Inner fixtures should have both tilt_role and tilt_offset_deg
        inner_targets = ["MH2", "MH3"]  # Assuming n=4, inner are indices 1,2
        for target in inner_targets:
            assert "tilt_role" in result[target]
            assert result[target]["tilt_role"] == "up"
            # Inner fixtures have tilt lift
            assert "tilt_offset_deg" in result[target]
            assert result[target]["tilt_offset_deg"] > 0

    def test_mirror_lr_with_tilt_spread(self):
        """Test mirror_lr with tilt_spread_deg parameter (Phase 0 enhancement)."""
        params = {"pan_spread_deg": 30, "tilt_spread_deg": 10, "tilt": "up"}
        result = self.engine.apply_geometry(
            geometry_type="mirror_lr",
            targets=self.targets,
            base_movement=self.base_movement,
            params=params,
        )

        # All fixtures should have tilt_role
        for target in self.targets:
            assert result[target]["tilt_role"] == "up"

        # Outer fixtures should have more tilt offset than inner
        # Assuming left-to-right: MH1 (outer), MH2 (inner), MH3 (inner), MH4 (outer)
        outer_offsets = [
            result["MH1"].get("tilt_offset_deg", 0),
            result["MH4"].get("tilt_offset_deg", 0),
        ]
        inner_offsets = [
            result["MH2"].get("tilt_offset_deg", 0),
            result["MH3"].get("tilt_offset_deg", 0),
        ]

        # Outer fixtures should have non-zero offsets
        assert all(offset > 0 for offset in outer_offsets)
        # Inner fixtures should have smaller offsets
        assert all(
            outer > inner for outer, inner in zip(outer_offsets, inner_offsets, strict=False)
        )


class TestTiltRoleIntegration:
    """Integration tests for end-to-end tilt role flow."""

    def test_tilt_role_preserved_through_geometry_pipeline(self):
        """Test that tilt_role is preserved from geometry to movement spec."""
        engine = GeometryEngine()
        targets = ["MH1", "MH2"]
        base_movement = {"pattern": "sweep_lr", "amplitude_deg": 45}
        params = {"pan_spread_deg": 20, "tilt": "up"}

        # Apply geometry
        result = engine.apply_geometry(
            geometry_type="mirror_lr",
            targets=targets,
            base_movement=base_movement,
            params=params,
        )

        # Verify each per-fixture movement has tilt_role
        for target in targets:
            movement = result[target]
            assert "tilt_role" in movement
            assert movement["tilt_role"] == "up"
            # Base movement properties should also be preserved
            assert movement["pattern"] == "sweep_lr"
            assert movement["amplitude_deg"] == 45
            # Geometry should have added pan_offset_deg
            assert "pan_offset_deg" in movement

    def test_different_tilt_roles_per_geometry(self):
        """Test that different geometries can use different tilt roles."""
        engine = GeometryEngine()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}

        # Mirror LR with 'up'
        result1 = engine.apply_geometry("mirror_lr", targets, base_movement, {"tilt": "up"})
        assert all(result1[t]["tilt_role"] == "up" for t in targets)

        # Audience scan with 'above_horizon'
        result2 = engine.apply_geometry(
            "audience_scan", targets, base_movement, {"tilt": "above_horizon"}
        )
        assert all(result2[t]["tilt_role"] == "above_horizon" for t in targets)

        # Wall wash with 'zero'
        result3 = engine.apply_geometry("wall_wash", targets, base_movement, {"tilt": "zero"})
        assert all(result3[t]["tilt_role"] == "zero" for t in targets)
