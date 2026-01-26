"""Diagnostic script to analyze clamping behavior in the rendering pipeline.

This script generates test curves and tracks where clamping occurs at each stage:
1. Movement handler curve generation
2. DMX conversion
3. xLights export

Usage:
    uv run python scripts/diagnose_clamping.py
"""

import logging

from blinkb0t.core.curves.dmx_conversion import movement_curve_to_dmx
from blinkb0t.core.curves.generator import CurveGenerator
from blinkb0t.core.curves.library import CurveLibrary
from blinkb0t.core.curves.models import CurvePoint

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


def analyze_movement_curve_clamping():
    """Analyze clamping behavior for movement curves."""
    logger.info("=" * 80)
    logger.info("MOVEMENT CURVE CLAMPING ANALYSIS")
    logger.info("=" * 80)

    # Test parameters
    base_pan_norm = 0.5
    pan_min_dmx = 64
    pan_max_dmx = 192
    amplitude = 1.0
    center_offset = 0.5  # No offset
    n_samples = 16

    # Calculate max amplitude (from DefaultMovementHandler logic)
    pan_min_norm = pan_min_dmx / 255.0
    pan_max_norm = pan_max_dmx / 255.0
    pan_dist_to_min = base_pan_norm - pan_min_norm
    pan_dist_to_max = pan_max_norm - base_pan_norm
    pan_max_amplitude_norm = min(pan_dist_to_min, pan_dist_to_max)

    logger.info(f"Base Position: {base_pan_norm:.3f}")
    logger.info(
        f"Pan Range: [{pan_min_dmx}, {pan_max_dmx}] DMX → [{pan_min_norm:.3f}, {pan_max_norm:.3f}] norm"
    )
    logger.info(f"Max Amplitude (norm): {pan_max_amplitude_norm:.3f}")
    logger.info(f"Distance to min: {pan_dist_to_min:.3f}, Distance to max: {pan_dist_to_max:.3f}")

    # Apply center offset (from DefaultMovementHandler logic)
    center_offset_normalized = (center_offset - 0.5) * pan_max_amplitude_norm * 2
    adjusted_base_norm = base_pan_norm + center_offset_normalized
    adjusted_base_norm_clamped = max(0.0, min(1.0, adjusted_base_norm))

    logger.info(f"Center Offset: {center_offset} → {center_offset_normalized:.3f} norm")
    logger.info(f"Adjusted Base (before clamp): {adjusted_base_norm:.3f}")
    logger.info(f"Adjusted Base (after clamp): {adjusted_base_norm_clamped:.3f}")

    if adjusted_base_norm != adjusted_base_norm_clamped:
        logger.warning("⚠️  CLAMP #1: adjusted_base_norm was clamped!")

    # Generate base curve
    curve_gen = CurveGenerator()
    base_curve = curve_gen.generate_custom_points(
        curve_id=CurveLibrary.SINE.value,
        num_points=n_samples,
        cycles=1.0,
    )

    # Apply amplitude scaling (from DefaultMovementHandler logic)
    effective_amplitude = pan_max_amplitude_norm * amplitude
    logger.info(f"Effective Amplitude: {effective_amplitude:.3f}")

    scaled_points: list[CurvePoint] = []
    clamp_count_handler = 0

    for point in base_curve:
        offset = point.v - 0.5
        scaled_offset = offset * (effective_amplitude / 0.5)
        new_v = adjusted_base_norm_clamped + scaled_offset

        # Track clamping
        new_v_before_clamp = new_v
        new_v = max(0.0, min(1.0, new_v))

        if new_v != new_v_before_clamp:
            clamp_count_handler += 1

        scaled_points.append(CurvePoint(t=point.t, v=new_v))

    logger.info(f"Handler Stage: {clamp_count_handler}/{len(scaled_points)} points clamped")

    if clamp_count_handler > 0:
        logger.warning(f"⚠️  CLAMP #2: {clamp_count_handler} curve points were clamped in handler!")

    # Show a few sample points
    logger.info("\nSample Points (Handler Output):")
    logger.info("  t    | curve_v | offset | scaled_offset | final_norm | final_dmx")
    logger.info("-" * 70)
    for i in [
        0,
        len(scaled_points) // 4,
        len(scaled_points) // 2,
        3 * len(scaled_points) // 4,
        len(scaled_points) - 1,
    ]:
        pt = scaled_points[i]
        base_pt = base_curve[i]
        offset = base_pt.v - 0.5
        scaled_offset = offset * (effective_amplitude / 0.5)
        dmx_approx = pt.v * 255
        logger.info(
            f" {pt.t:5.2f} | {base_pt.v:7.3f} | {offset:6.3f} | {scaled_offset:13.3f} | {pt.v:10.3f} | {dmx_approx:9.1f}"
        )

    # DMX Conversion Stage
    logger.info("\n" + "=" * 80)
    logger.info("DMX CONVERSION STAGE")
    logger.info("=" * 80)

    base_dmx = base_pan_norm * 255
    amplitude_dmx = effective_amplitude * 255

    logger.info(f"Base DMX: {base_dmx:.1f}")
    logger.info(f"Amplitude DMX: {amplitude_dmx:.1f}")
    logger.info(f"Clamp Range: [{pan_min_dmx}, {pan_max_dmx}] DMX")

    dmx_points = movement_curve_to_dmx(
        points=scaled_points,
        base_dmx=base_dmx,
        amplitude_dmx=amplitude_dmx,
        clamp_min=float(pan_min_dmx),
        clamp_max=float(pan_max_dmx),
    )

    # Check for clamping in DMX conversion
    clamp_count_dmx = 0
    for _, (orig, _) in enumerate(zip(scaled_points, dmx_points, strict=False)):
        # Reconstruct what the DMX value would be without clamping
        dmx_value_unclamped = base_dmx + amplitude_dmx * (orig.v - 0.5)
        dmx_value_clamped = max(pan_min_dmx, min(pan_max_dmx, dmx_value_unclamped))

        # Convert back to normalized
        _dmx_normalized_expected = dmx_value_clamped / 255.0

        if abs(dmx_value_unclamped - dmx_value_clamped) > 0.01:
            clamp_count_dmx += 1

    logger.info(f"DMX Conversion: {clamp_count_dmx}/{len(dmx_points)} points clamped")

    if clamp_count_dmx > 0:
        logger.warning(
            f"⚠️  CLAMP #3: {clamp_count_dmx} curve points were clamped in DMX conversion!"
        )

    # Show DMX sample points
    logger.info("\nSample Points (DMX Conversion Output):")
    logger.info("  t    | handler_norm | dmx_unclamped | dmx_clamped | final_norm")
    logger.info("-" * 70)
    for i in [
        0,
        len(dmx_points) // 4,
        len(dmx_points) // 2,
        3 * len(dmx_points) // 4,
        len(dmx_points) - 1,
    ]:
        pt_handler = scaled_points[i]
        pt_dmx = dmx_points[i]
        dmx_unclamped = base_dmx + amplitude_dmx * (pt_handler.v - 0.5)
        dmx_clamped = max(pan_min_dmx, min(pan_max_dmx, dmx_unclamped))
        logger.info(
            f" {pt_dmx.t:5.2f} | {pt_handler.v:12.3f} | {dmx_unclamped:13.1f} | {dmx_clamped:11.1f} | {pt_dmx.v:10.3f}"
        )

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total points: {len(base_curve)}")
    logger.info(
        f"Clamps in Handler (adjusted_base_norm): {'YES' if adjusted_base_norm != adjusted_base_norm_clamped else 'NO'}"
    )
    logger.info(f"Clamps in Handler (curve points): {clamp_count_handler} points")
    logger.info(f"Clamps in DMX Conversion: {clamp_count_dmx} points")
    logger.info(
        f"Total clamp operations: {(1 if adjusted_base_norm != adjusted_base_norm_clamped else 0) + clamp_count_handler + clamp_count_dmx}"
    )

    # Expected behavior
    logger.info("\n" + "=" * 80)
    logger.info("EXPECTED BEHAVIOR")
    logger.info("=" * 80)
    logger.info("With correct math, the following should be true:")
    logger.info("  1. adjusted_base_norm should NOT be clamped (within [0, 1])")
    logger.info("  2. Handler curve points should NOT be clamped (within [0, 1])")
    logger.info("  3. DMX Conversion should be the ONLY place where clamping occurs")
    logger.info("  4. DMX clamps should be RARE (only at boundaries)")

    if clamp_count_handler > 0:
        logger.error("\n❌ ISSUE DETECTED: Handler is clamping curve points!")
        logger.error(
            "This indicates the amplitude scaling is incorrect or the base position is wrong."
        )
    elif clamp_count_dmx > 0:
        logger.warning("\n⚠️  DMX conversion is clamping points (expected at boundaries)")
    else:
        logger.info("\n✅ No clamping detected - math is correct!")


def analyze_center_offset_issue():
    """Analyze the center_offset formula to check for the * 2 issue."""
    logger.info("\n" + "=" * 80)
    logger.info("CENTER OFFSET FORMULA ANALYSIS")
    logger.info("=" * 80)

    base_norm = 0.5
    max_amplitude_norm = 0.249

    logger.info(f"Base: {base_norm:.3f}, Max Amplitude: {max_amplitude_norm:.3f}")
    logger.info("\nTesting center_offset values:")
    logger.info(
        "  offset | current_formula | correct_formula | current_adjusted | correct_adjusted"
    )
    logger.info("-" * 90)

    for center_offset in [0.0, 0.25, 0.5, 0.75, 1.0]:
        # Current formula (with * 2)
        current_offset = (center_offset - 0.5) * max_amplitude_norm * 2
        current_adjusted = base_norm + current_offset

        # Correct formula (without * 2)
        correct_offset = (center_offset - 0.5) * max_amplitude_norm
        correct_adjusted = base_norm + correct_offset

        logger.info(
            f"  {center_offset:4.2f}  | {current_offset:15.3f} | {correct_offset:15.3f} | {current_adjusted:16.3f} | {correct_adjusted:16.3f}"
        )

    logger.info("\nPROBLEM:")
    logger.info("  The current formula uses '* 2', which doubles the offset.")
    logger.info("  This can push adjusted_base beyond the safe range [pan_min_norm, pan_max_norm].")
    logger.info("  When amplitude is then added, it can exceed [0, 1], triggering clamps.")

    logger.info("\nRECOMMENDATION:")
    logger.info("  Remove the '* 2' factor from the center_offset formula.")


def main():
    """Run all diagnostic analyses."""
    analyze_movement_curve_clamping()
    analyze_center_offset_issue()


if __name__ == "__main__":
    main()
