"""Tests for MacroSectionPlan model."""

from pydantic import ValidationError
import pytest

from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.sequencer.planning import MacroSectionPlan
from twinklr.core.sequencer.vocabulary import ChoreographyStyle, EnergyTarget, MotionDensity


def test_macro_section_plan_valid():
    """Valid MacroSectionPlan passes."""
    plan = MacroSectionPlan(
        section=SongSectionRef(
            section_id="chorus_1", name="Chorus 1", start_ms=30000, end_ms=45000
        ),
        energy_target=EnergyTarget.HIGH,
        primary_focus_targets=["OUTLINE", "MEGA_TREE"],
        choreography_style=ChoreographyStyle.IMAGERY,
        motion_density=MotionDensity.BUSY,
        notes="Big chorus, full display synchronized for maximum impact",
    )
    assert len(plan.primary_focus_targets) == 2
    assert plan.energy_target == EnergyTarget.HIGH
    assert plan.motion_density == MotionDensity.BUSY


def test_invalid_target_role():
    """Invalid target role rejected."""
    with pytest.raises(ValidationError, match="Invalid target role"):
        MacroSectionPlan(
            section=SongSectionRef(
                section_id="verse1", name="Verse 1", start_ms=10000, end_ms=25000
            ),
            energy_target=EnergyTarget.MED,
            primary_focus_targets=["INVALID_ROLE"],
            choreography_style=ChoreographyStyle.ABSTRACT,
            motion_density=MotionDensity.MED,
            notes="Test notes that are long enough for validation",
        )


def test_zero_focus_targets():
    """Empty primary_focus_targets rejected."""
    with pytest.raises(ValidationError):
        MacroSectionPlan(
            section=SongSectionRef(
                section_id="verse1", name="Verse 1", start_ms=10000, end_ms=25000
            ),
            energy_target=EnergyTarget.MED,
            primary_focus_targets=[],
            choreography_style=ChoreographyStyle.ABSTRACT,
            motion_density=MotionDensity.MED,
            notes="Test notes that are long enough for validation",
        )


def test_invalid_secondary_target():
    """Invalid secondary target role rejected."""
    with pytest.raises(ValidationError, match="Invalid target role"):
        MacroSectionPlan(
            section=SongSectionRef(
                section_id="verse1", name="Verse 1", start_ms=10000, end_ms=25000
            ),
            energy_target=EnergyTarget.MED,
            primary_focus_targets=["OUTLINE"],
            secondary_targets=["INVALID_SECONDARY"],
            choreography_style=ChoreographyStyle.ABSTRACT,
            motion_density=MotionDensity.MED,
            notes="Test notes that are long enough for validation",
        )


def test_notes_too_short():
    """Notes < 20 characters rejected."""
    with pytest.raises(ValidationError):
        MacroSectionPlan(
            section=SongSectionRef(
                section_id="verse1", name="Verse 1", start_ms=10000, end_ms=25000
            ),
            energy_target=EnergyTarget.MED,
            primary_focus_targets=["OUTLINE"],
            choreography_style=ChoreographyStyle.ABSTRACT,
            motion_density=MotionDensity.MED,
            notes="Short",
        )


def test_secondary_targets_optional():
    """Secondary targets are optional."""
    plan = MacroSectionPlan(
        section=SongSectionRef(section_id="intro", name="Intro", start_ms=0, end_ms=10000),
        energy_target=EnergyTarget.LOW,
        primary_focus_targets=["OUTLINE"],
        choreography_style=ChoreographyStyle.ABSTRACT,
        motion_density=MotionDensity.SPARSE,
        notes="Simple intro with outline only, building anticipation",
    )
    assert plan.secondary_targets == []


def test_macro_section_plan_with_secondary():
    """MacroSectionPlan with secondary targets."""
    plan = MacroSectionPlan(
        section=SongSectionRef(
            section_id="chorus_2", name="Chorus 2", start_ms=60000, end_ms=75000
        ),
        energy_target=EnergyTarget.PEAK,
        primary_focus_targets=["MEGA_TREE", "OUTLINE"],
        secondary_targets=["PROPS", "FLOODS"],
        choreography_style=ChoreographyStyle.HYBRID,
        motion_density=MotionDensity.BUSY,
        notes="Peak moment with all elements engaged for maximum wow factor",
    )
    assert len(plan.primary_focus_targets) == 2
    assert len(plan.secondary_targets) == 2


def test_macro_section_plan_serialization():
    """MacroSectionPlan serializes to/from JSON."""
    plan = MacroSectionPlan(
        section=SongSectionRef(section_id="bridge", name="Bridge", start_ms=90000, end_ms=105000),
        energy_target=EnergyTarget.BUILD,
        primary_focus_targets=["HERO"],
        secondary_targets=["ARCHES"],
        choreography_style=ChoreographyStyle.IMAGERY,
        motion_density=MotionDensity.MED,
        notes="Building energy through bridge with hero element leading the charge",
    )

    # Export to JSON
    json_str = plan.model_dump_json(indent=2)
    assert "bridge" in json_str
    assert "BUILD" in json_str

    # Import from JSON
    plan2 = MacroSectionPlan.model_validate_json(json_str)
    assert plan == plan2
