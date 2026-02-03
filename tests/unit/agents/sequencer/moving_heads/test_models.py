"""Tests for moving heads agent response models."""

from pydantic import ValidationError
import pytest

from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    PlanSection,
)


def test_plan_section_model():
    """Test plan section model."""
    section = PlanSection(
        section_name="intro",
        start_bar=1,
        end_bar=8,
        template_id="sweep_lr_fan_pulse",
        preset_id="CHILL",
        modifiers={"intensity": "HIGH"},
        reasoning="Low energy section needs calm movement",
    )

    assert section.section_name == "intro"
    assert section.start_bar == 1
    assert section.end_bar == 8
    assert section.template_id == "sweep_lr_fan_pulse"
    assert section.preset_id == "CHILL"
    assert section.modifiers == {"intensity": "HIGH"}


def test_plan_section_minimal():
    """Test plan section with minimal required fields."""
    section = PlanSection(
        section_name="verse",
        start_bar=1,
        end_bar=16,
        template_id="circle_fan_hold",
    )

    assert section.section_name == "verse"
    assert section.start_bar == 1
    assert section.end_bar == 16
    assert section.template_id == "circle_fan_hold"
    assert section.preset_id is None
    assert section.modifiers == {}


def test_plan_section_bar_validation():
    """Test plan section validates bar range."""
    # Valid section
    section = PlanSection(
        section_name="intro",
        start_bar=1,
        end_bar=8,
        template_id="test",
    )
    assert section.end_bar >= section.start_bar

    # Invalid: end_bar before start_bar
    with pytest.raises(ValidationError):
        PlanSection(
            section_name="intro",
            start_bar=8,
            end_bar=1,
            template_id="test",
        )


def test_plan_section_start_bar_minimum():
    """Test plan section enforces minimum start_bar of 1."""
    # Test valid case with start_bar = 1
    section = PlanSection(
        section_name="intro",
        start_bar=1,
        end_bar=8,
        template_id="test",
    )
    assert section.start_bar == 1

    # Test invalid case with start_bar = 0 (bars are 1-indexed)
    with pytest.raises(ValidationError):
        PlanSection(
            section_name="intro",
            start_bar=0,
            end_bar=8,
            template_id="test",
        )


def test_choreography_plan_model():
    """Test complete choreography plan model."""
    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=8,
                template_id="sweep_lr_fan_pulse",
            )
        ],
        overall_strategy="Start calm and build energy",
    )

    assert len(plan.sections) == 1
    assert plan.sections[0].section_name == "intro"
    assert plan.overall_strategy == "Start calm and build energy"


def test_choreography_plan_validation():
    """Test choreography plan validation."""
    # Missing required fields should fail
    with pytest.raises(ValidationError):
        ChoreographyPlan(sections=[])  # Empty sections

    # Valid plan
    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=8,
                template_id="circle_fan_hold",
            )
        ]
    )
    assert plan.sections is not None
    assert len(plan.sections) == 1


def test_models_are_serializable():
    """Test all models can be serialized."""
    plan = ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=8,
                template_id="sweep_lr_fan_pulse",
            )
        ]
    )

    # All should serialize
    assert plan.model_dump()
