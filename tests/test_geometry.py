"""Tests for geometry engine and transforms."""

import pytest

from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry import (
    GeometryEngine,
    GeometryTransform,
)
from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.audience_scan import (
    AudienceScanTransform,
)
from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.chevron_v import (
    ChevronVTransform,
)
from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.fan import (
    FanTransform,
)
from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.mirror_lr import (
    MirrorLRTransform,
)
from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.wave_lr import (
    WaveLRTransform,
)


class TestGeometryEngine:
    """Tests for GeometryEngine."""

    def test_engine_initialization(self):
        """Test that engine initializes with built-in transforms."""
        engine = GeometryEngine()

        # Should have registered built-in transforms
        assert len(engine.transforms) >= 10
        assert "mirror_lr" in engine.transforms
        assert "wave_lr" in engine.transforms
        assert "fan" in engine.transforms
        assert "chevron_v" in engine.transforms
        assert "audience_scan" in engine.transforms
        assert "wall_wash" in engine.transforms
        assert "spotlight_cluster" in engine.transforms
        assert "rainbow_arc" in engine.transforms
        assert "alternating_updown" in engine.transforms
        assert "tunnel_cone" in engine.transforms

    def test_register_transform(self):
        """Test registering a custom transform."""
        engine = GeometryEngine()

        # Create a mock transform
        class MockTransform(GeometryTransform):
            geometry_type = "test_pattern"

            def apply(self, targets, base_movement, params=None):
                return {t: base_movement.copy() for t in targets}

        mock = MockTransform()
        engine.register(mock)

        assert "test_pattern" in engine.transforms
        assert engine.transforms["test_pattern"] == mock

    def test_apply_geometry_no_type(self):
        """Test applying geometry with no type returns base movement."""
        engine = GeometryEngine()
        targets = ["MH1", "MH2"]
        base_movement = {"pattern": "sweep_lr", "amplitude_deg": 60}

        result = engine.apply_geometry(None, targets, base_movement)

        assert len(result) == 2
        assert result["MH1"] == base_movement
        assert result["MH2"] == base_movement

    def test_apply_geometry_unknown_type(self):
        """Test applying unknown geometry type falls back to base movement."""
        engine = GeometryEngine()
        targets = ["MH1", "MH2"]
        base_movement = {"pattern": "sweep_lr"}

        result = engine.apply_geometry("nonexistent", targets, base_movement)

        assert len(result) == 2
        assert result["MH1"] == base_movement
        assert result["MH2"] == base_movement

    def test_list_geometries(self):
        """Test listing available geometries."""
        engine = GeometryEngine()
        geometries = engine.list_geometries()

        assert isinstance(geometries, list)
        assert "mirror_lr" in geometries
        assert "wave_lr" in geometries

    def test_has_geometry(self):
        """Test checking if geometry exists."""
        engine = GeometryEngine()

        assert engine.has_geometry("mirror_lr") is True
        assert engine.has_geometry("nonexistent") is False


class TestMirrorLRTransform:
    """Tests for MirrorLRTransform."""

    def test_mirror_lr_4_fixtures(self):
        """Test mirror_lr with 4 fixtures."""
        transform = MirrorLRTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "sweep_lr", "amplitude_deg": 60}
        params = {"pan_spread_deg": 30}

        result = transform.apply(targets, base_movement, params)

        assert len(result) == 4

        # Check symmetric offsets
        assert result["MH1"]["pan_offset_deg"] < 0  # Left outer
        assert result["MH2"]["pan_offset_deg"] < 0  # Left inner
        assert result["MH3"]["pan_offset_deg"] > 0  # Right inner
        assert result["MH4"]["pan_offset_deg"] > 0  # Right outer

        # Check symmetry
        assert abs(result["MH1"]["pan_offset_deg"]) == pytest.approx(
            abs(result["MH4"]["pan_offset_deg"])
        )
        assert abs(result["MH2"]["pan_offset_deg"]) == pytest.approx(
            abs(result["MH3"]["pan_offset_deg"])
        )

    def test_mirror_lr_with_tilt_offset(self):
        """Test mirror_lr applies tilt offset."""
        transform = MirrorLRTransform()
        targets = ["MH1", "MH2"]
        base_movement = {"pattern": "static"}
        params = {"pan_spread_deg": 20, "tilt_offset_deg": 10}

        result = transform.apply(targets, base_movement, params)

        assert result["MH1"]["tilt_offset_deg"] == 10
        assert result["MH2"]["tilt_offset_deg"] == 10


class TestWaveLRTransform:
    """Tests for WaveLRTransform."""

    def test_wave_lr_4_fixtures_auto_spacing(self):
        """Test wave_lr with 4 fixtures uses 90° spacing."""
        transform = WaveLRTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "sweep_lr"}

        result = transform.apply(targets, base_movement, {"phase_spacing": "auto"})

        assert len(result) == 4
        assert result["MH1"]["phase_deg"] == 0
        assert result["MH2"]["phase_deg"] == 90
        assert result["MH3"]["phase_deg"] == 180
        assert result["MH4"]["phase_deg"] == 270

    def test_wave_lr_manual_spacing(self):
        """Test wave_lr with manual phase spacing."""
        transform = WaveLRTransform()
        targets = ["MH1", "MH2", "MH3"]
        base_movement = {"pattern": "sweep_lr"}

        result = transform.apply(targets, base_movement, {"phase_spacing": 120})

        assert result["MH1"]["phase_deg"] == 0
        assert result["MH2"]["phase_deg"] == 120
        assert result["MH3"]["phase_deg"] == 240

    def test_wave_lr_reverse_direction(self):
        """Test wave_lr with reverse direction."""
        transform = WaveLRTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "sweep_lr"}

        result = transform.apply(targets, base_movement, {"direction": "reverse"})

        # Reverse order: last fixture has 0°, first has largest phase
        assert result["MH1"]["phase_deg"] == 270
        assert result["MH2"]["phase_deg"] == 180
        assert result["MH3"]["phase_deg"] == 90
        assert result["MH4"]["phase_deg"] == 0


class TestFanTransform:
    """Tests for FanTransform."""

    def test_fan_4_fixtures(self):
        """Test fan with 4 fixtures."""
        transform = FanTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}
        params = {"total_spread_deg": 60}

        result = transform.apply(targets, base_movement, params)

        assert len(result) == 4

        # Check distributed offsets
        offsets = [result[t]["pan_offset_deg"] for t in targets]
        assert offsets[0] < offsets[1] < offsets[2] < offsets[3]
        assert offsets[0] < 0  # Left side
        assert offsets[3] > 0  # Right side

    def test_fan_with_center_offset(self):
        """Test fan with center offset."""
        transform = FanTransform()
        targets = ["MH1", "MH2"]
        base_movement = {"pattern": "static"}
        params = {"total_spread_deg": 40, "center_offset_deg": 20}

        result = transform.apply(targets, base_movement, params)

        # Both offsets should be shifted by center_offset
        assert result["MH1"]["pan_offset_deg"] == pytest.approx(20 - 20)  # center - half_spread
        assert result["MH2"]["pan_offset_deg"] == pytest.approx(20 + 20)  # center + half_spread


class TestChevronVTransform:
    """Tests for ChevronVTransform."""

    def test_chevron_v_4_fixtures(self):
        """Test chevron_v with 4 fixtures."""
        transform = ChevronVTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}
        params = {"tightness": 0.65, "max_outer_pan_deg": 60}

        result = transform.apply(targets, base_movement, params)

        assert len(result) == 4

        # Outer fixtures should have larger pan offsets than inner
        outer_left = abs(result["MH1"]["pan_offset_deg"])
        inner_left = abs(result["MH2"]["pan_offset_deg"])
        assert outer_left > inner_left

    def test_chevron_v_tilt_lift(self):
        """Test chevron_v applies tilt lift to inner fixtures."""
        transform = ChevronVTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}
        params = {"inner_tilt_lift_deg": 8}

        result = transform.apply(targets, base_movement, params)

        # Inner fixtures (MH2, MH3) should have tilt lift
        assert result["MH2"].get("tilt_offset_deg", 0) > 0
        assert result["MH3"].get("tilt_offset_deg", 0) > 0
        # Outer fixtures (MH1, MH4) should not
        assert result["MH1"].get("tilt_offset_deg", 0) == 0
        assert result["MH4"].get("tilt_offset_deg", 0) == 0


class TestAudienceScanTransform:
    """Tests for AudienceScanTransform."""

    def test_audience_scan_wide_4_fixtures(self):
        """Test audience_scan with wide coverage and 4 fixtures."""
        transform = AudienceScanTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "sweep_lr"}
        params = {"coverage_width": "wide"}

        result = transform.apply(targets, base_movement, params)

        assert len(result) == 4

        # Should match preset for n=4
        assert result["MH1"]["pan_offset_deg"] == -60
        assert result["MH2"]["pan_offset_deg"] == -20
        assert result["MH3"]["pan_offset_deg"] == 20
        assert result["MH4"]["pan_offset_deg"] == 60

    def test_audience_scan_coverage_presets(self):
        """Test different coverage presets."""
        transform = AudienceScanTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}

        # Test narrow coverage
        result_narrow = transform.apply(targets, base_movement, {"coverage_width": "narrow"})
        narrow_spread = (
            result_narrow["MH4"]["pan_offset_deg"] - result_narrow["MH1"]["pan_offset_deg"]
        )

        # Test full coverage
        result_full = transform.apply(targets, base_movement, {"coverage_width": "full"})
        full_spread = result_full["MH4"]["pan_offset_deg"] - result_full["MH1"]["pan_offset_deg"]

        # Full should be wider than narrow
        assert full_spread > narrow_spread


class TestSpotlightClusterTransform:
    """Tests for SpotlightClusterTransform."""

    def test_spotlight_cluster_4_fixtures(self):
        """Test spotlight_cluster with 4 fixtures converging to center."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.spotlight_cluster import (
            SpotlightClusterTransform,
        )

        transform = SpotlightClusterTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}
        params = {"target_pan_offset_deg": 0.0, "spread": 0.2}

        result = transform.apply(targets, base_movement, params)

        assert len(result) == 4
        # All fixtures should have pan offsets
        assert all("pan_offset_deg" in r for r in result.values())
        # With spread > 0, offsets should not all be identical
        offsets = [r["pan_offset_deg"] for r in result.values()]
        assert len(set(offsets)) > 1  # Not all the same

    def test_spotlight_cluster_perfect_convergence(self):
        """Test spotlight_cluster with spread=0 creates perfect convergence."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.spotlight_cluster import (
            SpotlightClusterTransform,
        )

        transform = SpotlightClusterTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}
        params = {"target_pan_offset_deg": 10.0, "spread": 0.0}

        result = transform.apply(targets, base_movement, params)

        # All fixtures should converge to same point (target_pan_offset_deg)
        assert all(r["pan_offset_deg"] == 10.0 for r in result.values())

    def test_spotlight_cluster_target_offset(self):
        """Test spotlight_cluster converges toward non-zero target."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.spotlight_cluster import (
            SpotlightClusterTransform,
        )

        transform = SpotlightClusterTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}
        params = {"target_pan_offset_deg": -20.0, "spread": 0.1}

        result = transform.apply(targets, base_movement, params)

        # All offsets should be close to target (-20°)
        offsets = [r["pan_offset_deg"] for r in result.values()]
        assert all(-25.0 < offset < -15.0 for offset in offsets)

    def test_spotlight_cluster_tilt_role(self):
        """Test spotlight_cluster applies tilt role."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.spotlight_cluster import (
            SpotlightClusterTransform,
        )

        transform = SpotlightClusterTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}
        params = {"target_pan_offset_deg": 0.0, "spread": 0.2, "tilt": "up"}

        result = transform.apply(targets, base_movement, params)

        # All fixtures should have tilt_role set
        assert all(r.get("tilt_role") == "up" for r in result.values())

    def test_spotlight_cluster_single_fixture(self):
        """Test spotlight_cluster with single fixture."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.spotlight_cluster import (
            SpotlightClusterTransform,
        )

        transform = SpotlightClusterTransform()
        targets = ["MH1"]
        base_movement = {"pattern": "static"}
        params = {"target_pan_offset_deg": 15.0}

        result = transform.apply(targets, base_movement, params)

        assert len(result) == 1
        assert result["MH1"]["pan_offset_deg"] == 15.0

    def test_spotlight_cluster_spread_clamping(self):
        """Test spotlight_cluster clamps spread to valid range."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.spotlight_cluster import (
            SpotlightClusterTransform,
        )

        transform = SpotlightClusterTransform()
        targets = ["MH1", "MH2"]
        base_movement = {"pattern": "static"}

        # Test spread > 1.0 gets clamped to 1.0
        result_high = transform.apply(targets, base_movement, {"spread": 5.0})
        # Test spread < 0.0 gets clamped to 0.0
        result_low = transform.apply(targets, base_movement, {"spread": -1.0})

        # Both should produce valid results
        assert len(result_high) == 2
        assert len(result_low) == 2

    def test_spotlight_cluster_default_tilt_role(self):
        """Test spotlight_cluster defaults to above_horizon for tilt role."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.spotlight_cluster import (
            SpotlightClusterTransform,
        )

        transform = SpotlightClusterTransform()
        targets = ["MH1", "MH2"]
        base_movement = {"pattern": "static"}
        params = {}  # No tilt specified

        result = transform.apply(targets, base_movement, params)

        # Should default to above_horizon
        assert all(r.get("tilt_role") == "above_horizon" for r in result.values())


class TestRainbowArcTransform:
    """Tests for RainbowArcTransform."""

    def test_rainbow_arc_4_fixtures_curved(self):
        """Test rainbow_arc with 4 fixtures in curved mode."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.rainbow_arc import (
            RainbowArcTransform,
        )

        transform = RainbowArcTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "sweep_lr"}
        params = {"arc_width_deg": 120.0, "arc_height": "curved", "center_tilt_lift_deg": 7.0}

        result = transform.apply(targets, base_movement, params)

        assert len(result) == 4
        # Check pan offsets span the arc
        pan_offsets = [r["pan_offset_deg"] for r in result.values()]
        assert min(pan_offsets) < -50  # Left edge
        assert max(pan_offsets) > 50  # Right edge

        # Check tilt offsets form parabolic curve
        tilt_offsets = [r["tilt_offset_deg"] for r in result.values()]
        # Edges should be lower than center
        assert tilt_offsets[0] < tilt_offsets[1]  # Left edge < left-center
        assert tilt_offsets[3] < tilt_offsets[2]  # Right edge < right-center

    def test_rainbow_arc_flat_mode(self):
        """Test rainbow_arc with flat mode (no tilt variation)."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.rainbow_arc import (
            RainbowArcTransform,
        )

        transform = RainbowArcTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "sweep_lr"}
        params = {"arc_width_deg": 120.0, "arc_height": "flat"}

        result = transform.apply(targets, base_movement, params)

        # All tilt offsets should be 0 in flat mode
        tilt_offsets = [r["tilt_offset_deg"] for r in result.values()]
        assert all(offset == 0.0 for offset in tilt_offsets)

    def test_rainbow_arc_narrow_arc(self):
        """Test rainbow_arc with narrow arc width."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.rainbow_arc import (
            RainbowArcTransform,
        )

        transform = RainbowArcTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}
        params = {"arc_width_deg": 60.0}

        result = transform.apply(targets, base_movement, params)

        # Pan offsets should be within ±30°
        pan_offsets = [r["pan_offset_deg"] for r in result.values()]
        assert all(-35 < offset < 35 for offset in pan_offsets)

    def test_rainbow_arc_wide_arc(self):
        """Test rainbow_arc with very wide arc width."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.rainbow_arc import (
            RainbowArcTransform,
        )

        transform = RainbowArcTransform()
        targets = ["MH1", "MH2", "MH3"]
        base_movement = {"pattern": "static"}
        params = {"arc_width_deg": 160.0}

        result = transform.apply(targets, base_movement, params)

        # Pan offsets should span ±80°
        pan_offsets = [r["pan_offset_deg"] for r in result.values()]
        assert min(pan_offsets) < -70
        assert max(pan_offsets) > 70

    def test_rainbow_arc_tilt_role(self):
        """Test rainbow_arc applies tilt role."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.rainbow_arc import (
            RainbowArcTransform,
        )

        transform = RainbowArcTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}
        params = {"arc_width_deg": 120.0, "tilt": "up"}

        result = transform.apply(targets, base_movement, params)

        # All fixtures should have tilt_role set
        assert all(r.get("tilt_role") == "up" for r in result.values())

    def test_rainbow_arc_default_tilt_role(self):
        """Test rainbow_arc defaults to above_horizon for tilt role."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.rainbow_arc import (
            RainbowArcTransform,
        )

        transform = RainbowArcTransform()
        targets = ["MH1", "MH2"]
        base_movement = {"pattern": "static"}
        params = {}  # No tilt specified

        result = transform.apply(targets, base_movement, params)

        # Should default to above_horizon
        assert all(r.get("tilt_role") == "above_horizon" for r in result.values())

    def test_rainbow_arc_parameter_clamping(self):
        """Test rainbow_arc clamps parameters to valid ranges."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.rainbow_arc import (
            RainbowArcTransform,
        )

        transform = RainbowArcTransform()
        targets = ["MH1", "MH2", "MH3"]
        base_movement = {"pattern": "static"}

        # Test arc_width clamping (should clamp to 30-160)
        result_low = transform.apply(targets, base_movement, {"arc_width_deg": 10.0})
        result_high = transform.apply(targets, base_movement, {"arc_width_deg": 200.0})

        # Test center_tilt_lift clamping (should clamp to 0-15)
        result_negative = transform.apply(
            targets, base_movement, {"arc_height": "curved", "center_tilt_lift_deg": -5.0}
        )
        result_too_high = transform.apply(
            targets, base_movement, {"arc_height": "curved", "center_tilt_lift_deg": 30.0}
        )

        # All should produce valid results
        assert len(result_low) == 3
        assert len(result_high) == 3
        assert len(result_negative) == 3
        assert len(result_too_high) == 3

    def test_rainbow_arc_single_fixture(self):
        """Test rainbow_arc with single fixture (edge case)."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.rainbow_arc import (
            RainbowArcTransform,
        )

        transform = RainbowArcTransform()
        targets = ["MH1"]
        base_movement = {"pattern": "static"}
        params = {"arc_width_deg": 120.0}

        result = transform.apply(targets, base_movement, params)

        assert len(result) == 1
        # Single fixture should be at center (0°)
        assert result["MH1"]["pan_offset_deg"] == 0.0


class TestGeometryIntegration:
    """Integration tests for geometry engine."""

    def test_engine_applies_wave_lr(self):
        """Test engine correctly applies wave_lr geometry."""
        engine = GeometryEngine()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "sweep_lr", "amplitude_deg": 60}

        result = engine.apply_geometry("wave_lr", targets, base_movement)

        assert len(result) == 4
        # All fixtures should have base pattern
        assert all(r["pattern"] == "sweep_lr" for r in result.values())
        # All fixtures should have base amplitude
        assert all(r["amplitude_deg"] == 60 for r in result.values())
        # Fixtures should have progressive phase offsets
        assert result["MH1"]["phase_deg"] == 0
        assert result["MH2"]["phase_deg"] == 90
        assert result["MH3"]["phase_deg"] == 180
        assert result["MH4"]["phase_deg"] == 270

    def test_engine_applies_mirror_lr(self):
        """Test engine correctly applies mirror_lr geometry."""
        engine = GeometryEngine()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "tilt_rock"}

        result = engine.apply_geometry("mirror_lr", targets, base_movement, {"pan_spread_deg": 40})

        assert len(result) == 4
        # Check symmetry
        assert abs(result["MH1"]["pan_offset_deg"]) == pytest.approx(
            abs(result["MH4"]["pan_offset_deg"])
        )
        assert abs(result["MH2"]["pan_offset_deg"]) == pytest.approx(
            abs(result["MH3"]["pan_offset_deg"])
        )

    def test_engine_applies_spotlight_cluster(self):
        """Test engine correctly applies spotlight_cluster geometry."""
        engine = GeometryEngine()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}

        result = engine.apply_geometry(
            "spotlight_cluster",
            targets,
            base_movement,
            {"target_pan_offset_deg": 5.0, "spread": 0.2, "tilt": "above_horizon"},
        )

        assert len(result) == 4
        # All fixtures should have pan offsets close to target
        offsets = [r["pan_offset_deg"] for r in result.values()]
        assert all(-10.0 < offset < 15.0 for offset in offsets)
        # All fixtures should have tilt_role
        assert all(r.get("tilt_role") == "above_horizon" for r in result.values())

    def test_engine_applies_rainbow_arc(self):
        """Test engine correctly applies rainbow_arc geometry."""
        engine = GeometryEngine()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "wave_lr"}

        result = engine.apply_geometry(
            "rainbow_arc",
            targets,
            base_movement,
            {"arc_width_deg": 120.0, "arc_height": "curved", "tilt": "above_horizon"},
        )

        assert len(result) == 4
        # Check pan offsets span the arc
        pan_offsets = [r["pan_offset_deg"] for r in result.values()]
        assert min(pan_offsets) < -50  # Left side
        assert max(pan_offsets) > 50  # Right side
        # All fixtures should have tilt_role
        assert all(r.get("tilt_role") == "above_horizon" for r in result.values())


class TestAlternatingUpDownTransform:
    """Tests for AlternatingUpDownTransform (geometry)."""

    def test_alternating_updown_basic(self):
        """Test basic alternating up/down pattern."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.alternating_updown import (
            AlternatingUpDownTransform,
        )

        transform = AlternatingUpDownTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}

        result = transform.apply(targets, base_movement, {})

        assert len(result) == 4
        # Check alternating tilt roles (default: every_other)
        assert result["MH1"]["tilt_role"] == "up"  # idx 0 (even)
        assert result["MH2"]["tilt_role"] == "above_horizon"  # idx 1 (odd)
        assert result["MH3"]["tilt_role"] == "up"  # idx 2 (even)
        assert result["MH4"]["tilt_role"] == "above_horizon"  # idx 3 (odd)

    def test_alternating_updown_pairs_pattern(self):
        """Test alternating in pairs pattern."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.alternating_updown import (
            AlternatingUpDownTransform,
        )

        transform = AlternatingUpDownTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}

        result = transform.apply(targets, base_movement, {"pattern": "pairs"})

        assert len(result) == 4
        # Check pairs pattern: 0,0,1,1
        assert result["MH1"]["tilt_role"] == "up"  # idx 0, pair 0
        assert result["MH2"]["tilt_role"] == "up"  # idx 1, pair 0
        assert result["MH3"]["tilt_role"] == "above_horizon"  # idx 2, pair 1
        assert result["MH4"]["tilt_role"] == "above_horizon"  # idx 3, pair 1

    def test_alternating_updown_custom_tilt_roles(self):
        """Test alternating with custom tilt roles."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.alternating_updown import (
            AlternatingUpDownTransform,
        )

        transform = AlternatingUpDownTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}

        result = transform.apply(
            targets,
            base_movement,
            {"up_tilt_role": "above_horizon", "down_tilt_role": "zero"},
        )

        assert len(result) == 4
        assert result["MH1"]["tilt_role"] == "above_horizon"
        assert result["MH2"]["tilt_role"] == "zero"
        assert result["MH3"]["tilt_role"] == "above_horizon"
        assert result["MH4"]["tilt_role"] == "zero"

    def test_alternating_updown_with_tilt_offset(self):
        """Test alternating with shared tilt offset."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.alternating_updown import (
            AlternatingUpDownTransform,
        )

        transform = AlternatingUpDownTransform()
        targets = ["MH1", "MH2"]
        base_movement = {"pattern": "static"}

        result = transform.apply(targets, base_movement, {"tilt_offset_deg": 10.0})

        assert len(result) == 2
        # Both should have the tilt offset applied
        assert result["MH1"]["tilt_offset_deg"] == 10.0
        assert result["MH2"]["tilt_offset_deg"] == 10.0

    def test_alternating_updown_min_fixtures_warning(self):
        """Test warning with less than 2 fixtures."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.alternating_updown import (
            AlternatingUpDownTransform,
        )

        transform = AlternatingUpDownTransform()
        targets = ["MH1"]
        base_movement = {"pattern": "static"}

        result = transform.apply(targets, base_movement, {})

        # Should still return result for single fixture
        assert len(result) == 1
        assert "MH1" in result

    def test_alternating_updown_invalid_pattern(self):
        """Test fallback with invalid pattern."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.alternating_updown import (
            AlternatingUpDownTransform,
        )

        transform = AlternatingUpDownTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}

        # Invalid pattern should fallback to every_other
        result = transform.apply(targets, base_movement, {"pattern": "invalid"})

        assert len(result) == 4
        # Should use default every_other pattern
        assert result["MH1"]["tilt_role"] == "up"
        assert result["MH2"]["tilt_role"] == "above_horizon"


class TestTunnelConeTransform:
    """Tests for TunnelConeTransform (geometry)."""

    def test_tunnel_cone_basic(self):
        """Test basic tunnel/cone circular distribution."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.tunnel_cone import (
            TunnelConeTransform,
        )

        transform = TunnelConeTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}

        result = transform.apply(targets, base_movement, {})

        assert len(result) == 4
        # All fixtures should have pan offsets
        for fixture_result in result.values():
            assert "pan_offset_deg" in fixture_result
            # Check tilt role applied
            assert fixture_result.get("tilt_role") == "above_horizon"

    def test_tunnel_cone_circular_distribution(self):
        """Test that fixtures are distributed in circular pattern."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.tunnel_cone import (
            TunnelConeTransform,
        )

        transform = TunnelConeTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}

        result = transform.apply(
            targets, base_movement, {"pan_spread_deg": 90.0, "center_pan_deg": 0.0}
        )

        # Extract pan offsets
        pan_offsets = [result[t]["pan_offset_deg"] for t in targets]

        # Offsets should span the range with circular distribution
        assert min(pan_offsets) < 0  # Some fixtures left
        assert max(pan_offsets) > 0  # Some fixtures right
        # Range should be within pan_spread_deg
        assert max(pan_offsets) - min(pan_offsets) <= 90.0

    def test_tunnel_cone_radius_effect(self):
        """Test radius parameter affects cone tightness."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.tunnel_cone import (
            TunnelConeTransform,
        )

        transform = TunnelConeTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}

        # Tight cone (radius=0.1)
        result_tight = transform.apply(
            targets, base_movement, {"radius": 0.1, "pan_spread_deg": 90.0}
        )

        # Wide cone (radius=0.9)
        result_wide = transform.apply(
            targets, base_movement, {"radius": 0.9, "pan_spread_deg": 90.0}
        )

        # Both should have results
        assert len(result_tight) == 4
        assert len(result_wide) == 4

        # Wider radius should generally create more tilt variation
        tight_tilt_offsets = [abs(r.get("tilt_offset_deg", 0)) for r in result_tight.values()]
        wide_tilt_offsets = [abs(r.get("tilt_offset_deg", 0)) for r in result_wide.values()]

        # Wide cone should have larger tilt variations on average
        assert max(wide_tilt_offsets) >= max(tight_tilt_offsets)

    def test_tunnel_cone_custom_tilt(self):
        """Test tunnel/cone with custom tilt role."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.tunnel_cone import (
            TunnelConeTransform,
        )

        transform = TunnelConeTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}

        result = transform.apply(targets, base_movement, {"tilt": "up"})

        assert len(result) == 4
        # All fixtures should have "up" tilt role
        for fixture_result in result.values():
            assert fixture_result.get("tilt_role") == "up"

    def test_tunnel_cone_with_center_offset(self):
        """Test tunnel/cone with center pan offset."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.tunnel_cone import (
            TunnelConeTransform,
        )

        transform = TunnelConeTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}

        result = transform.apply(
            targets, base_movement, {"center_pan_deg": 20.0, "pan_spread_deg": 60.0}
        )

        # All pan offsets should be shifted by center offset
        pan_offsets = [result[t]["pan_offset_deg"] for t in targets]

        # The average should be near the center offset
        avg_offset = sum(pan_offsets) / len(pan_offsets)
        assert abs(avg_offset - 20.0) < 10.0  # Within reasonable range

    def test_tunnel_cone_min_fixtures_warning(self):
        """Test warning with less than 4 fixtures."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.tunnel_cone import (
            TunnelConeTransform,
        )

        transform = TunnelConeTransform()
        targets = ["MH1", "MH2"]  # Less than optimal 4
        base_movement = {"pattern": "static"}

        result = transform.apply(targets, base_movement, {})

        # Should still return result
        assert len(result) == 2
        assert "MH1" in result
        assert "MH2" in result

    def test_tunnel_cone_radius_clamping(self):
        """Test radius is clamped to 0.0-1.0 range."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.tunnel_cone import (
            TunnelConeTransform,
        )

        transform = TunnelConeTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}

        # Test with out-of-range radius values
        result_negative = transform.apply(targets, base_movement, {"radius": -0.5})
        result_excessive = transform.apply(targets, base_movement, {"radius": 1.5})

        # Both should still work (clamped internally)
        assert len(result_negative) == 4
        assert len(result_excessive) == 4

    def test_tunnel_cone_pan_spread_validation(self):
        """Test pan_spread_deg validation and clamping."""
        from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.patterns.tunnel_cone import (
            TunnelConeTransform,
        )

        transform = TunnelConeTransform()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}

        # Test with out-of-range pan_spread values
        result_low = transform.apply(targets, base_movement, {"pan_spread_deg": 30.0})
        result_high = transform.apply(targets, base_movement, {"pan_spread_deg": 150.0})

        # Both should still work (clamped to 60-120 range)
        assert len(result_low) == 4
        assert len(result_high) == 4


class TestGeometriesIntegration:
    """Integration tests for geometries."""

    def test_engine_has_alternating_updown(self):
        """Test engine includes alternating_updown geometry."""
        engine = GeometryEngine()
        assert "alternating_updown" in engine.transforms

    def test_engine_has_tunnel_cone(self):
        """Test engine includes tunnel_cone geometry."""
        engine = GeometryEngine()
        assert "tunnel_cone" in engine.transforms

    def test_engine_applies_alternating_updown(self):
        """Test engine correctly applies alternating_updown geometry."""
        engine = GeometryEngine()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}

        result = engine.apply_geometry(
            "alternating_updown",
            targets,
            base_movement,
            {"pattern": "every_other"},
        )

        assert len(result) == 4
        # Check alternating pattern
        assert result["MH1"]["tilt_role"] == "up"
        assert result["MH2"]["tilt_role"] == "above_horizon"
        assert result["MH3"]["tilt_role"] == "up"
        assert result["MH4"]["tilt_role"] == "above_horizon"

    def test_engine_applies_tunnel_cone(self):
        """Test engine correctly applies tunnel_cone geometry."""
        engine = GeometryEngine()
        targets = ["MH1", "MH2", "MH3", "MH4"]
        base_movement = {"pattern": "static"}

        result = engine.apply_geometry(
            "tunnel_cone",
            targets,
            base_movement,
            {"radius": 0.5, "tilt": "above_horizon", "pan_spread_deg": 90.0},
        )

        assert len(result) == 4
        # All fixtures should have pan offsets and tilt roles
        for fixture_result in result.values():
            assert "pan_offset_deg" in fixture_result
            assert fixture_result.get("tilt_role") == "above_horizon"

    def test_engine_contains_offsets_alternating_updown(self):
        """Test contains_offsets returns True for alternating_updown."""
        engine = GeometryEngine()
        assert engine.contains_offsets("alternating_updown", {}) is True

    def test_engine_contains_offsets_tunnel_cone(self):
        """Test contains_offsets returns True for tunnel_cone with spread."""
        engine = GeometryEngine()
        assert engine.contains_offsets("tunnel_cone", {"pan_spread_deg": 90.0}) is True

    def test_engine_contains_offsets_tunnel_cone_zero_spread(self):
        """Test contains_offsets returns False for tunnel_cone with zero spread."""
        engine = GeometryEngine()
        assert engine.contains_offsets("tunnel_cone", {"pan_spread_deg": 0.0}) is False
