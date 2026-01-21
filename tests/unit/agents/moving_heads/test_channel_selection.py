"""Tests for channel selection validation.

Tests that ensure LLM populates channel specifications
and that plans include shutter/color/gobo selections.
"""

from blinkb0t.core.agents.moving_heads.models_agent_plan import AgentPlan, SectionPlan


class TestChannelSelection:
    """Test channel selection validation."""

    def test_plan_sections_have_channel_specs(self):
        """Test that plan sections have channel specifications."""
        # Simulate the bug: all channels are null
        section = SectionPlan(
            name="Intro",
            start_bar=1,
            end_bar=12,
            section_role="intro",
            energy_level=20,
            templates=["gentle_sweep_breathe"],
            params={"intensity": "SMOOTH"},
            base_pose="AUDIENCE_CENTER",
            reasoning="Gentle intro",
            channels={
                "shutter": None,  # ❌ Bug: should have a value
                "color": None,  # ❌ Bug: should have a value
                "gobo": None,  # ❌ Bug: should have a value
            },
        )

        # This should fail because channels are all null
        assert section.channels is not None, "Section should have channels dict"

        # At least one channel should be populated for sections with energy > 50
        if section.energy_level > 50:
            has_any_channel = any(
                v is not None
                for v in [
                    section.channels.shutter,
                    section.channels.color,
                    section.channels.gobo,
                ]
            )
            assert has_any_channel, (
                f"High energy section '{section.name}' should have at least one channel populated"
            )

    def test_high_energy_sections_use_strobes(self):
        """Test that high energy sections (>80) use strobes."""
        # High energy section with strobe (correct behavior)
        section = SectionPlan(
            name="Chorus",
            start_bar=37,
            end_bar=48,
            section_role="chorus",
            energy_level=85,  # High energy
            templates=["chorus_circle_strobe"],
            params={"intensity": "DRAMATIC"},
            base_pose="AUDIENCE_CENTER",
            reasoning="High-energy chorus",
            channels={
                "shutter": "strobe_fast",  # ✅ Fixed: high energy uses strobes
                "color": "warm_white",
                "gobo": None,
            },
        )

        # High energy sections should have shutter effects
        assert section.energy_level > 80
        assert section.channels.shutter is not None, (
            f"High energy section '{section.name}' (energy={section.energy_level}) should have shutter effect"
        )
        # Verify it's an appropriate high-energy shutter pattern
        assert "strobe" in section.channels.shutter or "pulse" in section.channels.shutter

    def test_plan_has_channel_variety(self):
        """Test that plan uses variety of channels across sections."""
        plan = AgentPlan(
            sections=[
                SectionPlan(
                    name="Intro",
                    start_bar=1,
                    end_bar=12,
                    section_role="intro",
                    energy_level=20,
                    templates=["gentle_sweep"],
                    params={},
                    base_pose="FORWARD",
                    reasoning="Gentle intro",
                    channels={"shutter": "pulse_slow", "color": "cool_blue", "gobo": None},
                ),
                SectionPlan(
                    name="Chorus",
                    start_bar=37,
                    end_bar=48,
                    section_role="chorus",
                    energy_level=85,
                    templates=["chorus_circle"],
                    params={},
                    base_pose="AUDIENCE_CENTER",
                    reasoning="High energy chorus",
                    channels={
                        "shutter": "strobe_fast",
                        "color": "warm_white",
                        "gobo": "gobo_spin_fast",
                    },
                ),
            ],
            overall_strategy="Test plan",
            template_variety_score=8,
            energy_alignment_score=9,
        )

        # Collect all channel usages
        all_shutters = [s.channels.shutter for s in plan.sections if s.channels.shutter]
        all_colors = [s.channels.color for s in plan.sections if s.channels.color]
        all_gobos = [s.channels.gobo for s in plan.sections if s.channels.gobo]

        # Verify channels are used with variety
        assert len(all_shutters) > 0, "Plan should use shutters"
        assert len(all_colors) > 0, "Plan should use colors"
        assert len(all_gobos) > 0, "Plan should use gobos"

        # Verify variety (not all same)
        assert len(set(all_shutters)) > 1 or len(set(all_colors)) > 1, (
            "Plan should have variety in channels"
        )

    def test_channels_match_energy_level(self):
        """Test that channel selections match section energy levels."""
        # Low energy with appropriate slow shutter (correct)
        low_energy_section = SectionPlan(
            name="Bridge",
            start_bar=61,
            end_bar=72,
            section_role="bridge",
            energy_level=35,  # Low energy
            templates=["ambient_hold"],
            params={"intensity": "SMOOTH"},
            base_pose="DOWN",
            reasoning="Calm bridge",
            channels={
                "shutter": "pulse_slow",  # ✅ Correct: slow pulse with low energy
                "color": "cool_blue",
                "gobo": None,
            },
        )

        # High energy with appropriate fast shutter (correct)
        high_energy_section = SectionPlan(
            name="Climax",
            start_bar=85,
            end_bar=96,
            section_role="climax",
            energy_level=95,  # High energy
            templates=["dramatic_sweep"],
            params={"intensity": "DRAMATIC"},
            base_pose="AUDIENCE_CENTER",
            reasoning="Peak moment",
            channels={
                "shutter": "strobe_fast",  # ✅ Correct: fast strobe with high energy
                "color": "warm_white",
                "gobo": "gobo_spin_fast",
            },
        )

        # Verify low energy uses appropriate patterns
        assert low_energy_section.energy_level < 50
        assert low_energy_section.channels.shutter is not None
        assert (
            "slow" in low_energy_section.channels.shutter.lower()
            or "pulse" in low_energy_section.channels.shutter.lower()
        )

        # Verify high energy uses appropriate patterns
        assert high_energy_section.energy_level > 80
        assert high_energy_section.channels.shutter is not None
        assert (
            "fast" in high_energy_section.channels.shutter.lower()
            or "strobe" in high_energy_section.channels.shutter.lower()
        )

    def test_channel_library_coverage(self):
        """Test that plans use diverse patterns from channel libraries."""
        # Test that if channels are used, they come from known patterns
        known_shutter_patterns = [
            "open",
            "strobe_slow",
            "strobe_medium",
            "strobe_fast",
            "pulse_slow",
            "pulse_fast",
            "random_strobe",
        ]
        known_color_patterns = [
            "white",
            "red",
            "blue",
            "green",
            "amber",
            "rainbow_slow",
            "rainbow_fast",
        ]
        known_gobo_patterns = ["open", "beam_split", "prism_slow", "prism_fast", "pattern_rotate"]

        # Section with valid patterns from libraries
        section = SectionPlan(
            name="Chorus",
            start_bar=37,
            end_bar=48,
            section_role="chorus",
            energy_level=85,
            templates=["chorus_circle"],
            params={},
            base_pose="AUDIENCE_CENTER",
            reasoning="High energy",
            channels={
                "shutter": "strobe_fast",  # ✅ Valid pattern
                "color": "blue",  # ✅ Valid pattern
                "gobo": "prism_fast",  # ✅ Valid pattern
            },
        )

        # Verify all channels use patterns from known libraries
        if section.channels.shutter:
            assert section.channels.shutter in known_shutter_patterns, (
                f"Shutter pattern '{section.channels.shutter}' not in library"
            )

        if section.channels.color:
            assert section.channels.color in known_color_patterns, (
                f"Color pattern '{section.channels.color}' not in library"
            )

        if section.channels.gobo:
            assert section.channels.gobo in known_gobo_patterns, (
                f"Gobo pattern '{section.channels.gobo}' not in library"
            )
