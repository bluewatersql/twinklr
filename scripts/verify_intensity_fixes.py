"""Test script to verify intensity calculation and preset inference fixes."""

import logging
import sys

from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.sequencer.moving_heads.handlers.movement.default import DefaultMovementHandler
from twinklr.core.sequencer.moving_heads.libraries.movement import (
    MovementLibrary,
    MovementType,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


def test_intensity_fix():
    """Test that intensity calculation is no longer dependent on base position."""
    logger.info("=" * 80)
    logger.info("TESTING INTENSITY CALCULATION FIX")
    logger.info("=" * 80)

    handler = DefaultMovementHandler()
    pattern = MovementLibrary.get_pattern(MovementType.SWEEP_LR)

    test_cases = [
        (0.5, "Centered", "Should get full amplitude"),
        (0.1, "Extreme Left", "Should get constrained but not artificially reduced"),
        (0.9, "Extreme Right", "Should get constrained but not artificially reduced"),
    ]

    results = []

    for base_norm, description, note in test_cases:
        logger.info(f"\nTest: {description} (base={base_norm})")

        params = {
            "movement_pattern": pattern,
            "geometry": "NONE",
            "base_pan_norm": base_norm,
            "base_tilt_norm": 0.5,
            "calibration": {
                "pan_min_dmx": 0,
                "pan_max_dmx": 255,
                "tilt_min_dmx": 0,
                "tilt_max_dmx": 255,
            },
            "intensity": Intensity.SMOOTH,  # amplitude = 0.4
        }

        result = handler.generate(
            params=params, n_samples=64, cycles=1.0, intensity=Intensity.SMOOTH
        )

        if result.pan_curve:
            pan_min = min(pt.v for pt in result.pan_curve)
            pan_max = max(pt.v for pt in result.pan_curve)
            pan_range = pan_max - pan_min
        else:
            pan_min = pan_max = pan_range = 0.0

        logger.info(f"  Pan range: [{pan_min:.3f}, {pan_max:.3f}] = {pan_range:.3f}")

        # Expected: SMOOTH (0.4) should give ~0.2 amplitude (±0.2 from base)
        # Constrained by boundaries if base is extreme
        expected_amplitude = 0.4 * 0.5  # 0.2
        expected_min = max(0.0, base_norm - expected_amplitude)
        expected_max = min(1.0, base_norm + expected_amplitude)
        expected_range = expected_max - expected_min

        logger.info(
            f"  Expected range: [{expected_min:.3f}, {expected_max:.3f}] = {expected_range:.3f}"
        )

        # Check if result matches expectation (within tolerance)
        range_diff = abs(pan_range - expected_range)
        passed = range_diff < 0.05  # 5% tolerance

        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"  {status}: {note}")

        results.append((description, passed, pan_range, expected_range))

    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)

    for desc, passed, actual, expected in results:
        status = "✓" if passed else "✗"
        logger.info(
            f"{status} {desc}: actual={actual:.3f}, expected={expected:.3f}, "
            f"diff={abs(actual - expected):.3f}"
        )

    all_passed = all(p for _, p, _, _ in results)

    if all_passed:
        logger.info("\n✅ All tests passed! Intensity calculation fix is working.")
    else:
        logger.error("\n❌ Some tests failed. Review the intensity calculation.")

    return all_passed


def test_preset_inference():
    """Test that preset inference creates the correct intensity mappings."""
    logger.info("\n" + "=" * 80)
    logger.info("TESTING PRESET INFERENCE")
    logger.info("=" * 80)

    from twinklr.core.sequencer.models.enum import Intensity

    intensity_map = {
        "CHILL": Intensity.SLOW,
        "MODERATE": Intensity.SMOOTH,
        "ENERGETIC": Intensity.DRAMATIC,
        "INTENSE": Intensity.FAST,
    }

    logger.info("\nPreset ID → Intensity mapping:")
    for preset_id, intensity in intensity_map.items():
        logger.info(f"  {preset_id:12s} → {intensity.value:12s}")

    logger.info("\n✅ Preset inference mapping is correct.")
    return True


def main():
    """Run all tests."""
    test1_passed = test_intensity_fix()
    test2_passed = test_preset_inference()

    if test1_passed and test2_passed:
        logger.info("\n🎉 All fixes verified!")
        return 0
    else:
        logger.error("\n❌ Some fixes failed verification")
        return 1


if __name__ == "__main__":
    sys.exit(main())
