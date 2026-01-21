"""Test geometry optimization for grouped vs individual effects."""

from __future__ import annotations

from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.engine import GeometryEngine


def test_contains_offsets_no_geometry():
    """Test that no geometry returns False (no offsets = should group)."""
    engine = GeometryEngine()
    result = engine.contains_offsets(None, {})
    assert result is False, "No geometry should have no offsets (allow grouping)"


def test_contains_offsets_wall_wash_tight():
    """Test that wall_wash with tight spacing returns False (no offsets = should group)."""
    engine = GeometryEngine()
    result = engine.contains_offsets("wall_wash", {"spacing": "tight"})
    assert result is False, "wall_wash tight should have no offsets (allow grouping)"


def test_contains_offsets_wall_wash_medium():
    """Test that wall_wash with medium spacing returns True (has offsets = should not group)."""
    engine = GeometryEngine()
    result = engine.contains_offsets("wall_wash", {"spacing": "medium"})
    assert result is True, "wall_wash medium should have offsets (require individual effects)"


def test_contains_offsets_wall_wash_wide():
    """Test that wall_wash with wide spacing returns True (has offsets = should not group)."""
    engine = GeometryEngine()
    result = engine.contains_offsets("wall_wash", {"spacing": "wide"})
    assert result is True, "wall_wash wide should have offsets (require individual effects)"


def test_contains_offsets_fan_zero():
    """Test that fan with 0 spread returns False (no offsets = should group)."""
    engine = GeometryEngine()
    result = engine.contains_offsets("fan", {"total_spread_deg": 0})
    assert result is False, "fan with 0 spread should have no offsets (allow grouping)"


def test_contains_offsets_fan_nonzero():
    """Test that fan with non-zero spread returns True (has offsets = should not group)."""
    engine = GeometryEngine()
    result = engine.contains_offsets("fan", {"total_spread_deg": 60})
    assert result is True, "fan with 60 spread should have offsets (require individual effects)"


def test_contains_offsets_fan_default():
    """Test that fan with default params (60° spread) returns True (has offsets)."""
    engine = GeometryEngine()
    result = engine.contains_offsets("fan", {})
    assert result is True, (
        "fan with default 60° spread should have offsets (require individual effects)"
    )


def test_contains_offsets_wave_lr():
    """Test that wave_lr always returns True (inherently has offsets)."""
    engine = GeometryEngine()
    result = engine.contains_offsets("wave_lr", {})
    assert result is True, "wave_lr should always have offsets (require individual effects)"


def test_contains_offsets_mirror_lr():
    """Test that mirror_lr always returns True (inherently has offsets)."""
    engine = GeometryEngine()
    result = engine.contains_offsets("mirror_lr", {})
    assert result is True, "mirror_lr should always have offsets (require individual effects)"


def test_wall_wash_tight_actually_identical():
    """Verify that wall_wash tight actually produces identical movements."""
    engine = GeometryEngine()
    targets = ["MH1", "MH2", "MH3", "MH4"]
    base_movement = {"pattern": "static", "pan_center": 128, "tilt_center": 47}

    movements = engine.apply_geometry("wall_wash", targets, base_movement, {"spacing": "tight"})

    # Check all movements are identical
    first_movement = movements[targets[0]]
    for target in targets[1:]:
        assert movements[target] == first_movement, f"{target} movement differs from MH1"

    # Check all pan offsets are 0
    for target, movement in movements.items():
        pan_offset = movement.get("pan_offset_deg", 0)
        assert pan_offset == 0.0, f"{target} has non-zero pan_offset: {pan_offset}"


def test_fan_nonzero_creates_differences():
    """Verify that fan with non-zero spread actually produces different movements."""
    engine = GeometryEngine()
    targets = ["MH1", "MH2", "MH3", "MH4"]
    base_movement = {"pattern": "static", "pan_center": 128, "tilt_center": 47}

    movements = engine.apply_geometry("fan", targets, base_movement, {"total_spread_deg": 60})

    # Check movements are different
    unique_movements = len({str(m) for m in movements.values()})
    assert unique_movements > 1, "Fan 60° should create different movements"

    # Check pan offsets vary
    pan_offsets = [m.get("pan_offset_deg", 0) for m in movements.values()]
    unique_offsets = len(set(pan_offsets))
    assert unique_offsets > 1, f"Fan 60° should create different pan offsets: {pan_offsets}"
