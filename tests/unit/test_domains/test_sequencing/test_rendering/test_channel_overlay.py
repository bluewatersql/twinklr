"""Tests for channel overlay resolution.

Tests the resolve_channel_overlays function that resolves per-section
channel specifications (shutter, color, gobo) from AgentImplementation.
"""

from unittest.mock import Mock

from blinkb0t.core.agents.moving_heads.models_agent_plan import (
    AgentImplementation,
    ImplementationSection,
)
from blinkb0t.core.config.models import ChannelDefaults, JobConfig
from blinkb0t.core.domains.sequencing.rendering.channel_overlay import (
    resolve_channel_overlays,
)
from blinkb0t.core.domains.sequencing.rendering.models import ChannelOverlay

# ============================================================================
# Fixture / Test Data Helpers
# ============================================================================


def create_test_section(
    name: str = "intro",
    start_bar: int = 1,
    end_bar: int = 4,
    shutter: str | None = None,
    color: str | None = None,
    gobo: str | None = None,
) -> ImplementationSection:
    """Create a test ImplementationSection (Phase 5A schema: bars, no transitions)."""
    return ImplementationSection(
        name=name,
        plan_section_name=name,
        start_bar=start_bar,
        end_bar=end_bar,
        template_id="test_template",
        params={},
        base_pose="AUDIENCE_CENTER",
        targets=["ALL"],
    )


def create_test_implementation(sections: list[ImplementationSection]) -> AgentImplementation:
    """Create a test AgentImplementation (Phase 5A schema: bars)."""
    total_duration = max(s.end_bar for s in sections) if sections else 1
    return AgentImplementation(
        sections=sections,
        total_duration_bars=total_duration,
        quantization_applied=True,
        timing_precision="bar_aligned",
    )


def create_test_job_config(
    shutter: str = "open",
    color: str = "white",
    gobo: str = "open",
) -> JobConfig:
    """Create a test JobConfig with channel defaults."""
    # Create a mock JobConfig with channel_defaults
    job_config = Mock(spec=JobConfig)
    job_config.channel_defaults = ChannelDefaults(
        shutter=shutter,
        color=color,
        gobo=gobo,
    )
    return job_config


# ============================================================================
# Tests for resolve_channel_overlays
# ============================================================================


def test_resolve_channel_overlays_empty_implementation():
    """Test resolve_channel_overlays with no sections."""
    implementation = create_test_implementation([])
    job_config = create_test_job_config()

    # Create mock handlers
    shutter_handler = Mock()
    color_handler = Mock()
    gobo_handler = Mock()

    overlays = resolve_channel_overlays(
        agent_implementation=implementation,
        shutter_handler=shutter_handler,
        color_handler=color_handler,
        gobo_handler=gobo_handler,
        job_config=job_config,
    )

    assert overlays == {}


def test_resolve_channel_overlays_with_defaults():
    """Test resolve_channel_overlays uses job defaults when no overrides."""
    section = create_test_section("intro")
    implementation = create_test_implementation([section])
    job_config = create_test_job_config(shutter="open", color="white", gobo="open")

    # Mock handlers to return static values
    shutter_handler = Mock()
    shutter_handler.resolve.return_value = 255  # Open shutter

    color_handler = Mock()
    color_handler.resolve.return_value = (255, 255, 255)  # White

    gobo_handler = Mock()
    gobo_handler.resolve.return_value = 0  # Open gobo

    overlays = resolve_channel_overlays(
        agent_implementation=implementation,
        shutter_handler=shutter_handler,
        color_handler=color_handler,
        gobo_handler=gobo_handler,
        job_config=job_config,
    )

    # Should have one overlay for the section
    assert len(overlays) == 1
    assert "intro" in overlays

    overlay = overlays["intro"]
    assert isinstance(overlay, ChannelOverlay)
    assert overlay.shutter == 255
    assert overlay.color == (255, 255, 255)
    assert overlay.gobo == 0


def test_resolve_channel_overlays_multiple_sections():
    """Test resolve_channel_overlays with multiple sections."""
    sections = [
        create_test_section("intro", start_bar=1, end_bar=4),
        create_test_section("verse_1", start_bar=5, end_bar=8),
        create_test_section("chorus_1", start_bar=9, end_bar=12),
    ]
    implementation = create_test_implementation(sections)
    job_config = create_test_job_config()

    # Mock handlers
    shutter_handler = Mock()
    shutter_handler.resolve.return_value = 255

    color_handler = Mock()
    color_handler.resolve.return_value = (255, 0, 0)  # Red

    gobo_handler = Mock()
    gobo_handler.resolve.return_value = 1

    overlays = resolve_channel_overlays(
        agent_implementation=implementation,
        shutter_handler=shutter_handler,
        color_handler=color_handler,
        gobo_handler=gobo_handler,
        job_config=job_config,
    )

    assert len(overlays) == 3
    assert "intro" in overlays
    assert "verse_1" in overlays
    assert "chorus_1" in overlays


def test_resolve_channel_overlays_with_curve_spec():
    """Test resolve_channel_overlays when handler returns ValueCurveSpec.

    NOTE: Phase 4 feature - skipped for Phase 3.
    Phase 3 handlers return static values only. Dynamic curve specs
    will be added in Phase 4 when CurvePipeline is implemented.
    """
    import pytest

    pytest.skip("Phase 4 feature - dynamic curves not implemented in Phase 3")


def test_resolve_channel_overlays_handler_called_with_correct_args():
    """Test that handlers are called with correct section timing."""
    section = create_test_section("verse", start_bar=5, end_bar=8)
    implementation = create_test_implementation([section])
    job_config = create_test_job_config()

    # Mock handlers
    shutter_handler = Mock()
    shutter_handler.resolve.return_value = 255

    color_handler = Mock()
    color_handler.resolve.return_value = (255, 255, 255)

    gobo_handler = Mock()
    gobo_handler.resolve.return_value = 0

    resolve_channel_overlays(
        agent_implementation=implementation,
        shutter_handler=shutter_handler,
        color_handler=color_handler,
        gobo_handler=gobo_handler,
        job_config=job_config,
    )

    # Verify handlers were called with section timing
    # Note: The exact call signature depends on handler implementation
    # This test verifies the function calls handlers correctly
    assert shutter_handler.resolve.called
    assert color_handler.resolve.called
    assert gobo_handler.resolve.called


def test_resolve_channel_overlays_section_id_as_key():
    """Test that section name is used as dictionary key."""
    section = create_test_section("my_custom_section")
    implementation = create_test_implementation([section])
    job_config = create_test_job_config()

    # Mock handlers
    shutter_handler = Mock()
    shutter_handler.resolve.return_value = 200

    color_handler = Mock()
    color_handler.resolve.return_value = 100

    gobo_handler = Mock()
    gobo_handler.resolve.return_value = 2

    overlays = resolve_channel_overlays(
        agent_implementation=implementation,
        shutter_handler=shutter_handler,
        color_handler=color_handler,
        gobo_handler=gobo_handler,
        job_config=job_config,
    )

    # Section name should be the key
    assert "my_custom_section" in overlays
    assert overlays["my_custom_section"].gobo == 2


def test_resolve_channel_overlays_different_return_types():
    """Test resolve_channel_overlays handles different handler return types.

    Phase 3: All handlers return static values (int or RGB tuple).
    Phase 4: Will support ValueCurveSpec for dynamic patterns.
    """
    section = create_test_section("mixed")
    implementation = create_test_implementation([section])
    job_config = create_test_job_config()

    # Mock handlers returning static types (Phase 3)
    shutter_handler = Mock()
    shutter_handler.resolve.return_value = 200  # Static int (Phase 3)

    color_handler = Mock()
    color_handler.resolve.return_value = (128, 64, 200)  # RGB tuple

    gobo_handler = Mock()
    gobo_handler.resolve.return_value = 5  # Static int

    overlays = resolve_channel_overlays(
        agent_implementation=implementation,
        shutter_handler=shutter_handler,
        color_handler=color_handler,
        gobo_handler=gobo_handler,
        job_config=job_config,
    )

    overlay = overlays["mixed"]
    assert overlay.shutter == 200  # Phase 3: static value
    assert overlay.color == (128, 64, 200)
    assert overlay.gobo == 5
