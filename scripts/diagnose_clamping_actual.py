"""Extended diagnostic to analyze actual rendered curves from evaluation report."""

import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


def analyze_clamped_curves():
    """Analyze curves with clamping from the evaluation report."""
    logger.info("=" * 80)
    logger.info("ACTUAL CURVE CLAMPING ANALYSIS (from eval report)")
    logger.info("=" * 80)

    report_path = Path("artifacts/need_a_favor/eval_report/report.json")
    if not report_path.exists():
        logger.error(f"Report not found: {report_path}")
        return

    with report_path.open() as f:
        report = json.load(f)

    # Find all curves with clamping
    clamped_curves = []
    for section in report["sections"]:
        section_name = section.get("section_name", "Unknown")
        for curve in section.get("curves", []):
            clamp_pct = curve["stats"]["clamp_pct"]
            if clamp_pct > 0:
                clamped_curves.append(
                    {
                        "section": section_name,
                        "role": curve["role"],
                        "channel": curve["channel"],
                        "curve_type": curve.get("curve_type", "Unknown"),
                        "handler": curve.get("handler", "Unknown"),
                        "base": curve.get("base_position"),
                        "clamp_pct": clamp_pct,
                        "min": curve["stats"]["min"],
                        "max": curve["stats"]["max"],
                        "range": curve["stats"]["range"],
                        "mean": curve["stats"]["mean"],
                    }
                )

    logger.info(f"Found {len(clamped_curves)} curves with clamping\n")

    # Group by channel type
    movement_curves = [c for c in clamped_curves if c["channel"] in ["pan", "tilt"]]
    dimmer_curves = [c for c in clamped_curves if c["channel"] == "dimmer"]

    logger.info("=" * 80)
    logger.info("MOVEMENT CURVES (Pan/Tilt) WITH CLAMPING")
    logger.info("=" * 80)
    logger.info(f"Total: {len(movement_curves)}\n")

    for i, curve in enumerate(movement_curves, 1):
        logger.info(f"{i}. {curve['role']} - {curve['channel'].upper()}")
        logger.info(f"   Curve Type: {curve['curve_type']}")
        logger.info(f"   Handler: {curve['handler']}")
        logger.info(f"   Base Position: {curve['base']}")
        logger.info(
            f"   Range: [{curve['min']:.3f}, {curve['max']:.3f}] (span: {curve['range']:.3f})"
        )
        logger.info(f"   Mean: {curve['mean']:.3f}")
        logger.info(f"   Clamp %: {curve['clamp_pct']:.2f}%")

        # Analysis
        if curve["min"] == 0.0:
            logger.warning("   ⚠️  Hitting LOWER boundary (0.0)")
        if curve["max"] == 1.0:
            logger.warning("   ⚠️  Hitting UPPER boundary (1.0)")

        # Check if base position could be causing issues
        if curve["base"] is not None:
            base = float(curve["base"])
            dist_to_min = base - curve["min"]
            dist_to_max = curve["max"] - base
            logger.info(f"   Distance from base to min: {dist_to_min:.3f}")
            logger.info(f"   Distance from base to max: {dist_to_max:.3f}")

            if dist_to_min < 0:
                logger.error("   ❌ ISSUE: Curve goes BELOW base position!")
            if dist_to_max < 0:
                logger.error("   ❌ ISSUE: Curve goes ABOVE base position!")

        logger.info("")

    logger.info("=" * 80)
    logger.info("DIMMER CURVES WITH CLAMPING")
    logger.info("=" * 80)
    logger.info(f"Total: {len(dimmer_curves)}\n")

    for i, curve in enumerate(dimmer_curves, 1):
        logger.info(f"{i}. {curve['role']} - {curve['channel'].upper()}")
        logger.info(f"   Curve Type: {curve['curve_type']}")
        logger.info(
            f"   Range: [{curve['min']:.3f}, {curve['max']:.3f}] (span: {curve['range']:.3f})"
        )
        logger.info(f"   Clamp %: {curve['clamp_pct']:.2f}%")

        if curve["curve_type"] == "CurveLibrary.HOLD" and curve["clamp_pct"] == 100.0:
            logger.info("   ℹ️  HOLD curve at full brightness - expected behavior")

        logger.info("")

    # Summary and recommendations
    logger.info("=" * 80)
    logger.info("ANALYSIS SUMMARY")
    logger.info("=" * 80)

    movement_clamp_total = len(movement_curves)
    dimmer_clamp_total = len(dimmer_curves)
    dimmer_hold_100 = len(
        [
            c
            for c in dimmer_curves
            if c["curve_type"] == "CurveLibrary.HOLD" and c["clamp_pct"] == 100.0
        ]
    )

    logger.info(f"Movement curves with clamping: {movement_clamp_total}")
    logger.info(f"Dimmer curves with clamping: {dimmer_clamp_total}")
    logger.info(f"  - HOLD curves at 100%: {dimmer_hold_100} (expected)")
    logger.info(f"  - Other: {dimmer_clamp_total - dimmer_hold_100}")

    logger.info("\n" + "=" * 80)
    logger.info("ROOT CAUSE ANALYSIS")
    logger.info("=" * 80)

    if movement_clamp_total > 0:
        logger.warning("Movement curves should NOT be clamped if math is correct!")
        logger.warning("Possible causes:")
        logger.warning("  1. Center offset formula is incorrect (has '* 2' factor)")
        logger.warning("  2. Amplitude is not respecting max_amplitude_norm")
        logger.warning("  3. Base position from geometry is outside safe bounds")
        logger.warning("  4. Calibration min/max constraints are too tight")

        # Check specific cases
        for curve in movement_curves:
            if curve["min"] == 0.0 and curve["base"] is not None:
                base = float(curve["base"])
                if base < 0.15:  # Very close to lower bound
                    logger.warning(
                        f"\n  {curve['role']} {curve['channel']}: Base position ({base:.3f}) is very close to lower bound"
                    )
                    logger.warning("    This leaves little room for negative amplitude excursions")
                    logger.warning(f"    Expected max amplitude: ~{base:.3f}")
                    logger.warning(f"    Actual max negative excursion: {base - curve['min']:.3f}")

    if dimmer_clamp_total - dimmer_hold_100 > 0:
        logger.warning(
            f"\n{dimmer_clamp_total - dimmer_hold_100} dimmer curves with unexpected clamping"
        )
        logger.warning("Check dimmer intensity scaling logic")

    logger.info("\n" + "=" * 80)
    logger.info("RECOMMENDATIONS")
    logger.info("=" * 80)
    logger.info("1. Fix center_offset formula: Remove '* 2' factor")
    logger.info("2. Ensure max_amplitude_norm calculation accounts for center offset")
    logger.info("3. Add assertions instead of silent clamps")
    logger.info("4. Review geometry handlers - ensure base positions are centered in safe zone")


def main():
    """Run analysis."""
    analyze_clamped_curves()


if __name__ == "__main__":
    main()
