"""Test center offset formula fix.

This script verifies that the center_offset formula fix (removing * 2 factor)
correctly keeps the adjusted base position within safe bounds.
"""

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


def test_center_offset_formula():
    """Test that center_offset formula keeps adjusted_base within bounds."""
    logger.info("=" * 80)
    logger.info("CENTER OFFSET FORMULA FIX VERIFICATION")
    logger.info("=" * 80)

    # Test parameters
    base_pan_norm = 0.5
    pan_min_dmx = 64
    pan_max_dmx = 192

    # Calculate max amplitude
    pan_min_norm = pan_min_dmx / 255.0
    pan_max_norm = pan_max_dmx / 255.0
    pan_max_amplitude_norm = min(base_pan_norm - pan_min_norm, pan_max_norm - base_pan_norm)

    logger.info(f"Base: {base_pan_norm:.3f}")
    logger.info(
        f"Pan Range: [{pan_min_dmx}, {pan_max_dmx}] → [{pan_min_norm:.3f}, {pan_max_norm:.3f}]"
    )
    logger.info(f"Max Amplitude: {pan_max_amplitude_norm:.3f}\n")

    # Test various center_offset values
    test_cases = [
        (0.0, "Far left"),
        (0.25, "Left"),
        (0.5, "Center"),
        (0.75, "Right"),
        (1.0, "Far right"),
    ]

    logger.info("Testing center_offset values with NEW formula (no * 2):")
    logger.info("  offset | center_norm | adjusted_base | in_bounds | peak | trough | all_ok")
    logger.info("-" * 90)

    all_passed = True

    for center_offset, _ in test_cases:
        # New formula (without * 2)
        center_offset_normalized_new = (center_offset - 0.5) * pan_max_amplitude_norm * 1.0
        adjusted_base_new = base_pan_norm + center_offset_normalized_new

        # Check if new formula keeps base in bounds
        in_bounds_new = 0.0 <= adjusted_base_new <= 1.0

        # Calculate expected peak/trough with new formula
        effective_amplitude = pan_max_amplitude_norm * 1.0  # Full amplitude
        peak_new = adjusted_base_new + effective_amplitude
        trough_new = adjusted_base_new - effective_amplitude

        peak_in_bounds = 0.0 <= peak_new <= 1.0
        trough_in_bounds = 0.0 <= trough_new <= 1.0
        all_ok = in_bounds_new and peak_in_bounds and trough_in_bounds

        status = "✓" if all_ok else "✗"
        if not all_ok:
            all_passed = False

        logger.info(
            f"  {center_offset:4.2f}  | {center_offset_normalized_new:11.3f} | "
            f"{adjusted_base_new:13.3f} | {in_bounds_new!s:9s} | {peak_new:4.3f} | {trough_new:6.3f} | {status}"
        )

    logger.info("\n" + "=" * 90)
    logger.info("Comparison with OLD formula (* 2):")
    logger.info("  offset | center_norm | adjusted_base | in_bounds | would_clamp")
    logger.info("-" * 90)

    for center_offset, _ in test_cases:
        # Old formula (with * 2)
        center_offset_normalized_old = (center_offset - 0.5) * pan_max_amplitude_norm * 2
        adjusted_base_old = base_pan_norm + center_offset_normalized_old
        in_bounds_old = 0.0 <= adjusted_base_old <= 1.0
        would_clamp = not in_bounds_old

        status = "YES ⚠️" if would_clamp else "NO"

        logger.info(
            f"  {center_offset:4.2f}  | {center_offset_normalized_old:11.3f} | "
            f"{adjusted_base_old:13.3f} | {in_bounds_old!s:9s} | {status}"
        )

    logger.info("")

    if all_passed:
        logger.info("✅ All test cases passed! Center offset formula fix is working correctly.")
        logger.info("   The new formula (without * 2) keeps all values within bounds.")
    else:
        logger.error("❌ Some test cases failed. Review the formula.")

    return all_passed


def main():
    """Run verification test."""
    success = test_center_offset_formula()
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
