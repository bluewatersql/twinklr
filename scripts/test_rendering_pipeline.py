#!/usr/bin/env python3
"""Test script for RenderingPipeline."""

import logging
import sys

from blinkb0t.core.agents.moving_heads.models_llm_plan import (
    LLMChoreographyPlan,
    SectionSelection,
)
from blinkb0t.core.config.fixtures import FixtureGroup, FixtureInstance
from blinkb0t.core.config.models import JobConfig
from blinkb0t.core.sequencer.moving_heads.pipeline import RenderingPipeline
from blinkb0t.core.sequencer.timing.beat_grid import BeatGrid

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def create_test_fixture_group() -> FixtureGroup:
    """Create a simple test fixture group with 4 fixtures."""
    from blinkb0t.core.config.fixtures import (
        ChannelInversions,
        ChannelWithConfig,
        DMXMapping,
        FixtureConfig,
        FixturePosition,
    )

    fixtures = []
    for i in range(4):
        fixture = FixtureInstance(
            fixture_id=f"fixture_{i}",
            config=FixtureConfig(
                position=FixturePosition(position_index=i, x=float(i), y=0.0, z=0.0),
                dmx_mapping=DMXMapping(
                    universe=1,
                    start_address=1 + (i * 16),
                    pan_channel=ChannelWithConfig(channel=1),
                    tilt_channel=ChannelWithConfig(channel=2),
                    dimmer_channel=ChannelWithConfig(channel=3),
                ),
                inversions=ChannelInversions(pan=False, tilt=False, dimmer=False),
            ),
        )
        fixtures.append(fixture)

    return FixtureGroup(
        group_id="test_group",
        fixtures=fixtures,
    )


def create_test_beat_grid() -> BeatGrid:
    """Create a simple test beat grid at 120 BPM."""
    # 120 BPM = 2 beats per second = 500ms per beat
    # 4 beats per bar = 2000ms per bar

    # Create beat boundaries for 16 bars (32 seconds)
    beat_boundaries = [i * 500.0 for i in range(64)]  # 64 beats
    bar_boundaries = [i * 2000.0 for i in range(17)]  # 17 bar boundaries (16 bars)

    return BeatGrid(
        bar_boundaries=bar_boundaries,
        beat_boundaries=beat_boundaries,
        quarter_boundaries=beat_boundaries,
        eighth_boundaries=[i * 250.0 for i in range(128)],
        sixteenth_boundaries=[i * 125.0 for i in range(256)],
        tempo_bpm=120.0,
        beats_per_bar=4,
        duration_ms=32000,
    )


def create_test_plan() -> LLMChoreographyPlan:
    """Create a simple test choreography plan."""
    return LLMChoreographyPlan(
        sections=[
            SectionSelection(
                section_name="intro",
                start_bar=1,
                end_bar=4,
                section_role="intro",
                energy_level=40,
                template_id="bounce_fan_pulse",
                preset_id="ENERGETIC",
                modifiers={},
                reasoning="Simple bounce pattern for intro",
            ),
            SectionSelection(
                section_name="verse",
                start_bar=5,
                end_bar=8,
                section_role="verse",
                energy_level=60,
                template_id="bounce_fan_pulse",
                preset_id=None,
                modifiers={},
                reasoning="Continue with base bounce pattern",
            ),
        ],
        overall_strategy="Build energy from intro to verse",
        template_variety_notes="Using same template with different presets",
    )


def main():
    """Run the test."""
    logger.info("Creating test data...")

    # Create test components
    fixture_group = create_test_fixture_group()
    beat_grid = create_test_beat_grid()
    plan = create_test_plan()
    job_config = JobConfig()  # Default config

    logger.info(f"Fixture group: {len(fixture_group.fixtures)} fixtures")
    logger.info(f"Beat grid: {len(beat_grid.bar_boundaries) - 1} bars, {beat_grid.tempo_bpm} BPM")
    logger.info(f"Plan: {len(plan.sections)} sections")

    # Create pipeline
    logger.info("Initializing rendering pipeline...")
    pipeline = RenderingPipeline(
        llm_plan=plan,
        beat_grid=beat_grid,
        fixture_group=fixture_group,
        job_config=job_config,
    )

    # Render
    logger.info("Starting render...")
    try:
        segments = pipeline.render()
        logger.info(f"✅ Render complete: {len(segments)} segments generated")

        # Print summary
        logger.info("\n=== Render Summary ===")
        logger.info(f"Total segments: {len(segments)}")

        # Group by fixture
        by_fixture = {}
        for seg in segments:
            if seg.fixture_id not in by_fixture:
                by_fixture[seg.fixture_id] = []
            by_fixture[seg.fixture_id].append(seg)

        for fixture_id, segs in by_fixture.items():
            logger.info(f"  {fixture_id}: {len(segs)} segments")

        # Print first segment details
        if segments:
            seg = segments[0]
            logger.info("\nFirst segment details:")
            logger.info(f"  Fixture: {seg.fixture_id}")
            logger.info(f"  Time: {seg.t0_ms}ms - {seg.t1_ms}ms")
            logger.info(f"  Channels: {list(seg.channels.keys())}")

    except Exception as e:
        logger.error(f"❌ Render failed: {e}", exc_info=True)
        return 1

    logger.info("\n✅ Test complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
