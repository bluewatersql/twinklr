"""Unit tests for transition models."""

from twinklr.core.curves.library import CurveLibrary
from twinklr.core.sequencer.models.enum import ChannelName, TransitionMode
from twinklr.core.sequencer.models.transition import (
    Boundary,
    BoundaryType,
    TransitionHint,
    TransitionPlan,
    TransitionRegistry,
    TransitionStrategy,
)


class TestTransitionStrategy:
    """Test TransitionStrategy enum."""

    def test_all_strategies_defined(self):
        """Test all expected strategies are defined."""
        assert TransitionStrategy.SNAP == "snap"
        assert TransitionStrategy.SMOOTH_INTERPOLATION == "smooth"
        assert TransitionStrategy.CROSSFADE == "crossfade"
        assert TransitionStrategy.FADE_VIA_BLACK == "fade_via_black"
        assert TransitionStrategy.SEQUENCE == "sequence"


class TestTransitionHint:
    """Test TransitionHint model."""

    def test_crossfade_transition(self):
        """Test creating a crossfade transition."""
        hint = TransitionHint(
            mode=TransitionMode.CROSSFADE, duration_bars=1.0, curve=CurveLibrary.LINEAR
        )

        assert hint.mode == TransitionMode.CROSSFADE
        assert hint.duration_bars == 1.0
        assert hint.curve == CurveLibrary.LINEAR
        assert hint.is_snap is False

    def test_with_channel_overrides(self):
        """Test transition hint with per-channel overrides."""
        hint = TransitionHint(
            mode=TransitionMode.CROSSFADE,
            duration_bars=1.5,
            per_channel_overrides={
                "dimmer": TransitionStrategy.FADE_VIA_BLACK,
                "color": TransitionStrategy.SNAP,
            },
        )

        assert hint.per_channel_overrides is not None
        assert hint.per_channel_overrides["dimmer"] == TransitionStrategy.FADE_VIA_BLACK
        assert hint.per_channel_overrides["color"] == TransitionStrategy.SNAP

    def test_is_snap_property(self):
        """Test is_snap property logic."""
        # SNAP mode
        assert TransitionHint(mode=TransitionMode.SNAP).is_snap is True

        # Zero duration
        assert TransitionHint(mode=TransitionMode.CROSSFADE, duration_bars=0.0).is_snap is True

        # Non-zero duration, non-SNAP mode
        assert TransitionHint(mode=TransitionMode.CROSSFADE, duration_bars=1.0).is_snap is False


class TestBoundary:
    """Test Boundary model."""

    def test_section_boundary(self):
        """Test creating a section boundary."""
        boundary = Boundary(
            type=BoundaryType.SECTION_BOUNDARY,
            source_id="verse_1",
            target_id="chorus_1",
            time_ms=40000,
            bar_position=16.0,
        )

        assert boundary.type == BoundaryType.SECTION_BOUNDARY
        assert boundary.source_id == "verse_1"
        assert boundary.target_id == "chorus_1"
        assert boundary.time_ms == 40000
        assert boundary.bar_position == 16.0

    def test_step_boundary(self):
        """Test creating a step boundary."""
        boundary = Boundary(
            type=BoundaryType.STEP_BOUNDARY,
            source_id="intro_step",
            target_id="main_step",
            time_ms=10000,
            bar_position=4.0,
        )

        assert boundary.type == BoundaryType.STEP_BOUNDARY
        assert boundary.source_id == "intro_step"
        assert boundary.target_id == "main_step"

    def test_basic_transition_plan(self):
        """Test creating a basic transition plan."""
        boundary = Boundary(
            type=BoundaryType.SECTION_BOUNDARY,
            source_id="verse_1",
            target_id="chorus_1",
            time_ms=40000,
            bar_position=16.0,
        )

        hint = TransitionHint(mode=TransitionMode.CROSSFADE, duration_bars=1.0)

        plan = TransitionPlan(
            transition_id="trans_001",
            boundary=boundary,
            hint=hint,
            overlap_start_ms=39000,
            overlap_end_ms=41000,
            overlap_duration_ms=2000,
            channel_strategies={
                ChannelName.PAN: TransitionStrategy.SMOOTH_INTERPOLATION,
                ChannelName.TILT: TransitionStrategy.SMOOTH_INTERPOLATION,
                ChannelName.DIMMER: TransitionStrategy.CROSSFADE,
            },
            fixtures=["fixture_1", "fixture_2"],
        )

        assert plan.transition_id == "trans_001"
        assert plan.boundary == boundary
        assert plan.hint == hint
        assert plan.overlap_start_ms == 39000
        assert plan.overlap_end_ms == 41000
        assert plan.overlap_duration_ms == 2000
        assert len(plan.channel_strategies) == 3
        assert len(plan.fixtures) == 2

    def test_duration_bars_property(self):
        """Test duration_bars property."""
        hint = TransitionHint(duration_bars=1.5)
        plan = TransitionPlan(
            transition_id="trans_001",
            boundary=Boundary(
                type=BoundaryType.SECTION_BOUNDARY,
                source_id="a",
                target_id="b",
                time_ms=0,
                bar_position=0.0,
            ),
            hint=hint,
            overlap_start_ms=0,
            overlap_end_ms=1000,
            overlap_duration_ms=1000,
        )

        assert plan.duration_bars == 1.5

    def test_metadata_storage(self):
        """Test metadata storage."""
        plan = TransitionPlan(
            transition_id="trans_001",
            boundary=Boundary(
                type=BoundaryType.SECTION_BOUNDARY,
                source_id="a",
                target_id="b",
                time_ms=0,
                bar_position=0.0,
            ),
            hint=TransitionHint(),
            overlap_start_ms=0,
            overlap_end_ms=1000,
            overlap_duration_ms=1000,
            metadata={"custom_key": "custom_value", "iteration": 1},
        )

        assert plan.metadata["custom_key"] == "custom_value"
        assert plan.metadata["iteration"] == 1


class TestTransitionRegistry:
    """Test TransitionRegistry model."""

    def test_add_transition(self):
        """Test adding transitions to registry."""
        registry = TransitionRegistry()

        plan1 = TransitionPlan(
            transition_id="trans_001",
            boundary=Boundary(
                type=BoundaryType.SECTION_BOUNDARY,
                source_id="verse",
                target_id="chorus",
                time_ms=40000,
                bar_position=16.0,
            ),
            hint=TransitionHint(),
            overlap_start_ms=39000,
            overlap_end_ms=41000,
            overlap_duration_ms=2000,
        )

        plan2 = TransitionPlan(
            transition_id="trans_002",
            boundary=Boundary(
                type=BoundaryType.SECTION_BOUNDARY,
                source_id="chorus",
                target_id="bridge",
                time_ms=80000,
                bar_position=32.0,
            ),
            hint=TransitionHint(),
            overlap_start_ms=79000,
            overlap_end_ms=81000,
            overlap_duration_ms=2000,
        )

        registry.add_transition(plan1)
        registry.add_transition(plan2)

        assert len(registry.transitions) == 2

    def test_get_by_boundary(self):
        """Test getting transition by boundary."""
        registry = TransitionRegistry()

        boundary = Boundary(
            type=BoundaryType.SECTION_BOUNDARY,
            source_id="verse",
            target_id="chorus",
            time_ms=40000,
            bar_position=16.0,
        )

        plan = TransitionPlan(
            transition_id="trans_001",
            boundary=boundary,
            hint=TransitionHint(),
            overlap_start_ms=39000,
            overlap_end_ms=41000,
            overlap_duration_ms=2000,
        )

        registry.add_transition(plan)

        # Find by matching boundary
        found = registry.get_by_boundary(boundary)
        assert found is not None
        assert found.transition_id == "trans_001"

        # Not found
        other_boundary = Boundary(
            type=BoundaryType.SECTION_BOUNDARY,
            source_id="other",
            target_id="section",
            time_ms=0,
            bar_position=0.0,
        )
        not_found = registry.get_by_boundary(other_boundary)
        assert not_found is None

    def test_get_incoming(self):
        """Test getting incoming transition for a section."""
        registry = TransitionRegistry()

        plan = TransitionPlan(
            transition_id="trans_001",
            boundary=Boundary(
                type=BoundaryType.SECTION_BOUNDARY,
                source_id="verse",
                target_id="chorus",
                time_ms=40000,
                bar_position=16.0,
            ),
            hint=TransitionHint(),
            overlap_start_ms=39000,
            overlap_end_ms=41000,
            overlap_duration_ms=2000,
        )

        registry.add_transition(plan)

        # Get transition INTO chorus
        incoming = registry.get_incoming("chorus")
        assert incoming is not None
        assert incoming.transition_id == "trans_001"

        # No transition INTO verse
        assert registry.get_incoming("verse") is None

    def test_get_outgoing(self):
        """Test getting outgoing transition from a section."""
        registry = TransitionRegistry()

        plan = TransitionPlan(
            transition_id="trans_001",
            boundary=Boundary(
                type=BoundaryType.SECTION_BOUNDARY,
                source_id="verse",
                target_id="chorus",
                time_ms=40000,
                bar_position=16.0,
            ),
            hint=TransitionHint(),
            overlap_start_ms=39000,
            overlap_end_ms=41000,
            overlap_duration_ms=2000,
        )

        registry.add_transition(plan)

        # Get transition OUT OF verse
        outgoing = registry.get_outgoing("verse")
        assert outgoing is not None
        assert outgoing.transition_id == "trans_001"

        # No transition OUT OF chorus
        assert registry.get_outgoing("chorus") is None

    def test_get_all_for_section(self):
        """Test getting all transitions involving a section."""
        registry = TransitionRegistry()

        plan1 = TransitionPlan(
            transition_id="trans_001",
            boundary=Boundary(
                type=BoundaryType.SECTION_BOUNDARY,
                source_id="verse",
                target_id="chorus",
                time_ms=40000,
                bar_position=16.0,
            ),
            hint=TransitionHint(),
            overlap_start_ms=39000,
            overlap_end_ms=41000,
            overlap_duration_ms=2000,
        )

        plan2 = TransitionPlan(
            transition_id="trans_002",
            boundary=Boundary(
                type=BoundaryType.SECTION_BOUNDARY,
                source_id="chorus",
                target_id="bridge",
                time_ms=80000,
                bar_position=32.0,
            ),
            hint=TransitionHint(),
            overlap_start_ms=79000,
            overlap_end_ms=81000,
            overlap_duration_ms=2000,
        )

        registry.add_transition(plan1)
        registry.add_transition(plan2)

        # Chorus has both incoming and outgoing
        chorus_transitions = registry.get_all_for_section("chorus")
        assert len(chorus_transitions) == 2

        # Verse has only outgoing
        verse_transitions = registry.get_all_for_section("verse")
        assert len(verse_transitions) == 1
        assert verse_transitions[0].transition_id == "trans_001"

        # Bridge has only incoming
        bridge_transitions = registry.get_all_for_section("bridge")
        assert len(bridge_transitions) == 1
        assert bridge_transitions[0].transition_id == "trans_002"

        # Unknown section
        unknown_transitions = registry.get_all_for_section("unknown")
        assert len(unknown_transitions) == 0
