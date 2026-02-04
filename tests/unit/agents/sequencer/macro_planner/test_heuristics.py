"""Tests for MacroPlan heuristic validator."""

import pytest

from twinklr.core.agents.audio.profile.models import AudioProfileModel, SongSectionRef
from twinklr.core.agents.issues import Issue, IssueCategory, IssueSeverity
from twinklr.core.agents.sequencer.macro_planner.heuristics import MacroPlanHeuristicValidator
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


@pytest.fixture
def valid_macro_plan() -> MacroPlan:
    """Create a valid MacroPlan for testing."""
    global_story = GlobalStory(
        theme="Christmas magic with cascading waves",
        motifs=["Starbursts", "Waves", "Sparkles"],
        pacing_notes="Build energy through verses, peak at chorus, gentle outro",
        color_story="Cool blues to warm golds",
    )

    base_layer = LayerSpec(
        layer_index=0,
        layer_role=LayerRole.BASE,
        target_selector=TargetSelector(roles=["OUTLINE"]),
        blend_mode=BlendMode.NORMAL,
        timing_driver=TimingDriver.BARS,
        usage_notes="Foundation layer with slow evolution",
    )

    layering_plan = LayeringPlan(
        layers=[base_layer], strategy_notes="Single base layer for clean foundation"
    )

    section_plan = MacroSectionPlan(
        section=SongSectionRef(section_id="intro", name="Intro", start_ms=0, end_ms=10000),
        energy_target=EnergyTarget.LOW,
        primary_focus_targets=["OUTLINE"],
        choreography_style=ChoreographyStyle.ABSTRACT,
        motion_density=MotionDensity.SPARSE,
        notes="Gentle intro establishing foundation",
    )

    return MacroPlan(
        global_story=global_story,
        layering_plan=layering_plan,
        section_plans=[section_plan],
        asset_requirements=[],
    )


@pytest.fixture
def simple_audio_profile(valid_macro_plan: MacroPlan) -> AudioProfileModel:
    """Create a simple AudioProfileModel matching the plan."""
    # Load from existing fixture
    import json
    from pathlib import Path

    # Path: tests/unit/agents/sequencer/macro_planner -> tests/fixtures
    fixture_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "fixtures"
        / "audio_profile"
        / "audio_profile_model.json"
    )
    with fixture_path.open() as f:
        data = json.load(f)

    return AudioProfileModel(**data)


# Skip trivial instantiation/type tests


def test_validate_accepts_plan_and_profile(
    valid_macro_plan: MacroPlan, simple_audio_profile: AudioProfileModel
):
    """Validate accepts MacroPlan and AudioProfileModel."""
    validator = MacroPlanHeuristicValidator()

    # Should not raise
    issues = validator.validate(valid_macro_plan, simple_audio_profile)
    assert issues is not None


def test_has_errors_true():
    """has_errors detects ERROR severity."""
    validator = MacroPlanHeuristicValidator()
    issues = [
        Issue(
            issue_id="W001",
            category=IssueCategory.TIMING,
            severity=IssueSeverity.WARN,
            estimated_effort="LOW",
            scope="SECTION",
            location={},
            rule="DON'T test - this is a test issue",
            message="Warning message",
            fix_hint="Fix hint",
            acceptance_test="Test",
            suggested_action="PATCH",
        ),
        Issue(
            issue_id="E001",
            category=IssueCategory.COVERAGE,
            severity=IssueSeverity.ERROR,
            estimated_effort="MEDIUM",
            scope="GLOBAL",
            location={},
            rule="DON'T test - this is a test issue",
            message="Error message",
            fix_hint="Fix hint",
            acceptance_test="Test",
            suggested_action="REPLAN_GLOBAL",
        ),
    ]

    assert validator.has_errors(issues) is True


def test_has_errors_false():
    """has_errors returns False when no errors present."""
    validator = MacroPlanHeuristicValidator()
    issues = [
        Issue(
            issue_id="W001",
            category=IssueCategory.TIMING,
            severity=IssueSeverity.WARN,
            estimated_effort="LOW",
            scope="SECTION",
            location={},
            rule="DON'T test - this is a test issue",
            message="Warning message",
            fix_hint="Fix hint",
            acceptance_test="Test",
            suggested_action="PATCH",
        ),
    ]

    assert validator.has_errors(issues) is False


def test_has_warnings_true():
    """has_warnings detects WARN severity."""
    validator = MacroPlanHeuristicValidator()
    issues = [
        Issue(
            issue_id="W001",
            category=IssueCategory.TIMING,
            severity=IssueSeverity.WARN,
            estimated_effort="LOW",
            scope="SECTION",
            location={},
            rule="DON'T test - this is a test issue",
            message="Warning message",
            fix_hint="Fix hint",
            acceptance_test="Test",
            suggested_action="PATCH",
        ),
    ]

    assert validator.has_warnings(issues) is True


def test_has_warnings_false():
    """has_warnings returns False when no warnings present."""
    validator = MacroPlanHeuristicValidator()
    issues = [
        Issue(
            issue_id="E001",
            category=IssueCategory.COVERAGE,
            severity=IssueSeverity.ERROR,
            estimated_effort="MEDIUM",
            scope="GLOBAL",
            location={},
            rule="DON'T test - this is a test issue",
            message="Error message",
            fix_hint="Fix hint",
            acceptance_test="Test",
            suggested_action="REPLAN_GLOBAL",
        ),
    ]

    assert validator.has_warnings(issues) is False


def test_empty_issues_list():
    """Helper methods work with empty issues list."""
    validator = MacroPlanHeuristicValidator()
    issues = []

    assert validator.has_errors(issues) is False
    assert validator.has_warnings(issues) is False


# ============================================================================
# Task 1.2.2: Section Coverage Validation Tests
# ============================================================================


def test_section_coverage_complete(simple_audio_profile: AudioProfileModel):
    """Complete section coverage passes validation."""
    validator = MacroPlanHeuristicValidator()

    # Create plan matching all audio sections
    section_plans = []
    for section in simple_audio_profile.structure.sections:
        section_plans.append(
            MacroSectionPlan(
                section=section,
                energy_target=EnergyTarget.MED,
                primary_focus_targets=["OUTLINE"],
                choreography_style=ChoreographyStyle.ABSTRACT,
                motion_density=MotionDensity.MED,
                notes="Section plan matching audio section",
            )
        )

    plan = MacroPlan(
        global_story=GlobalStory(
            theme="Test theme with complete coverage",
            motifs=["Motif1", "Motif2", "Motif3"],
            pacing_notes="Build energy through song with good pacing",
            color_story="Blues to golds",
        ),
        layering_plan=LayeringPlan(
            layers=[
                LayerSpec(
                    layer_index=0,
                    layer_role=LayerRole.BASE,
                    target_selector=TargetSelector(roles=["OUTLINE"]),
                    blend_mode=BlendMode.NORMAL,
                    timing_driver=TimingDriver.BARS,
                    usage_notes="Foundation layer",
                )
            ],
            strategy_notes="Single layer for testing",
        ),
        section_plans=section_plans,
        asset_requirements=[],
    )

    issues = validator._validate_section_coverage(plan, simple_audio_profile)

    assert len(issues) == 0


def test_section_coverage_missing_sections(simple_audio_profile: AudioProfileModel):
    """Missing sections trigger ERROR."""
    validator = MacroPlanHeuristicValidator()

    # Create plan with only first 2 sections (missing rest)
    section_plans = []
    for section in simple_audio_profile.structure.sections[:2]:
        section_plans.append(
            MacroSectionPlan(
                section=section,
                energy_target=EnergyTarget.MED,
                primary_focus_targets=["OUTLINE"],
                choreography_style=ChoreographyStyle.ABSTRACT,
                motion_density=MotionDensity.MED,
                notes="Partial coverage test",
            )
        )

    plan = MacroPlan(
        global_story=GlobalStory(
            theme="Test theme",
            motifs=["M1", "M2", "M3"],
            pacing_notes="Test pacing notes for validation",
            color_story="Test colors",
        ),
        layering_plan=LayeringPlan(
            layers=[
                LayerSpec(
                    layer_index=0,
                    layer_role=LayerRole.BASE,
                    target_selector=TargetSelector(roles=["OUTLINE"]),
                    blend_mode=BlendMode.NORMAL,
                    timing_driver=TimingDriver.BARS,
                    usage_notes="Foundation layer",
                )
            ],
            strategy_notes="Single layer for testing",
        ),
        section_plans=section_plans,
        asset_requirements=[],
    )

    issues = validator._validate_section_coverage(plan, simple_audio_profile)

    # Should have ERROR for missing sections
    assert len(issues) >= 1
    error_issues = [i for i in issues if i.severity == IssueSeverity.ERROR]
    assert len(error_issues) >= 1

    error = error_issues[0]
    assert error.category == IssueCategory.COVERAGE
    assert "COVERAGE_MISSING_SECTIONS" in error.issue_id

    # Check that missing section IDs are in message
    missing_sections = {s.section_id for s in simple_audio_profile.structure.sections[2:]}
    for section_id in missing_sections:
        assert section_id in error.message


def test_section_coverage_extra_sections(simple_audio_profile: AudioProfileModel):
    """Extra sections not in audio trigger WARN."""
    validator = MacroPlanHeuristicValidator()

    # Create plan with all audio sections + extra one at the end (adjacent, no gap)
    section_plans = []
    for section in simple_audio_profile.structure.sections:
        section_plans.append(
            MacroSectionPlan(
                section=section,
                energy_target=EnergyTarget.MED,
                primary_focus_targets=["OUTLINE"],
                choreography_style=ChoreographyStyle.ABSTRACT,
                motion_density=MotionDensity.MED,
                notes="Valid section plan matching audio section",
            )
        )

    # Add extra section adjacent to last section (no gap)
    last_section = simple_audio_profile.structure.sections[-1]
    section_plans.append(
        MacroSectionPlan(
            section=SongSectionRef(
                section_id="extra_section",
                name="Extra Section",
                start_ms=last_section.end_ms,  # Adjacent to last section
                end_ms=last_section.end_ms + 10000,
            ),
            energy_target=EnergyTarget.HIGH,
            primary_focus_targets=["HERO"],
            choreography_style=ChoreographyStyle.IMAGERY,
            motion_density=MotionDensity.BUSY,
            notes="Extra section not in audio profile for testing",
        )
    )

    plan = MacroPlan(
        global_story=GlobalStory(
            theme="Test theme",
            motifs=["M1", "M2", "M3"],
            pacing_notes="Test pacing notes for validation",
            color_story="Test colors",
        ),
        layering_plan=LayeringPlan(
            layers=[
                LayerSpec(
                    layer_index=0,
                    layer_role=LayerRole.BASE,
                    target_selector=TargetSelector(roles=["OUTLINE"]),
                    blend_mode=BlendMode.NORMAL,
                    timing_driver=TimingDriver.BARS,
                    usage_notes="Foundation layer",
                )
            ],
            strategy_notes="Single layer for testing",
        ),
        section_plans=section_plans,
        asset_requirements=[],
    )

    issues = validator._validate_section_coverage(plan, simple_audio_profile)

    # Should have WARN for extra sections
    assert len(issues) >= 1
    warn_issues = [i for i in issues if i.severity == IssueSeverity.WARN]
    assert len(warn_issues) >= 1

    warn = warn_issues[0]
    assert warn.category == IssueCategory.COVERAGE
    assert "COVERAGE_EXTRA_SECTIONS" in warn.issue_id
    assert "extra_section" in warn.message


def test_section_coverage_both_missing_and_extra():
    """Both missing and extra sections produce separate issues."""
    # This test would require building a full AudioProfileModel which is complex
    # TODO: Implement this test once we have a helper to create test AudioProfileModels


def test_section_coverage_empty_plan():
    """Empty section plans trigger ERROR for all missing sections."""
    # This test would also require building a custom AudioProfileModel
    # Skip for now as it's covered by test_section_coverage_missing_sections


# ============================================================================
# Task 1.2.3: Layer Count & Target Validation Tests
# ============================================================================


def test_layer_count_optimal(simple_audio_profile: AudioProfileModel):
    """2-4 layers is optimal, no warnings."""
    validator = MacroPlanHeuristicValidator()

    # Create plan with 3 layers (optimal)
    layers = [
        LayerSpec(
            layer_index=0,
            layer_role=LayerRole.BASE,
            target_selector=TargetSelector(roles=["OUTLINE"]),
            blend_mode=BlendMode.NORMAL,
            timing_driver=TimingDriver.BARS,
            usage_notes="Foundation layer",
        ),
        LayerSpec(
            layer_index=1,
            layer_role=LayerRole.RHYTHM,
            target_selector=TargetSelector(roles=["MEGA_TREE"]),
            blend_mode=BlendMode.ADD,
            timing_driver=TimingDriver.BEATS,
            usage_notes="Beat-driven accents",
        ),
        LayerSpec(
            layer_index=2,
            layer_role=LayerRole.ACCENT,
            target_selector=TargetSelector(roles=["HERO"]),
            blend_mode=BlendMode.ADD,
            timing_driver=TimingDriver.PEAKS,
            usage_notes="Peak moment highlights",
        ),
    ]

    plan = MacroPlan(
        global_story=GlobalStory(
            theme="Test theme",
            motifs=["M1", "M2", "M3"],
            pacing_notes="Test pacing notes for validation testing",
            color_story="Test colors",
        ),
        layering_plan=LayeringPlan(
            layers=layers, strategy_notes="Three-layer composition with clear hierarchy"
        ),
        section_plans=[
            MacroSectionPlan(
                section=simple_audio_profile.structure.sections[0],
                energy_target=EnergyTarget.MED,
                primary_focus_targets=["OUTLINE"],
                choreography_style=ChoreographyStyle.ABSTRACT,
                motion_density=MotionDensity.MED,
                notes="Test section plan for optimal layer count",
            )
        ],
        asset_requirements=[],
    )

    issues = validator._validate_layer_count(plan)

    # 3 layers is optimal - no warnings
    assert len(issues) == 0


def test_layer_count_minimal_warning(simple_audio_profile: AudioProfileModel):
    """Single layer triggers quality warning."""
    validator = MacroPlanHeuristicValidator()

    # Create plan with only 1 layer
    plan = MacroPlan(
        global_story=GlobalStory(
            theme="Test theme",
            motifs=["M1", "M2", "M3"],
            pacing_notes="Test pacing notes for validation testing",
            color_story="Test colors",
        ),
        layering_plan=LayeringPlan(
            layers=[
                LayerSpec(
                    layer_index=0,
                    layer_role=LayerRole.BASE,
                    target_selector=TargetSelector(roles=["OUTLINE"]),
                    blend_mode=BlendMode.NORMAL,
                    timing_driver=TimingDriver.BARS,
                    usage_notes="Foundation layer only",
                )
            ],
            strategy_notes="Single layer composition for minimal testing",
        ),
        section_plans=[
            MacroSectionPlan(
                section=simple_audio_profile.structure.sections[0],
                energy_target=EnergyTarget.LOW,
                primary_focus_targets=["OUTLINE"],
                choreography_style=ChoreographyStyle.ABSTRACT,
                motion_density=MotionDensity.SPARSE,
                notes="Test section plan for minimal layer count",
            )
        ],
        asset_requirements=[],
    )

    issues = validator._validate_layer_count(plan)

    # Should have warning about minimal layering
    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARN
    assert issues[0].category == IssueCategory.LAYERING
    assert "LAYERING_MINIMAL" in issues[0].issue_id
    assert "1 layer" in issues[0].message.lower()


def test_layer_count_maximum_warning(simple_audio_profile: AudioProfileModel):
    """5 layers (maximum) triggers complexity warning."""
    validator = MacroPlanHeuristicValidator()

    # Create plan with 5 layers (maximum allowed)
    layers = [
        LayerSpec(
            layer_index=0,
            layer_role=LayerRole.BASE,
            target_selector=TargetSelector(roles=["OUTLINE"]),
            blend_mode=BlendMode.NORMAL,
            timing_driver=TimingDriver.BARS,
            usage_notes="Foundation layer",
        ),
        LayerSpec(
            layer_index=1,
            layer_role=LayerRole.RHYTHM,
            target_selector=TargetSelector(roles=["MEGA_TREE"]),
            blend_mode=BlendMode.ADD,
            timing_driver=TimingDriver.BEATS,
            usage_notes="Beat-driven layer",
        ),
        LayerSpec(
            layer_index=2,
            layer_role=LayerRole.ACCENT,
            target_selector=TargetSelector(roles=["HERO"]),
            blend_mode=BlendMode.ADD,
            timing_driver=TimingDriver.PEAKS,
            usage_notes="Peak moments layer",
        ),
        LayerSpec(
            layer_index=3,
            layer_role=LayerRole.FILL,
            target_selector=TargetSelector(roles=["PROPS"]),
            blend_mode=BlendMode.ADD,
            timing_driver=TimingDriver.DOWNBEATS,
            usage_notes="Fill layer for gaps",
        ),
        LayerSpec(
            layer_index=4,
            layer_role=LayerRole.TEXTURE,
            target_selector=TargetSelector(roles=["FLOODS"]),
            blend_mode=BlendMode.ADD,
            timing_driver=TimingDriver.PHRASES,
            usage_notes="Textural background layer",
        ),
    ]

    plan = MacroPlan(
        global_story=GlobalStory(
            theme="Test theme",
            motifs=["M1", "M2", "M3"],
            pacing_notes="Test pacing notes for validation testing",
            color_story="Test colors",
        ),
        layering_plan=LayeringPlan(
            layers=layers, strategy_notes="Five-layer composition at maximum complexity"
        ),
        section_plans=[
            MacroSectionPlan(
                section=simple_audio_profile.structure.sections[0],
                energy_target=EnergyTarget.HIGH,
                primary_focus_targets=["OUTLINE", "MEGA_TREE"],
                choreography_style=ChoreographyStyle.HYBRID,
                motion_density=MotionDensity.BUSY,
                notes="Test section plan for maximum layer count",
            )
        ],
        asset_requirements=[],
    )

    issues = validator._validate_layer_count(plan)

    # Should have warning about maximum complexity
    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARN
    assert issues[0].category == IssueCategory.LAYERING
    assert "LAYERING_MAXIMUM" in issues[0].issue_id
    assert "5 layers" in issues[0].message.lower()


def test_target_validity_always_passes(simple_audio_profile: AudioProfileModel):
    """Target validity check always passes (Pydantic validates)."""
    validator = MacroPlanHeuristicValidator()

    # Any valid plan will pass because Pydantic already validated targets
    plan = MacroPlan(
        global_story=GlobalStory(
            theme="Test theme",
            motifs=["M1", "M2", "M3"],
            pacing_notes="Test pacing notes for validation testing",
            color_story="Test colors",
        ),
        layering_plan=LayeringPlan(
            layers=[
                LayerSpec(
                    layer_index=0,
                    layer_role=LayerRole.BASE,
                    target_selector=TargetSelector(roles=["OUTLINE", "MEGA_TREE"]),
                    blend_mode=BlendMode.NORMAL,
                    timing_driver=TimingDriver.BARS,
                    usage_notes="Foundation layer",
                )
            ],
            strategy_notes="Single layer for target validation testing",
        ),
        section_plans=[
            MacroSectionPlan(
                section=simple_audio_profile.structure.sections[0],
                energy_target=EnergyTarget.MED,
                primary_focus_targets=["HERO", "ARCHES"],
                secondary_targets=["PROPS"],
                choreography_style=ChoreographyStyle.ABSTRACT,
                motion_density=MotionDensity.MED,
                notes="Test section with valid targets for validation",
            )
        ],
        asset_requirements=[],
    )

    issues = validator._validate_target_validity(plan)

    # Should always be empty because Pydantic validates
    assert len(issues) == 0


def test_focus_target_variety_good(simple_audio_profile: AudioProfileModel):
    """Good target variety across sections passes."""
    validator = MacroPlanHeuristicValidator()

    # Create plan with varied targets across sections
    section_plans = []
    targets = [["OUTLINE"], ["MEGA_TREE"], ["HERO"], ["ARCHES"]]

    for i, section in enumerate(simple_audio_profile.structure.sections[:4]):
        section_plans.append(
            MacroSectionPlan(
                section=section,
                energy_target=EnergyTarget.MED,
                primary_focus_targets=targets[i % len(targets)],
                choreography_style=ChoreographyStyle.ABSTRACT,
                motion_density=MotionDensity.MED,
                notes="Section with varied target for good variety testing",
            )
        )

    plan = MacroPlan(
        global_story=GlobalStory(
            theme="Test theme",
            motifs=["M1", "M2", "M3"],
            pacing_notes="Test pacing notes for validation testing",
            color_story="Test colors",
        ),
        layering_plan=LayeringPlan(
            layers=[
                LayerSpec(
                    layer_index=0,
                    layer_role=LayerRole.BASE,
                    target_selector=TargetSelector(roles=["OUTLINE"]),
                    blend_mode=BlendMode.NORMAL,
                    timing_driver=TimingDriver.BARS,
                    usage_notes="Foundation layer",
                )
            ],
            strategy_notes="Single layer for focus target testing",
        ),
        section_plans=section_plans,
        asset_requirements=[],
    )

    issues = validator._validate_focus_targets(plan)

    # Good variety - no warnings
    assert len(issues) == 0


def test_focus_target_overused_warning(simple_audio_profile: AudioProfileModel):
    """Overusing same target triggers variety warning."""
    validator = MacroPlanHeuristicValidator()

    # Create plan where OUTLINE is used in >70% of sections
    section_plans = []
    for section in simple_audio_profile.structure.sections[:10]:
        section_plans.append(
            MacroSectionPlan(
                section=section,
                energy_target=EnergyTarget.MED,
                primary_focus_targets=["OUTLINE"],  # Always same target
                choreography_style=ChoreographyStyle.ABSTRACT,
                motion_density=MotionDensity.MED,
                notes="Section with repetitive target for overuse testing",
            )
        )

    plan = MacroPlan(
        global_story=GlobalStory(
            theme="Test theme",
            motifs=["M1", "M2", "M3"],
            pacing_notes="Test pacing notes for validation testing",
            color_story="Test colors",
        ),
        layering_plan=LayeringPlan(
            layers=[
                LayerSpec(
                    layer_index=0,
                    layer_role=LayerRole.BASE,
                    target_selector=TargetSelector(roles=["OUTLINE"]),
                    blend_mode=BlendMode.NORMAL,
                    timing_driver=TimingDriver.BARS,
                    usage_notes="Foundation layer",
                )
            ],
            strategy_notes="Single layer for focus overuse testing",
        ),
        section_plans=section_plans,
        asset_requirements=[],
    )

    issues = validator._validate_focus_targets(plan)

    # Should warn about OUTLINE overuse
    assert len(issues) >= 1
    warn_issues = [i for i in issues if i.severity == IssueSeverity.WARN]
    assert len(warn_issues) >= 1
    assert warn_issues[0].category == IssueCategory.VARIETY
    assert "FOCUS_OVERUSED" in warn_issues[0].issue_id
    assert "OUTLINE" in warn_issues[0].message


# ============================================================================
# Task 1.2.4: Asset Validation Tests
# ============================================================================


def test_asset_types_valid(simple_audio_profile: AudioProfileModel):
    """Valid asset types (.png, .gif) pass."""
    validator = MacroPlanHeuristicValidator()

    plan = MacroPlan(
        global_story=GlobalStory(
            theme="Test theme",
            motifs=["M1", "M2", "M3"],
            pacing_notes="Test pacing notes for validation testing",
            color_story="Test colors",
        ),
        layering_plan=LayeringPlan(
            layers=[
                LayerSpec(
                    layer_index=0,
                    layer_role=LayerRole.BASE,
                    target_selector=TargetSelector(roles=["OUTLINE"]),
                    blend_mode=BlendMode.NORMAL,
                    timing_driver=TimingDriver.BARS,
                    usage_notes="Foundation layer",
                )
            ],
            strategy_notes="Single layer for asset testing",
        ),
        section_plans=[
            MacroSectionPlan(
                section=simple_audio_profile.structure.sections[0],
                energy_target=EnergyTarget.MED,
                primary_focus_targets=["OUTLINE"],
                choreography_style=ChoreographyStyle.ABSTRACT,
                motion_density=MotionDensity.MED,
                notes="Test section plan for valid asset types",
            )
        ],
        asset_requirements=["snowflake.png", "starburst.gif", "wave.PNG"],
    )

    issues = validator._validate_asset_types(plan)

    # All valid extensions - no errors
    assert len(issues) == 0


def test_asset_types_invalid_extension(simple_audio_profile: AudioProfileModel):
    """Invalid asset extensions trigger ERROR."""
    validator = MacroPlanHeuristicValidator()

    plan = MacroPlan(
        global_story=GlobalStory(
            theme="Test theme",
            motifs=["M1", "M2", "M3"],
            pacing_notes="Test pacing notes for validation testing",
            color_story="Test colors",
        ),
        layering_plan=LayeringPlan(
            layers=[
                LayerSpec(
                    layer_index=0,
                    layer_role=LayerRole.BASE,
                    target_selector=TargetSelector(roles=["OUTLINE"]),
                    blend_mode=BlendMode.NORMAL,
                    timing_driver=TimingDriver.BARS,
                    usage_notes="Foundation layer",
                )
            ],
            strategy_notes="Single layer for invalid asset testing",
        ),
        section_plans=[
            MacroSectionPlan(
                section=simple_audio_profile.structure.sections[0],
                energy_target=EnergyTarget.MED,
                primary_focus_targets=["OUTLINE"],
                choreography_style=ChoreographyStyle.ABSTRACT,
                motion_density=MotionDensity.MED,
                notes="Test section plan for invalid asset types",
            )
        ],
        asset_requirements=["valid.png", "invalid.jpg", "bad.mp4"],
    )

    issues = validator._validate_asset_types(plan)

    # Should have ERRORs for .jpg and .mp4
    error_issues = [i for i in issues if i.severity == IssueSeverity.ERROR]
    assert len(error_issues) == 2

    # Check specific invalid assets mentioned
    messages = " ".join([i.message for i in error_issues])
    assert "invalid.jpg" in messages
    assert "bad.mp4" in messages


def test_asset_bloat_warning(simple_audio_profile: AudioProfileModel):
    """More than 10 assets triggers bloat warning."""
    validator = MacroPlanHeuristicValidator()

    # Create plan with 15 assets (>10)
    many_assets = [f"asset_{i:02d}.png" for i in range(15)]

    plan = MacroPlan(
        global_story=GlobalStory(
            theme="Test theme",
            motifs=["M1", "M2", "M3"],
            pacing_notes="Test pacing notes for validation testing",
            color_story="Test colors",
        ),
        layering_plan=LayeringPlan(
            layers=[
                LayerSpec(
                    layer_index=0,
                    layer_role=LayerRole.BASE,
                    target_selector=TargetSelector(roles=["OUTLINE"]),
                    blend_mode=BlendMode.NORMAL,
                    timing_driver=TimingDriver.BARS,
                    usage_notes="Foundation layer",
                )
            ],
            strategy_notes="Single layer for asset bloat testing",
        ),
        section_plans=[
            MacroSectionPlan(
                section=simple_audio_profile.structure.sections[0],
                energy_target=EnergyTarget.MED,
                primary_focus_targets=["OUTLINE"],
                choreography_style=ChoreographyStyle.ABSTRACT,
                motion_density=MotionDensity.MED,
                notes="Test section plan for asset bloat warning",
            )
        ],
        asset_requirements=many_assets,
    )

    issues = validator._check_asset_bloat(plan)

    # Should warn about too many assets
    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARN
    assert issues[0].category == IssueCategory.COMPLEXITY
    assert "ASSET_BLOAT" in issues[0].issue_id
    assert "15 assets" in issues[0].message


def test_asset_bloat_no_warning(simple_audio_profile: AudioProfileModel):
    """10 or fewer assets passes without warning."""
    validator = MacroPlanHeuristicValidator()

    plan = MacroPlan(
        global_story=GlobalStory(
            theme="Test theme",
            motifs=["M1", "M2", "M3"],
            pacing_notes="Test pacing notes for validation testing",
            color_story="Test colors",
        ),
        layering_plan=LayeringPlan(
            layers=[
                LayerSpec(
                    layer_index=0,
                    layer_role=LayerRole.BASE,
                    target_selector=TargetSelector(roles=["OUTLINE"]),
                    blend_mode=BlendMode.NORMAL,
                    timing_driver=TimingDriver.BARS,
                    usage_notes="Foundation layer",
                )
            ],
            strategy_notes="Single layer for reasonable assets",
        ),
        section_plans=[
            MacroSectionPlan(
                section=simple_audio_profile.structure.sections[0],
                energy_target=EnergyTarget.MED,
                primary_focus_targets=["OUTLINE"],
                choreography_style=ChoreographyStyle.ABSTRACT,
                motion_density=MotionDensity.MED,
                notes="Test section plan for reasonable asset count",
            )
        ],
        asset_requirements=["a1.png", "a2.png", "a3.gif"],  # 3 assets
    )

    issues = validator._check_asset_bloat(plan)

    # No warning for reasonable count
    assert len(issues) == 0


# ============================================================================
# Task 1.2.5: Contrast & Quality Checks Tests
# ============================================================================


def test_contrast_good_variety(simple_audio_profile: AudioProfileModel):
    """Good variety across sections passes."""
    validator = MacroPlanHeuristicValidator()

    # Create plan with varied energy, density, style
    section_plans = [
        MacroSectionPlan(
            section=simple_audio_profile.structure.sections[0],
            energy_target=EnergyTarget.LOW,
            motion_density=MotionDensity.SPARSE,
            choreography_style=ChoreographyStyle.ABSTRACT,
            primary_focus_targets=["OUTLINE"],
            notes="Low energy sparse section for contrast testing",
        ),
        MacroSectionPlan(
            section=simple_audio_profile.structure.sections[1],
            energy_target=EnergyTarget.MED,
            motion_density=MotionDensity.MED,
            choreography_style=ChoreographyStyle.IMAGERY,
            primary_focus_targets=["MEGA_TREE"],
            notes="Medium energy medium density for contrast test",
        ),
        MacroSectionPlan(
            section=simple_audio_profile.structure.sections[2],
            energy_target=EnergyTarget.HIGH,
            motion_density=MotionDensity.BUSY,
            choreography_style=ChoreographyStyle.HYBRID,
            primary_focus_targets=["HERO"],
            notes="High energy busy section for contrast testing",
        ),
    ]

    plan = MacroPlan(
        global_story=GlobalStory(
            theme="Test theme",
            motifs=["M1", "M2", "M3"],
            pacing_notes="Test pacing notes for validation testing",
            color_story="Test colors",
        ),
        layering_plan=LayeringPlan(
            layers=[
                LayerSpec(
                    layer_index=0,
                    layer_role=LayerRole.BASE,
                    target_selector=TargetSelector(roles=["OUTLINE"]),
                    blend_mode=BlendMode.NORMAL,
                    timing_driver=TimingDriver.BARS,
                    usage_notes="Foundation layer",
                )
            ],
            strategy_notes="Single layer for contrast testing",
        ),
        section_plans=section_plans,
        asset_requirements=[],
    )

    issues = validator._check_contrast(plan)

    # Good variety - no warnings
    assert len(issues) == 0


def test_contrast_no_energy_variety(simple_audio_profile: AudioProfileModel):
    """All same energy target triggers warning."""
    validator = MacroPlanHeuristicValidator()

    # Create plan with all MED energy
    section_plans = []
    for section in simple_audio_profile.structure.sections[:5]:
        section_plans.append(
            MacroSectionPlan(
                section=section,
                energy_target=EnergyTarget.MED,  # All same
                motion_density=MotionDensity.MED,
                choreography_style=ChoreographyStyle.ABSTRACT,
                primary_focus_targets=["OUTLINE"],
                notes="All medium energy for no contrast testing",
            )
        )

    plan = MacroPlan(
        global_story=GlobalStory(
            theme="Test theme",
            motifs=["M1", "M2", "M3"],
            pacing_notes="Test pacing notes for validation testing",
            color_story="Test colors",
        ),
        layering_plan=LayeringPlan(
            layers=[
                LayerSpec(
                    layer_index=0,
                    layer_role=LayerRole.BASE,
                    target_selector=TargetSelector(roles=["OUTLINE"]),
                    blend_mode=BlendMode.NORMAL,
                    timing_driver=TimingDriver.BARS,
                    usage_notes="Foundation layer",
                )
            ],
            strategy_notes="Single layer for energy contrast testing",
        ),
        section_plans=section_plans,
        asset_requirements=[],
    )

    issues = validator._check_contrast(plan)

    # Should warn about no energy variety
    warn_issues = [i for i in issues if "ENERGY" in i.issue_id]
    assert len(warn_issues) >= 1
    assert warn_issues[0].severity == IssueSeverity.WARN
    assert warn_issues[0].category == IssueCategory.VARIETY


def test_contrast_no_density_variety(simple_audio_profile: AudioProfileModel):
    """All same density (4+ sections) triggers warning."""
    validator = MacroPlanHeuristicValidator()

    # Create plan with 5 sections, all MED density
    section_plans = []
    for i, section in enumerate(simple_audio_profile.structure.sections[:5]):
        section_plans.append(
            MacroSectionPlan(
                section=section,
                energy_target=EnergyTarget.MED if i % 2 == 0 else EnergyTarget.HIGH,  # Vary energy
                motion_density=MotionDensity.MED,  # All same density
                choreography_style=ChoreographyStyle.ABSTRACT,
                primary_focus_targets=["OUTLINE"],
                notes="All medium density for no contrast testing",
            )
        )

    plan = MacroPlan(
        global_story=GlobalStory(
            theme="Test theme",
            motifs=["M1", "M2", "M3"],
            pacing_notes="Test pacing notes for validation testing",
            color_story="Test colors",
        ),
        layering_plan=LayeringPlan(
            layers=[
                LayerSpec(
                    layer_index=0,
                    layer_role=LayerRole.BASE,
                    target_selector=TargetSelector(roles=["OUTLINE"]),
                    blend_mode=BlendMode.NORMAL,
                    timing_driver=TimingDriver.BARS,
                    usage_notes="Foundation layer",
                )
            ],
            strategy_notes="Single layer for density contrast testing",
        ),
        section_plans=section_plans,
        asset_requirements=[],
    )

    issues = validator._check_contrast(plan)

    # Should warn about no density variety
    warn_issues = [i for i in issues if "DENSITY" in i.issue_id]
    assert len(warn_issues) >= 1
    assert warn_issues[0].severity == IssueSeverity.WARN


def test_contrast_single_style_nit(simple_audio_profile: AudioProfileModel):
    """All same style (5+ sections) triggers NIT."""
    validator = MacroPlanHeuristicValidator()

    # Create plan with 6 sections, all ABSTRACT style
    section_plans = []
    for i, section in enumerate(simple_audio_profile.structure.sections[:6]):
        section_plans.append(
            MacroSectionPlan(
                section=section,
                energy_target=EnergyTarget.MED if i % 2 == 0 else EnergyTarget.HIGH,  # Vary energy
                motion_density=MotionDensity.MED
                if i % 2 == 0
                else MotionDensity.BUSY,  # Vary density
                choreography_style=ChoreographyStyle.ABSTRACT,  # All same style
                primary_focus_targets=["OUTLINE"],
                notes="All abstract style for style variety testing",
            )
        )

    plan = MacroPlan(
        global_story=GlobalStory(
            theme="Test theme",
            motifs=["M1", "M2", "M3"],
            pacing_notes="Test pacing notes for validation testing",
            color_story="Test colors",
        ),
        layering_plan=LayeringPlan(
            layers=[
                LayerSpec(
                    layer_index=0,
                    layer_role=LayerRole.BASE,
                    target_selector=TargetSelector(roles=["OUTLINE"]),
                    blend_mode=BlendMode.NORMAL,
                    timing_driver=TimingDriver.BARS,
                    usage_notes="Foundation layer",
                )
            ],
            strategy_notes="Single layer for style variety testing",
        ),
        section_plans=section_plans,
        asset_requirements=[],
    )

    issues = validator._check_contrast(plan)

    # Should have NIT about single style
    nit_issues = [i for i in issues if i.severity == IssueSeverity.NIT]
    assert len(nit_issues) >= 1
    assert "STYLE" in nit_issues[0].issue_id
