"""Tests for LLM choreography plan models.

These models represent the simplified LLM response schema for template-based
choreography. The LLM selects templates + presets + modifiers rather than
generating raw implementation details.
"""

from pydantic import ValidationError
import pytest


class TestSectionSelection:
    """Test cases for SectionSelection model."""

    def test_valid_minimal_selection(self) -> None:
        """Test minimal valid section selection with only template_id."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import SectionSelection

        selection = SectionSelection(
            section_name="verse_1",
            start_bar=1,
            end_bar=16,
            template_id="fan_pulse",
        )
        assert selection.section_name == "verse_1"
        assert selection.start_bar == 1
        assert selection.end_bar == 16
        assert selection.template_id == "fan_pulse"
        assert selection.preset_id is None
        assert selection.modifiers == {}

    def test_valid_full_selection(self) -> None:
        """Test full section selection with all fields."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import SectionSelection

        selection = SectionSelection(
            section_name="chorus_1",
            start_bar=17,
            end_bar=32,
            section_role="chorus",
            energy_level=80,
            template_id="sweep_pulse",
            preset_id="ENERGETIC",
            modifiers={"intensity": "HIGH", "speed": "FAST"},
            reasoning="High energy chorus needs dramatic sweeping motion",
        )
        assert selection.template_id == "sweep_pulse"
        assert selection.preset_id == "ENERGETIC"
        assert selection.modifiers == {"intensity": "HIGH", "speed": "FAST"}
        assert selection.reasoning == "High energy chorus needs dramatic sweeping motion"

    def test_rejects_empty_template_id(self) -> None:
        """Test that empty template_id is rejected."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import SectionSelection

        with pytest.raises(ValidationError) as exc:
            SectionSelection(
                section_name="verse_1",
                start_bar=1,
                end_bar=16,
                template_id="",
            )
        assert "template_id" in str(exc.value)

    def test_rejects_empty_section_name(self) -> None:
        """Test that empty section_name is rejected."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import SectionSelection

        with pytest.raises(ValidationError) as exc:
            SectionSelection(
                section_name="",
                start_bar=1,
                end_bar=16,
                template_id="fan_pulse",
            )
        assert "section_name" in str(exc.value)

    def test_rejects_invalid_bar_range(self) -> None:
        """Test that start_bar > end_bar is rejected."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import SectionSelection

        with pytest.raises(ValidationError) as exc:
            SectionSelection(
                section_name="verse_1",
                start_bar=20,
                end_bar=10,
                template_id="fan_pulse",
            )
        assert "end_bar" in str(exc.value).lower() or "start_bar" in str(exc.value).lower()

    def test_rejects_zero_start_bar(self) -> None:
        """Test that start_bar < 1 is rejected (bars are 1-indexed)."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import SectionSelection

        with pytest.raises(ValidationError) as exc:
            SectionSelection(
                section_name="verse_1",
                start_bar=0,
                end_bar=16,
                template_id="fan_pulse",
            )
        assert "start_bar" in str(exc.value)

    def test_energy_level_bounds(self) -> None:
        """Test that energy_level is bounded 0-100."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import SectionSelection

        # Valid energy levels
        selection = SectionSelection(
            section_name="test",
            start_bar=1,
            end_bar=8,
            template_id="fan_pulse",
            energy_level=0,
        )
        assert selection.energy_level == 0

        selection = SectionSelection(
            section_name="test",
            start_bar=1,
            end_bar=8,
            template_id="fan_pulse",
            energy_level=100,
        )
        assert selection.energy_level == 100

        # Invalid energy levels
        with pytest.raises(ValidationError):
            SectionSelection(
                section_name="test",
                start_bar=1,
                end_bar=8,
                template_id="fan_pulse",
                energy_level=-1,
            )

        with pytest.raises(ValidationError):
            SectionSelection(
                section_name="test",
                start_bar=1,
                end_bar=8,
                template_id="fan_pulse",
                energy_level=101,
            )

    def test_serialization_round_trip(self) -> None:
        """Test that model serializes and deserializes correctly."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import SectionSelection

        original = SectionSelection(
            section_name="chorus_1",
            start_bar=17,
            end_bar=32,
            section_role="chorus",
            energy_level=80,
            template_id="sweep_pulse",
            preset_id="ENERGETIC",
            modifiers={"intensity": "HIGH"},
            reasoning="Test reasoning",
        )
        json_data = original.model_dump()
        restored = SectionSelection.model_validate(json_data)

        assert restored.section_name == original.section_name
        assert restored.template_id == original.template_id
        assert restored.preset_id == original.preset_id
        assert restored.modifiers == original.modifiers


class TestLLMChoreographyPlan:
    """Test cases for LLMChoreographyPlan model."""

    def test_valid_single_section_plan(self) -> None:
        """Test valid plan with single section."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import (
            LLMChoreographyPlan,
            SectionSelection,
        )

        plan = LLMChoreographyPlan(
            sections=[
                SectionSelection(
                    section_name="intro",
                    start_bar=1,
                    end_bar=8,
                    template_id="fan_pulse",
                )
            ],
            overall_strategy="Simple intro with fan pattern",
        )
        assert len(plan.sections) == 1
        assert plan.overall_strategy == "Simple intro with fan pattern"

    def test_valid_multi_section_plan(self) -> None:
        """Test valid plan with multiple sections."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import (
            LLMChoreographyPlan,
            SectionSelection,
        )

        plan = LLMChoreographyPlan(
            sections=[
                SectionSelection(
                    section_name="verse_1",
                    start_bar=1,
                    end_bar=16,
                    template_id="fan_pulse",
                    preset_id="CHILL",
                ),
                SectionSelection(
                    section_name="chorus_1",
                    start_bar=17,
                    end_bar=32,
                    template_id="sweep_pulse",
                    preset_id="ENERGETIC",
                    modifiers={"intensity": "HIGH"},
                ),
                SectionSelection(
                    section_name="verse_2",
                    start_bar=33,
                    end_bar=48,
                    template_id="fan_pulse",
                    preset_id="CHILL",
                ),
            ],
            overall_strategy="Build energy from verse to chorus, reset for verse 2",
            template_variety_notes="Used fan_pulse twice for continuity, sweep_pulse for contrast",
        )
        assert len(plan.sections) == 3
        assert plan.sections[1].template_id == "sweep_pulse"
        assert plan.template_variety_notes is not None

    def test_rejects_empty_sections(self) -> None:
        """Test that empty sections list is rejected."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import LLMChoreographyPlan

        with pytest.raises(ValidationError) as exc:
            LLMChoreographyPlan(
                sections=[],
                overall_strategy="No sections",
            )
        assert "sections" in str(exc.value)

    def test_rejects_empty_strategy(self) -> None:
        """Test that empty overall_strategy is rejected."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import (
            LLMChoreographyPlan,
            SectionSelection,
        )

        with pytest.raises(ValidationError) as exc:
            LLMChoreographyPlan(
                sections=[
                    SectionSelection(
                        section_name="verse_1",
                        start_bar=1,
                        end_bar=16,
                        template_id="fan_pulse",
                    )
                ],
                overall_strategy="",
            )
        assert "overall_strategy" in str(exc.value)

    def test_serialization_round_trip(self) -> None:
        """Test that plan serializes and deserializes correctly."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import (
            LLMChoreographyPlan,
            SectionSelection,
        )

        original = LLMChoreographyPlan(
            sections=[
                SectionSelection(
                    section_name="verse_1",
                    start_bar=1,
                    end_bar=16,
                    template_id="fan_pulse",
                    preset_id="CHILL",
                    modifiers={"intensity": "SMOOTH"},
                )
            ],
            overall_strategy="Test strategy",
            template_variety_notes="Test notes",
        )
        json_data = original.model_dump()
        restored = LLMChoreographyPlan.model_validate(json_data)

        assert len(restored.sections) == len(original.sections)
        assert restored.sections[0].template_id == original.sections[0].template_id
        assert restored.overall_strategy == original.overall_strategy

    def test_extra_fields_forbidden(self) -> None:
        """Test that extra fields are forbidden (strict schema)."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import (
            LLMChoreographyPlan,
            SectionSelection,
        )

        with pytest.raises(ValidationError) as exc:
            LLMChoreographyPlan(
                sections=[
                    SectionSelection(
                        section_name="verse_1",
                        start_bar=1,
                        end_bar=16,
                        template_id="fan_pulse",
                    )
                ],
                overall_strategy="Test",
                unknown_field="should fail",  # type: ignore[call-arg]
            )
        assert "extra" in str(exc.value).lower() or "unknown_field" in str(exc.value)


class TestModifierValidation:
    """Test cases for modifier validation."""

    def test_valid_modifier_keys(self) -> None:
        """Test that valid modifier keys are accepted."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import SectionSelection

        selection = SectionSelection(
            section_name="test",
            start_bar=1,
            end_bar=8,
            template_id="fan_pulse",
            modifiers={
                "intensity": "HIGH",
                "speed": "FAST",
                "variation": "A",
            },
        )
        assert len(selection.modifiers) == 3

    def test_modifiers_are_strings(self) -> None:
        """Test that modifier values must be strings (categorical)."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import SectionSelection

        # String values should work
        selection = SectionSelection(
            section_name="test",
            start_bar=1,
            end_bar=8,
            template_id="fan_pulse",
            modifiers={"intensity": "HIGH"},
        )
        assert selection.modifiers["intensity"] == "HIGH"


class TestIntegrationWithPlaybackPlan:
    """Test that LLM output aligns with PlaybackPlan model."""

    def test_section_selection_to_playback_plan_conversion(self) -> None:
        """Test that SectionSelection data can be used to create PlaybackPlan."""
        from blinkb0t.core.agents.moving_heads.models_llm_plan import SectionSelection
        from blinkb0t.core.sequencer.moving_heads.models.plan import PlaybackPlan

        # LLM selects template for a section
        selection = SectionSelection(
            section_name="chorus_1",
            start_bar=17,
            end_bar=32,
            template_id="sweep_pulse",
            preset_id="ENERGETIC",
            modifiers={"intensity": "HIGH"},
        )

        # Convert to PlaybackPlan (timing would come from beat mapper)
        # Here we simulate 120 BPM, 4 beats/bar -> 2000ms/bar
        ms_per_bar = 2000
        window_start_ms = (selection.start_bar - 1) * ms_per_bar
        window_end_ms = selection.end_bar * ms_per_bar

        plan = PlaybackPlan(
            template_id=selection.template_id,
            preset_id=selection.preset_id,
            modifiers=selection.modifiers,
            window_start_ms=window_start_ms,
            window_end_ms=window_end_ms,
        )

        assert plan.template_id == "sweep_pulse"
        assert plan.preset_id == "ENERGETIC"
        assert plan.modifiers == {"intensity": "HIGH"}
        assert plan.window_start_ms == 32000  # bar 17 starts at (17-1)*2000
        assert plan.window_end_ms == 64000  # bar 32 ends at 32*2000
