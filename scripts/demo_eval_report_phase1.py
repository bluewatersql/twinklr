#!/usr/bin/env python3
"""Demo script for Phase 1 evaluation report system.

Tests the full pipeline with real checkpoint data from need_a_favor.
"""

import logging
from pathlib import Path
import sys

from blinkb0t.core.reporting.evaluation import generate_evaluation_report
from blinkb0t.core.reporting.evaluation.config import EvalConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    """Run evaluation report generation demo."""
    logger.info("=== Evaluation Report Phase 1 Demo ===\n")

    # Paths
    checkpoint_path = Path("artifacts/need_a_favor/checkpoints/plans/need_a_favor_final.json")
    audio_path = Path("data/music/Need A Favor.mp3")  # User must provide
    fixture_config_path = Path("fixture_config.json")
    xsq_path = Path("artifacts/need_a_favor/need_a_favor_blinkb0t_mh.xsq")  # Use actual XSQ
    output_dir = Path("artifacts/need_a_favor/eval_report")

    # Verify inputs exist
    if not checkpoint_path.exists():
        logger.error(f"Checkpoint not found: {checkpoint_path}")
        return 1

    if not audio_path.exists():
        logger.error(f"Audio file not found: {audio_path}")
        logger.info("Please place need_a_favor.mp3 in artifacts/need_a_favor/")
        return 1

    if not fixture_config_path.exists():
        logger.error(f"Fixture config not found: {fixture_config_path}")
        return 1

    if not xsq_path.exists():
        logger.error(f"XSQ template not found: {xsq_path}")
        return 1

    logger.info(f"Checkpoint: {checkpoint_path}")
    logger.info(f"Audio: {audio_path}")
    logger.info(f"Fixtures: {fixture_config_path}")
    logger.info(f"XSQ: {xsq_path}")
    logger.info(f"Output: {output_dir}\n")

    # Configure evaluation
    config = EvalConfig(
        samples_per_bar=96,  # High resolution
        clamp_warning_threshold=0.10,  # 10% warning
        clamp_error_threshold=0.25,  # 25% error
        plot_all_roles=False,  # Auto-select representative roles
        include_dmx_plots=False,  # Normalized only for now
        output_format=["json", "md"],
    )

    logger.info("Configuration:")
    logger.info(f"  Samples per bar: {config.samples_per_bar}")
    logger.info(f"  Clamp warning: {config.clamp_warning_threshold * 100}%")
    logger.info(f"  Clamp error: {config.clamp_error_threshold * 100}%")
    logger.info(f"  Output formats: {config.output_format}\n")

    # Generate report
    logger.info("Generating evaluation report...")

    try:
        report = generate_evaluation_report(
            checkpoint_path=checkpoint_path,
            audio_path=audio_path,
            fixture_config_path=fixture_config_path,
            xsq_path=xsq_path,
            output_dir=output_dir,
            config=config,
        )

        logger.info("\n=== Report Generated Successfully ===\n")

        # Print summary
        logger.info(f"Run ID: {report.run.run_id}")
        logger.info(f"Engine: {report.run.engine_version}")
        logger.info(f"Git SHA: {report.run.git_sha or 'N/A'}")
        logger.info(f"Sections analyzed: {len(report.sections)}")

        # Section summary
        for section in report.sections:
            logger.info(f"\n[{section.label}]")
            logger.info(f"  Bars: {section.bar_range[0]:.1f} - {section.bar_range[1]:.1f}")
            logger.info(f"  Curve analyses: {len(section.curves)}")

        # Overall summary
        logger.info("\n=== Summary ===")
        logger.info(f"Total sections: {report.summary.sections}")
        logger.info(f"Error flags: {report.summary.total_errors}")
        logger.info(f"Warning flags: {report.summary.total_warnings}")
        logger.info(f"Templates used: {len(report.summary.templates_used)}")

        # Output files
        logger.info("\n=== Output Files ===")
        json_path = output_dir / "report.json"
        md_path = output_dir / "report.md"
        plots_dir = output_dir / "plots"

        if json_path.exists():
            logger.info(f"✓ JSON report: {json_path}")
        if md_path.exists():
            logger.info(f"✓ Markdown report: {md_path}")
        if plots_dir.exists():
            plot_count = len(list(plots_dir.glob("*.png")))
            logger.info(f"✓ Plots: {plots_dir} ({plot_count} images)")

        logger.info("\n✅ Phase 1 Demo Complete!")
        return 0

    except Exception as e:
        logger.exception(f"Report generation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
