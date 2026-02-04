"""Tests for MacroPlan root schema."""

from pydantic import ValidationError
import pytest

from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.sequencer.planning import (
    GlobalStory,
    LayeringPlan,
    LayerSpec,
    MacroPlan,
    MacroSectionPlan,
    TargetSelector,
)
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ChoreographyStyle,
    EnergyTarget,
    LayerRole,
    MotionDensity,
    TimingDriver,
)


def _create_section_ref(section_id: str, name: str, start_ms: int, end_ms: int) -> SongSectionRef:
    """Helper to create SongSectionRef."""
    return SongSectionRef(section_id=section_id, name=name, start_ms=start_ms, end_ms=end_ms)


def _create_section_plan(
    section_id: str,
    name: str,
    start_ms: int,
    end_ms: int,
    energy: EnergyTarget,
) -> MacroSectionPlan:
    """Helper to create MacroSectionPlan."""
    return MacroSectionPlan(
        section=_create_section_ref(section_id, name, start_ms, end_ms),
        energy_target=energy,
        primary_focus_targets=["OUTLINE"],
        choreography_style=ChoreographyStyle.ABSTRACT,
        motion_density=MotionDensity.MED,
        notes="Test section plan notes for validation",
    )


def _create_global_story() -> GlobalStory:
    """Helper to create GlobalStory."""
    return GlobalStory(
        theme="Christmas magic with cascading light waves",
        motifs=["Starbursts", "Waves", "Sparkles"],
        pacing_notes="Build energy through verses, peak at chorus, gentle outro",
        color_story="Cool blues transitioning to warm golds at climax",
    )


def _create_layering_plan() -> LayeringPlan:
    """Helper to create LayeringPlan."""
    base = LayerSpec(
        layer_index=0,
        layer_role=LayerRole.BASE,
        target_selector=TargetSelector(roles=["OUTLINE"]),
        blend_mode=BlendMode.NORMAL,
        timing_driver=TimingDriver.BARS,
        usage_notes="Foundation layer with slow evolving patterns",
    )
    return LayeringPlan(layers=[base], strategy_notes="Single base layer for clean foundation")


def test_macro_plan_valid_minimal():
    """Valid MacroPlan with minimal required fields."""
    plan = MacroPlan(
        global_story=_create_global_story(),
        layering_plan=_create_layering_plan(),
        section_plans=[_create_section_plan("intro", "Intro", 0, 10000, EnergyTarget.LOW)],
        asset_requirements=[],
    )

    assert plan.global_story.theme == "Christmas magic with cascading light waves"
    assert len(plan.section_plans) == 1
    assert len(plan.asset_requirements) == 0


def test_macro_plan_valid_complete():
    """Valid MacroPlan with multiple sections and assets."""
    plan = MacroPlan(
        global_story=_create_global_story(),
        layering_plan=_create_layering_plan(),
        section_plans=[
            _create_section_plan("intro", "Intro", 0, 10000, EnergyTarget.LOW),
            _create_section_plan("verse1", "Verse 1", 10000, 30000, EnergyTarget.MED),
            _create_section_plan("chorus1", "Chorus 1", 30000, 50000, EnergyTarget.HIGH),
        ],
        asset_requirements=["snowflake_burst.png", "starburst_gold.png"],
    )

    assert len(plan.section_plans) == 3
    assert len(plan.asset_requirements) == 2


def test_macro_plan_empty_section_plans():
    """Empty section_plans rejected."""
    with pytest.raises(ValidationError, match="at least 1 item"):
        MacroPlan(
            global_story=_create_global_story(),
            layering_plan=_create_layering_plan(),
            section_plans=[],
            asset_requirements=[],
        )


def test_macro_plan_no_gaps_validator():
    """Sections with gaps rejected."""
    with pytest.raises(ValidationError, match="Gap detected"):
        MacroPlan(
            global_story=_create_global_story(),
            layering_plan=_create_layering_plan(),
            section_plans=[
                _create_section_plan("intro", "Intro", 0, 10000, EnergyTarget.LOW),
                # Gap from 10000 to 15000
                _create_section_plan("verse1", "Verse 1", 15000, 30000, EnergyTarget.MED),
            ],
            asset_requirements=[],
        )


def test_macro_plan_overlapping_sections():
    """Overlapping sections rejected."""
    with pytest.raises(ValidationError, match="Overlap detected"):
        MacroPlan(
            global_story=_create_global_story(),
            layering_plan=_create_layering_plan(),
            section_plans=[
                _create_section_plan("intro", "Intro", 0, 15000, EnergyTarget.LOW),
                # Overlap: starts at 10000 but previous ends at 15000
                _create_section_plan("verse1", "Verse 1", 10000, 30000, EnergyTarget.MED),
            ],
            asset_requirements=[],
        )


def test_macro_plan_duplicate_section_ids():
    """Duplicate section IDs rejected."""
    with pytest.raises(ValidationError, match="Duplicate section_id"):
        MacroPlan(
            global_story=_create_global_story(),
            layering_plan=_create_layering_plan(),
            section_plans=[
                _create_section_plan("intro", "Intro", 0, 10000, EnergyTarget.LOW),
                _create_section_plan("intro", "Intro Repeated", 10000, 20000, EnergyTarget.LOW),
            ],
            asset_requirements=[],
        )


def test_macro_plan_sections_not_sorted():
    """Sections not sorted by start_ms rejected."""
    with pytest.raises(ValidationError, match="not sorted by start_ms"):
        MacroPlan(
            global_story=_create_global_story(),
            layering_plan=_create_layering_plan(),
            section_plans=[
                _create_section_plan("verse1", "Verse 1", 10000, 30000, EnergyTarget.MED),
                _create_section_plan("intro", "Intro", 0, 10000, EnergyTarget.LOW),  # Out of order
            ],
            asset_requirements=[],
        )


def test_macro_plan_section_invalid_timing():
    """Section with start_ms >= end_ms rejected."""
    # This should fail at MacroSectionPlan level, but let's verify
    with pytest.raises(ValidationError):
        _create_section_plan("bad", "Bad Section", 10000, 10000, EnergyTarget.LOW)


def test_macro_plan_asset_requirements_empty_string():
    """Empty strings in asset_requirements rejected."""
    with pytest.raises(ValidationError, match="at least 1 character"):
        MacroPlan(
            global_story=_create_global_story(),
            layering_plan=_create_layering_plan(),
            section_plans=[
                _create_section_plan("intro", "Intro", 0, 10000, EnergyTarget.LOW),
            ],
            asset_requirements=["valid.png", ""],
        )


def test_macro_plan_serialization():
    """MacroPlan serializes to/from JSON."""
    plan = MacroPlan(
        global_story=_create_global_story(),
        layering_plan=_create_layering_plan(),
        section_plans=[
            _create_section_plan("intro", "Intro", 0, 10000, EnergyTarget.LOW),
            _create_section_plan("verse1", "Verse 1", 10000, 30000, EnergyTarget.MED),
        ],
        asset_requirements=["snowflake.png"],
    )

    # Export to JSON
    json_str = plan.model_dump_json(indent=2)
    assert "Christmas magic" in json_str
    assert "snowflake.png" in json_str

    # Import from JSON
    plan2 = MacroPlan.model_validate_json(json_str)
    assert plan2.global_story.theme == plan.global_story.theme
    assert len(plan2.section_plans) == 2
    assert plan2.asset_requirements == ["snowflake.png"]


def test_macro_plan_start_at_nonzero():
    """First section can start at non-zero time."""
    # This is valid - we only check for gaps/overlaps between sections
    plan = MacroPlan(
        global_story=_create_global_story(),
        layering_plan=_create_layering_plan(),
        section_plans=[
            _create_section_plan("verse1", "Verse 1", 5000, 25000, EnergyTarget.MED),
        ],
        asset_requirements=[],
    )

    assert plan.section_plans[0].section.start_ms == 5000


def test_macro_plan_adjacent_sections_valid():
    """Adjacent sections with no gaps are valid."""
    plan = MacroPlan(
        global_story=_create_global_story(),
        layering_plan=_create_layering_plan(),
        section_plans=[
            _create_section_plan("intro", "Intro", 0, 10000, EnergyTarget.LOW),
            _create_section_plan("verse1", "Verse 1", 10000, 30000, EnergyTarget.MED),
            _create_section_plan("chorus1", "Chorus 1", 30000, 50000, EnergyTarget.HIGH),
        ],
        asset_requirements=[],
    )

    assert len(plan.section_plans) == 3
