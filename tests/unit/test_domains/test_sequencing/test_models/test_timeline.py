"""Tests for timeline models.

Tests the timeline models used in the rendering pipeline:
- TransitionSpec (imported from agents module)
- TemplateStepSegment
- GapSegment
- ExplodedTimeline
"""

from pydantic import ValidationError
import pytest

from blinkb0t.core.agents.moving_heads.models_agent_plan import TransitionSpec
from blinkb0t.core.domains.sequencing.models.timeline import (
    ExplodedTimeline,
    GapSegment,
    TemplateStepSegment,
)

# ============================================================================
# TransitionSpec Tests (imported model)
# ============================================================================


def test_transition_spec_creation():
    """Test TransitionSpec can be created with required fields."""
    spec = TransitionSpec(mode="snap", duration_ms=0)
    assert spec.mode == "snap"
    assert spec.duration_ms == 0


def test_transition_spec_crossfade():
    """Test TransitionSpec with crossfade mode."""
    spec = TransitionSpec(mode="crossfade", duration_ms=500)
    assert spec.mode == "crossfade"
    assert spec.duration_ms == 500


def test_transition_spec_fade_through_black():
    """Test TransitionSpec with fade_through_black mode."""
    spec = TransitionSpec(mode="fade_through_black", duration_ms=1000)
    assert spec.mode == "fade_through_black"
    assert spec.duration_ms == 1000


def test_transition_spec_negative_duration():
    """Test TransitionSpec rejects negative duration."""
    with pytest.raises(ValidationError):
        TransitionSpec(mode="snap", duration_ms=-100)


# ============================================================================
# TemplateStepSegment Tests
# ============================================================================


def test_template_step_segment_minimal():
    """Test TemplateStepSegment creation with minimal required fields."""
    segment = TemplateStepSegment(
        step_id="step_1",
        section_id="verse_1",
        start_ms=0.0,
        end_ms=2000.0,
        template_id="sweep_lr",
        movement_id="sweep",
        movement_params={},
        dimmer_id="full",
        dimmer_params={},
        base_pose="AUDIENCE_CENTER",
        target="ALL",
    )

    assert segment.step_id == "step_1"
    assert segment.section_id == "verse_1"
    assert segment.start_ms == 0.0
    assert segment.end_ms == 2000.0
    assert segment.template_id == "sweep_lr"
    assert segment.movement_id == "sweep"
    assert segment.movement_params == {}
    assert segment.dimmer_id == "full"
    assert segment.dimmer_params == {}
    assert segment.base_pose == "AUDIENCE_CENTER"
    assert segment.target == "ALL"
    assert segment.geometry_id is None
    assert segment.geometry_params is None
    assert segment.entry_transition is None
    assert segment.exit_transition is None


def test_template_step_segment_with_geometry():
    """Test TemplateStepSegment with geometry specification."""
    segment = TemplateStepSegment(
        step_id="step_1",
        section_id="verse_1",
        start_ms=0.0,
        end_ms=2000.0,
        template_id="sweep_lr",
        movement_id="sweep",
        movement_params={"amplitude": 0.5},
        dimmer_id="full",
        dimmer_params={},
        base_pose="AUDIENCE_CENTER",
        target="ALL",
        geometry_id="wave_lr",
        geometry_params={"phase_shift": 0.25},
    )

    assert segment.geometry_id == "wave_lr"
    assert segment.geometry_params == {"phase_shift": 0.25}


def test_template_step_segment_with_transitions():
    """Test TemplateStepSegment with entry and exit transitions."""
    entry = TransitionSpec(mode="crossfade", duration_ms=500)
    exit_trans = TransitionSpec(mode="snap", duration_ms=0)

    segment = TemplateStepSegment(
        step_id="step_1",
        section_id="verse_1",
        start_ms=0.0,
        end_ms=2000.0,
        template_id="sweep_lr",
        movement_id="sweep",
        movement_params={},
        dimmer_id="full",
        dimmer_params={},
        base_pose="AUDIENCE_CENTER",
        target="ALL",
        entry_transition=entry,
        exit_transition=exit_trans,
    )

    assert segment.entry_transition == entry
    assert segment.exit_transition == exit_trans


def test_template_step_segment_target_options():
    """Test TemplateStepSegment with different target options."""
    # ALL
    seg_all = TemplateStepSegment(
        step_id="step_1",
        section_id="verse_1",
        start_ms=0.0,
        end_ms=2000.0,
        template_id="sweep_lr",
        movement_id="sweep",
        movement_params={},
        dimmer_id="full",
        dimmer_params={},
        base_pose="AUDIENCE_CENTER",
        target="ALL",
    )
    assert seg_all.target == "ALL"

    # LEFT
    seg_left = TemplateStepSegment(
        step_id="step_2",
        section_id="verse_1",
        start_ms=0.0,
        end_ms=2000.0,
        template_id="sweep_lr",
        movement_id="sweep",
        movement_params={},
        dimmer_id="full",
        dimmer_params={},
        base_pose="AUDIENCE_CENTER",
        target="LEFT",
    )
    assert seg_left.target == "LEFT"

    # Specific fixture
    seg_specific = TemplateStepSegment(
        step_id="step_3",
        section_id="verse_1",
        start_ms=0.0,
        end_ms=2000.0,
        template_id="sweep_lr",
        movement_id="sweep",
        movement_params={},
        dimmer_id="full",
        dimmer_params={},
        base_pose="AUDIENCE_CENTER",
        target="MH_1",
    )
    assert seg_specific.target == "MH_1"


def test_template_step_segment_invalid_timing():
    """Test TemplateStepSegment rejects invalid timing."""
    # Start > End
    with pytest.raises(ValidationError):
        TemplateStepSegment(
            step_id="step_1",
            section_id="verse_1",
            start_ms=2000.0,
            end_ms=1000.0,  # Invalid: ends before it starts
            template_id="sweep_lr",
            movement_id="sweep",
            movement_params={},
            dimmer_id="full",
            dimmer_params={},
            base_pose="AUDIENCE_CENTER",
            target="ALL",
        )


def test_template_step_segment_serialization():
    """Test TemplateStepSegment can be serialized and deserialized."""
    segment = TemplateStepSegment(
        step_id="step_1",
        section_id="verse_1",
        start_ms=0.0,
        end_ms=2000.0,
        template_id="sweep_lr",
        movement_id="sweep",
        movement_params={"amplitude": 0.5},
        dimmer_id="full",
        dimmer_params={"base_pct": 80},
        base_pose="AUDIENCE_CENTER",
        target="ALL",
        geometry_id="wave_lr",
        geometry_params={"phase_shift": 0.25},
    )

    # Serialize
    data = segment.model_dump()
    assert isinstance(data, dict)
    assert data["step_id"] == "step_1"

    # Deserialize
    segment_restored = TemplateStepSegment(**data)
    assert segment_restored == segment


# ============================================================================
# GapSegment Tests
# ============================================================================


def test_gap_segment_minimal():
    """Test GapSegment creation with minimal fields."""
    gap = GapSegment(
        start_ms=1000.0,
        end_ms=2000.0,
        gap_type="inter_section",
    )

    assert gap.start_ms == 1000.0
    assert gap.end_ms == 2000.0
    assert gap.gap_type == "inter_section"
    assert gap.section_id is None


def test_gap_segment_with_section():
    """Test GapSegment with associated section."""
    gap = GapSegment(
        start_ms=1000.0,
        end_ms=2000.0,
        section_id="verse_1",
        gap_type="intra_section",
    )

    assert gap.section_id == "verse_1"
    assert gap.gap_type == "intra_section"


def test_gap_segment_types():
    """Test GapSegment with different gap types."""
    # inter_section
    gap_inter = GapSegment(start_ms=0.0, end_ms=100.0, gap_type="inter_section")
    assert gap_inter.gap_type == "inter_section"

    # intra_section
    gap_intra = GapSegment(start_ms=0.0, end_ms=100.0, gap_type="intra_section")
    assert gap_intra.gap_type == "intra_section"

    # end_of_song
    gap_end = GapSegment(start_ms=0.0, end_ms=100.0, gap_type="end_of_song")
    assert gap_end.gap_type == "end_of_song"


def test_gap_segment_invalid_timing():
    """Test GapSegment rejects invalid timing."""
    with pytest.raises(ValidationError):
        GapSegment(
            start_ms=2000.0,
            end_ms=1000.0,  # Invalid: ends before it starts
            gap_type="inter_section",
        )


def test_gap_segment_serialization():
    """Test GapSegment can be serialized and deserialized."""
    gap = GapSegment(
        start_ms=1000.0,
        end_ms=2000.0,
        section_id="verse_1",
        gap_type="intra_section",
    )

    # Serialize
    data = gap.model_dump()
    assert isinstance(data, dict)
    assert data["start_ms"] == 1000.0

    # Deserialize
    gap_restored = GapSegment(**data)
    assert gap_restored == gap


# ============================================================================
# ExplodedTimeline Tests
# ============================================================================


def test_exploded_timeline_empty():
    """Test ExplodedTimeline with no segments."""
    timeline = ExplodedTimeline(segments=[], total_duration_ms=0.0)

    assert timeline.segments == []
    assert timeline.total_duration_ms == 0.0


def test_exploded_timeline_with_segments():
    """Test ExplodedTimeline with template step segments."""
    seg1 = TemplateStepSegment(
        step_id="step_1",
        section_id="verse_1",
        start_ms=0.0,
        end_ms=2000.0,
        template_id="sweep_lr",
        movement_id="sweep",
        movement_params={},
        dimmer_id="full",
        dimmer_params={},
        base_pose="AUDIENCE_CENTER",
        target="ALL",
    )
    seg2 = TemplateStepSegment(
        step_id="step_2",
        section_id="verse_1",
        start_ms=2000.0,
        end_ms=4000.0,
        template_id="circle",
        movement_id="circle",
        movement_params={},
        dimmer_id="pulse",
        dimmer_params={},
        base_pose="AUDIENCE_CENTER",
        target="ALL",
    )

    timeline = ExplodedTimeline(segments=[seg1, seg2], total_duration_ms=4000.0)

    assert len(timeline.segments) == 2
    assert timeline.segments[0] == seg1
    assert timeline.segments[1] == seg2
    assert timeline.total_duration_ms == 4000.0


def test_exploded_timeline_with_gaps():
    """Test ExplodedTimeline with gap segments."""
    gap = GapSegment(start_ms=0.0, end_ms=1000.0, gap_type="inter_section")

    timeline = ExplodedTimeline(segments=[gap], total_duration_ms=1000.0)

    assert len(timeline.segments) == 1
    assert isinstance(timeline.segments[0], GapSegment)
    assert timeline.total_duration_ms == 1000.0


def test_exploded_timeline_mixed_segments():
    """Test ExplodedTimeline with both template and gap segments."""
    seg1 = TemplateStepSegment(
        step_id="step_1",
        section_id="verse_1",
        start_ms=0.0,
        end_ms=2000.0,
        template_id="sweep_lr",
        movement_id="sweep",
        movement_params={},
        dimmer_id="full",
        dimmer_params={},
        base_pose="AUDIENCE_CENTER",
        target="ALL",
    )
    gap = GapSegment(start_ms=2000.0, end_ms=3000.0, gap_type="inter_section")
    seg2 = TemplateStepSegment(
        step_id="step_2",
        section_id="chorus_1",
        start_ms=3000.0,
        end_ms=5000.0,
        template_id="circle",
        movement_id="circle",
        movement_params={},
        dimmer_id="pulse",
        dimmer_params={},
        base_pose="AUDIENCE_CENTER",
        target="ALL",
    )

    timeline = ExplodedTimeline(segments=[seg1, gap, seg2], total_duration_ms=5000.0)

    assert len(timeline.segments) == 3
    assert isinstance(timeline.segments[0], TemplateStepSegment)
    assert isinstance(timeline.segments[1], GapSegment)
    assert isinstance(timeline.segments[2], TemplateStepSegment)


def test_exploded_timeline_ordering():
    """Test ExplodedTimeline maintains segment order."""
    # Create segments in reverse chronological order
    seg2 = TemplateStepSegment(
        step_id="step_2",
        section_id="chorus_1",
        start_ms=2000.0,
        end_ms=4000.0,
        template_id="circle",
        movement_id="circle",
        movement_params={},
        dimmer_id="pulse",
        dimmer_params={},
        base_pose="AUDIENCE_CENTER",
        target="ALL",
    )
    seg1 = TemplateStepSegment(
        step_id="step_1",
        section_id="verse_1",
        start_ms=0.0,
        end_ms=2000.0,
        template_id="sweep_lr",
        movement_id="sweep",
        movement_params={},
        dimmer_id="full",
        dimmer_params={},
        base_pose="AUDIENCE_CENTER",
        target="ALL",
    )

    # Timeline should maintain order as provided
    timeline = ExplodedTimeline(segments=[seg2, seg1], total_duration_ms=4000.0)

    assert timeline.segments[0] == seg2
    assert timeline.segments[1] == seg1


def test_exploded_timeline_serialization():
    """Test ExplodedTimeline can be serialized and deserialized."""
    seg = TemplateStepSegment(
        step_id="step_1",
        section_id="verse_1",
        start_ms=0.0,
        end_ms=2000.0,
        template_id="sweep_lr",
        movement_id="sweep",
        movement_params={},
        dimmer_id="full",
        dimmer_params={},
        base_pose="AUDIENCE_CENTER",
        target="ALL",
    )
    gap = GapSegment(start_ms=2000.0, end_ms=3000.0, gap_type="inter_section")

    timeline = ExplodedTimeline(segments=[seg, gap], total_duration_ms=3000.0)

    # Serialize
    data = timeline.model_dump()
    assert isinstance(data, dict)
    assert len(data["segments"]) == 2

    # Deserialize
    timeline_restored = ExplodedTimeline(**data)
    assert len(timeline_restored.segments) == 2
    assert timeline_restored.total_duration_ms == 3000.0
