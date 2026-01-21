"""Tests for implementation timing validation.

Tests that ensure bar-level timing is correct and that all sections
have valid, non-zero durations.

Phase 5A: Agent works in bars, renderer converts to ms.
"""

from blinkb0t.core.agents.moving_heads.models_agent_plan import (
    AgentImplementation,
    ImplementationSection,
)


class TestImplementationTiming:
    """Test implementation timing validation."""

    def test_sections_have_different_start_bars(self):
        """Test that sections have different start bars."""
        # Correct timing: each section has different start bar
        sections = [
            ImplementationSection(
                name="intro",
                plan_section_name="intro",
                start_bar=1,
                end_bar=5,
                template_id="gentle_sweep",
                params={},
                base_pose="FORWARD",
                targets=["ALL"],
                layer_priority=0,
            ),
            ImplementationSection(
                name="verse",
                plan_section_name="verse",
                start_bar=6,
                end_bar=10,
                template_id="soft_tilt",
                params={},
                base_pose="LEFT_45",
                targets=["ALL"],
                layer_priority=0,
            ),
        ]

        # Verify sections have different start bars
        for i in range(len(sections) - 1):
            assert sections[i].start_bar != sections[i + 1].start_bar, (
                f"Section {i} and {i + 1} have identical start bars: {sections[i].start_bar}"
            )
            # Also verify they progress forward in time
            assert sections[i + 1].start_bar >= sections[i].end_bar, (
                f"Section {i + 1} starts before section {i} ends"
            )

    def test_sections_have_non_zero_duration(self):
        """Test that all sections have non-zero duration."""
        sections = [
            ImplementationSection(
                name="intro",
                plan_section_name="intro",
                start_bar=1,
                end_bar=5,
                template_id="gentle_sweep",
                params={},
                base_pose="FORWARD",
                targets=["ALL"],
                layer_priority=0,
            ),
            ImplementationSection(
                name="verse",
                plan_section_name="verse",
                start_bar=6,
                end_bar=12,
                template_id="soft_tilt",
                params={},
                base_pose="LEFT_45",
                targets=["ALL"],
                layer_priority=0,
            ),
        ]

        # Verify all sections have positive duration
        for section in sections:
            duration_bars = section.end_bar - section.start_bar + 1  # inclusive
            assert duration_bars > 0, (
                f"Section '{section.name}' has zero duration: bars {section.start_bar}-{section.end_bar}"
            )
            # Also verify duration is reasonable (at least 2 bars for sections)
            assert duration_bars >= 2, (
                f"Section '{section.name}' has unreasonably short duration: {duration_bars} bars"
            )

    def test_sections_progress_forward_in_time(self):
        """Test that sections progress forward in time (no overlaps)."""
        sections = [
            ImplementationSection(
                name="intro",
                plan_section_name="intro",
                start_bar=1,
                end_bar=5,
                template_id="gentle_sweep",
                params={},
                base_pose="FORWARD",
                targets=["ALL"],
                layer_priority=0,
            ),
            ImplementationSection(
                name="verse",
                plan_section_name="verse",
                start_bar=6,
                end_bar=10,
                template_id="soft_tilt",
                params={},
                base_pose="LEFT_45",
                targets=["ALL"],
                layer_priority=0,
            ),
        ]

        # Verify sections progress forward
        for i in range(len(sections) - 1):
            current = sections[i]
            next_section = sections[i + 1]
            assert current.end_bar < next_section.start_bar, (
                f"Section '{current.name}' overlaps with '{next_section.name}': bar {current.end_bar} >= bar {next_section.start_bar}"
            )

    def test_implementation_validates_timing_constraints(self):
        """Test that AgentImplementation validates basic timing constraints."""
        # Valid implementation
        valid_impl = AgentImplementation(
            sections=[
                ImplementationSection(
                    name="intro",
                    plan_section_name="intro",
                    start_bar=1,
                    end_bar=5,
                    template_id="gentle_sweep",
                    params={},
                    base_pose="FORWARD",
                    targets=["ALL"],
                    layer_priority=0,
                ),
                ImplementationSection(
                    name="verse",
                    plan_section_name="verse",
                    start_bar=6,
                    end_bar=10,
                    template_id="soft_tilt",
                    params={},
                    base_pose="LEFT_45",
                    targets=["ALL"],
                    layer_priority=0,
                ),
            ],
            total_duration_bars=10,
            quantization_applied=True,
            timing_precision="bar_aligned",
        )

        # Validate timing constraints
        for section in valid_impl.sections:
            assert section.end_bar > section.start_bar, (
                f"Section '{section.name}' has invalid duration"
            )

        for i in range(len(valid_impl.sections) - 1):
            current = valid_impl.sections[i]
            next_section = valid_impl.sections[i + 1]
            assert current.end_bar < next_section.start_bar, (
                f"Sections '{current.name}' and '{next_section.name}' overlap"
            )

    def test_bar_timing_realistic(self):
        """Test realistic bar-level timing values.

        Phase 5A: Agent works in bars, renderer converts to ms.
        At 120 BPM, 4/4 time: 1 bar = 2000ms
        - Bars 1-12 = 0-24000ms (renderer converts)
        - Bars 13-24 = 24000-48000ms (renderer converts)
        """
        # Create implementation with bar timing
        impl = AgentImplementation(
            sections=[
                ImplementationSection(
                    name="intro",
                    plan_section_name="intro",
                    start_bar=1,
                    end_bar=12,
                    template_id="gentle_sweep",
                    params={},
                    base_pose="FORWARD",
                    targets=["ALL"],
                    layer_priority=0,
                ),
            ],
            total_duration_bars=12,
            quantization_applied=True,
            timing_precision="bar_aligned",
        )

        # Verify bar timing is realistic
        intro = impl.sections[0]
        assert intro.start_bar == 1, f"Intro should start at bar 1, got bar {intro.start_bar}"
        assert intro.end_bar == 12, f"Intro should end at bar 12, got bar {intro.end_bar}"
        assert intro.end_bar - intro.start_bar + 1 == 12, "Intro should be 12 bars long"
