"""Integration tests for transitions in the rendering pipeline."""

import pytest

from blinkb0t.core.config.fixtures import FixtureConfig, FixtureGroup, FixtureInstance
from blinkb0t.core.config.models import JobConfig, TransitionConfig
from blinkb0t.core.sequencer.models.enum import ChannelName, TransitionMode
from blinkb0t.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from blinkb0t.core.sequencer.moving_heads.export.xsq_adapter import XsqAdapter
from blinkb0t.core.sequencer.timing.beat_grid import BeatGrid


@pytest.fixture
def beat_grid():
    """Create a test beat grid."""
    return BeatGrid.from_tempo(tempo=120.0, total_bars=32)


@pytest.fixture
def fixture_group():
    """Create a test fixture group."""
    from blinkb0t.core.config.fixtures.dmx import DmxMapping

    dmx_map = DmxMapping(
        pan_channel=1,
        tilt_channel=2,
        dimmer_channel=3,
    )

    config = FixtureConfig(
        fixture_id="test_mh",
        name="Test Moving Head",
        type="MOVING_HEAD",
        dmx_mapping=dmx_map,
    )

    fixtures = [
        FixtureInstance(
            fixture_id="mh1",
            xlights_model_name="Dmx MH1",
            config=config,
            start_channel=1,
        ),
        FixtureInstance(
            fixture_id="mh2",
            xlights_model_name="Dmx MH2",
            config=config,
            start_channel=10,
        ),
    ]

    return FixtureGroup(
        group_id="test_group",
        fixtures=fixtures,
        xlights_semantic_groups={},
    )


@pytest.fixture
def job_config():
    """Create test job config with transitions enabled."""
    return JobConfig(
        transitions=TransitionConfig(
            enabled=True,
            default_duration_bars=0.5,
            default_mode=TransitionMode.CROSSFADE,
        )
    )


class TestMultiLayerExport:
    """Test that transitions are exported on separate layers."""

    def test_transition_segments_on_separate_layer(self, fixture_group):
        """Test that transition segments are assigned to layer 1."""
        # Create regular segment on layer 0
        regular_segment = FixtureSegment(
            section_id="verse",
            segment_id="seg_1",
            step_id="step_1",
            template_id="template_verse",
            fixture_id="mh1",
            t0_ms=0,
            t1_ms=10000,
            channels={ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=255)},
        )

        # Create transition segment (overlaps with regular segment)
        transition_segment = FixtureSegment(
            section_id="transition_verse_to_chorus",
            segment_id="trans_1",
            step_id="transition",
            template_id="transition",
            fixture_id="mh1",
            t0_ms=9000,  # Overlaps with regular segment
            t1_ms=11000,
            channels={ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=200)},
            metadata={"is_transition": "true"},  # Mark as transition
        )

        adapter = XsqAdapter()
        placements = adapter.convert([regular_segment, transition_segment], fixture_group, xsq=None)

        # Should have 2 placements
        assert len(placements) == 2

        # Find regular and transition placements
        regular_placement = next(p for p in placements if p.start_ms == 0)
        transition_placement = next(p for p in placements if p.start_ms == 9000)

        # Regular should be on layer 0
        assert regular_placement.layer_index == 0

        # Transition should be on layer 1
        assert transition_placement.layer_index == 1

    def test_multiple_transitions_same_layer(self, fixture_group):
        """Test that multiple transitions are all on layer 1."""
        segments = [
            # Regular segments on layer 0
            FixtureSegment(
                section_id="verse",
                segment_id="seg_1",
                step_id="step_1",
                template_id="template_verse",
                fixture_id="mh1",
                t0_ms=0,
                t1_ms=10000,
                channels={
                    ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=255)
                },
            ),
            FixtureSegment(
                section_id="chorus",
                segment_id="seg_2",
                step_id="step_1",
                template_id="template_chorus",
                fixture_id="mh1",
                t0_ms=11000,
                t1_ms=20000,
                channels={
                    ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=200)
                },
            ),
            # Transition segments on layer 1
            FixtureSegment(
                section_id="transition_verse_to_chorus",
                segment_id="trans_1",
                step_id="transition",
                template_id="transition",
                fixture_id="mh1",
                t0_ms=9000,
                t1_ms=11000,
                channels={
                    ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=180)
                },
                metadata={"is_transition": "true"},
            ),
            FixtureSegment(
                section_id="transition_chorus_to_bridge",
                segment_id="trans_2",
                step_id="transition",
                template_id="transition",
                fixture_id="mh1",
                t0_ms=19000,
                t1_ms=21000,
                channels={
                    ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=150)
                },
                metadata={"is_transition": "true"},
            ),
        ]

        adapter = XsqAdapter()
        placements = adapter.convert(segments, fixture_group, xsq=None)

        # Should have 4 placements
        assert len(placements) == 4

        # All regular segments should be on layer 0
        regular_placements = [p for p in placements if "transition" not in p.effect_label]
        assert all(p.layer_index == 0 for p in regular_placements)

        # All transition segments should be on layer 1
        transition_placements = [p for p in placements if "transition" in p.effect_label]
        assert all(p.layer_index == 1 for p in transition_placements)

    def test_no_transitions_single_layer(self, fixture_group):
        """Test that without transitions, all effects are on layer 0."""
        segments = [
            FixtureSegment(
                section_id="verse",
                segment_id="seg_1",
                step_id="step_1",
                template_id="template_verse",
                fixture_id="mh1",
                t0_ms=0,
                t1_ms=10000,
                channels={
                    ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=255)
                },
            ),
            FixtureSegment(
                section_id="chorus",
                segment_id="seg_2",
                step_id="step_1",
                template_id="template_chorus",
                fixture_id="mh1",
                t0_ms=10000,
                t1_ms=20000,
                channels={
                    ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=200)
                },
            ),
        ]

        adapter = XsqAdapter()
        placements = adapter.convert(segments, fixture_group, xsq=None)

        # All should be on layer 0
        assert all(p.layer_index == 0 for p in placements)

    def test_multi_fixture_transitions_on_layer_1(self, fixture_group):
        """Test that transitions for multiple fixtures are on layer 1."""
        segments = [
            # Regular segments
            FixtureSegment(
                section_id="verse",
                segment_id="seg_1",
                step_id="step_1",
                template_id="template_verse",
                fixture_id="mh1",
                t0_ms=0,
                t1_ms=10000,
                channels={
                    ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=255)
                },
            ),
            FixtureSegment(
                section_id="verse",
                segment_id="seg_1",
                step_id="step_1",
                template_id="template_verse",
                fixture_id="mh2",
                t0_ms=0,
                t1_ms=10000,
                channels={
                    ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=255)
                },
            ),
            # Transitions
            FixtureSegment(
                section_id="transition_verse_to_chorus",
                segment_id="trans_1",
                step_id="transition",
                template_id="transition",
                fixture_id="mh1",
                t0_ms=9000,
                t1_ms=11000,
                channels={
                    ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=180)
                },
                metadata={"is_transition": "true"},
            ),
            FixtureSegment(
                section_id="transition_verse_to_chorus",
                segment_id="trans_1",
                step_id="transition",
                template_id="transition",
                fixture_id="mh2",
                t0_ms=9000,
                t1_ms=11000,
                channels={
                    ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=180)
                },
                metadata={"is_transition": "true"},
            ),
        ]

        adapter = XsqAdapter()
        placements = adapter.convert(segments, fixture_group, xsq=None)

        # Should have 4 placements
        assert len(placements) == 4

        # Regular segments (mh1 and mh2) on layer 0
        regular_count = sum(1 for p in placements if p.layer_index == 0)
        assert regular_count == 2

        # Transition segments (mh1 and mh2) on layer 1
        transition_count = sum(1 for p in placements if p.layer_index == 1)
        assert transition_count == 2
