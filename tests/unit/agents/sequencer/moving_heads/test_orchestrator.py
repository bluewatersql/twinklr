"""Tests for V2 MovingHead orchestrator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from twinklr.core.agents.audio.profile.models import (
    AssetUsage,
    AudioProfileModel,
    Contrast,
    CreativeGuidance,
    EnergyPoint,
    EnergyProfile,
    LyricProfile,
    MacroEnergy,
    MotionDensity,
    PlannerHints,
    SectionEnergyProfile,
    SongIdentity,
    SongSectionRef,
    Structure,
)
from twinklr.core.agents.sequencer.moving_heads.context import (
    FixtureContext,
    MovingHeadPlanningContext,
)
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    PlanSection,
)
from twinklr.core.agents.sequencer.moving_heads.orchestrator import (
    MovingHeadPlannerOrchestrator,
    build_judge_variables,
    build_planner_variables,
)


def create_test_audio_profile() -> AudioProfileModel:
    """Create a minimal audio profile for testing."""
    sections = [
        SongSectionRef(section_id="intro", name="intro", start_ms=0, end_ms=15000),
        SongSectionRef(section_id="verse_1", name="verse", start_ms=15000, end_ms=45000),
        SongSectionRef(section_id="chorus_1", name="chorus", start_ms=45000, end_ms=75000),
        SongSectionRef(section_id="outro", name="outro", start_ms=75000, end_ms=90000),
    ]

    song_identity = SongIdentity(
        title="Test Song",
        artist="Test Artist",
        duration_ms=90000,
        bpm=120.0,
        time_signature="4/4",
    )

    structure = Structure(sections=sections, structure_confidence=0.9)

    section_profiles = [
        SectionEnergyProfile(
            section_id=sec.section_id,
            start_ms=sec.start_ms,
            end_ms=sec.end_ms,
            energy_curve=[
                EnergyPoint(t_ms=sec.start_ms, energy_0_1=0.5),
                EnergyPoint(t_ms=(sec.start_ms + sec.end_ms) // 2, energy_0_1=0.6),
                EnergyPoint(t_ms=sec.end_ms - 1, energy_0_1=0.5),
            ],
            mean_energy=0.55,
            peak_energy=0.6,
        )
        for sec in sections
    ]

    energy_profile = EnergyProfile(
        macro_energy=MacroEnergy.MED,
        section_profiles=section_profiles,
        peaks=[],
        overall_mean=0.5,
        energy_confidence=0.8,
    )

    lyric_profile = LyricProfile(
        has_plain_lyrics=False,
        has_timed_words=False,
        has_phonemes=False,
        lyric_confidence=0.0,
        phoneme_confidence=0.0,
    )

    creative_guidance = CreativeGuidance(
        recommended_layer_count=2,
        recommended_contrast=Contrast.MED,
        recommended_motion_density=MotionDensity.MED,
        recommended_asset_usage=AssetUsage.SPARSE,
    )

    return AudioProfileModel(
        song_identity=song_identity,
        structure=structure,
        energy_profile=energy_profile,
        lyric_profile=lyric_profile,
        creative_guidance=creative_guidance,
        planner_hints=PlannerHints(),
    )


@pytest.fixture
def planning_context() -> MovingHeadPlanningContext:
    """Create a test planning context."""
    return MovingHeadPlanningContext(
        audio_profile=create_test_audio_profile(),
        fixtures=FixtureContext(count=4, groups=[{"id": "front", "fixtures": [1, 2]}]),
        available_templates=["sweep_lr_fan_pulse", "circle_fan_hold", "pendulum_chevron_breathe"],
    )


@pytest.fixture
def valid_plan() -> ChoreographyPlan:
    """Create a valid choreography plan."""
    return ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=8,
                template_id="sweep_lr_fan_pulse",
            ),
            PlanSection(
                section_name="verse_1",
                start_bar=9,
                end_bar=24,
                template_id="circle_fan_hold",
            ),
            PlanSection(
                section_name="chorus_1",
                start_bar=25,
                end_bar=40,
                template_id="pendulum_chevron_breathe",
            ),
        ],
        overall_strategy="Build energy progressively",
    )


class TestBuildPlannerVariables:
    """Tests for build_planner_variables function."""

    def test_initial_iteration(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test variables for initial iteration (iteration=0)."""
        variables = build_planner_variables(planning_context, iteration=0)

        # Should have all required fields
        assert variables["iteration"] == 0
        assert variables["song_title"] == "Test Song"
        assert variables["song_artist"] == "Test Artist"
        assert variables["tempo"] == 120.0
        assert variables["time_signature"] == "4/4"
        assert variables["fixture_count"] == 4
        assert len(variables["available_templates"]) == 3
        assert len(variables["sections"]) == 4

        # Should have audio_profile for initial iteration
        assert variables["audio_profile"] is not None

        # Should not have feedback for initial iteration
        assert variables["feedback"] is None

    def test_refinement_iteration(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test variables for refinement iteration (iteration>0)."""
        variables = build_planner_variables(
            planning_context,
            iteration=1,
            feedback="Fix timing issues",
            revision_focus=["TIMING: Fix overlapping sections"],
        )

        assert variables["iteration"] == 1
        assert variables["feedback"] == "Fix timing issues"
        assert variables["revision_focus"] == ["TIMING: Fix overlapping sections"]

        # Should NOT have audio_profile for refinement (token optimization)
        assert variables["audio_profile"] is None

    def test_sections_have_bar_positions(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test sections include calculated bar positions."""
        variables = build_planner_variables(planning_context, iteration=0)

        sections = variables["sections"]
        assert all("start_bar" in s for s in sections)
        assert all("end_bar" in s for s in sections)


class TestBuildJudgeVariables:
    """Tests for build_judge_variables function."""

    def test_basic_judge_variables(
        self, planning_context: MovingHeadPlanningContext, valid_plan: ChoreographyPlan
    ) -> None:
        """Test basic judge variable building."""
        variables = build_judge_variables(
            context=planning_context,
            plan=valid_plan,
            iteration=0,
        )

        assert "plan" in variables
        assert variables["iteration"] == 0
        assert len(variables["sections"]) == 4
        assert variables["total_bars"] > 0
        assert variables["tempo"] == 120.0
        assert len(variables["available_templates"]) == 3

    def test_judge_variables_with_history(
        self, planning_context: MovingHeadPlanningContext, valid_plan: ChoreographyPlan
    ) -> None:
        """Test judge variables with iteration history."""
        variables = build_judge_variables(
            context=planning_context,
            plan=valid_plan,
            iteration=2,
            previous_feedback=["Fix variety", "Add energy"],
            previous_issues=[
                {"issue_id": "VARIETY_LOW", "severity": "WARN", "message": "Low variety"}
            ],
        )

        assert variables["iteration"] == 2
        assert len(variables["previous_feedback"]) == 2
        assert len(variables["previous_issues"]) == 1

    def test_plan_serialized_as_dict(
        self, planning_context: MovingHeadPlanningContext, valid_plan: ChoreographyPlan
    ) -> None:
        """Test plan is serialized as dict for JSON templates."""
        variables = build_judge_variables(
            context=planning_context,
            plan=valid_plan,
            iteration=0,
        )

        # Plan should be dict, not Pydantic model
        assert isinstance(variables["plan"], dict)
        assert "sections" in variables["plan"]


class TestMovingHeadPlannerOrchestrator:
    """Tests for MovingHeadPlannerOrchestrator."""

    @pytest.fixture
    def mock_provider(self) -> MagicMock:
        """Create mock LLM provider."""
        return MagicMock()

    def test_orchestrator_init(self, mock_provider: MagicMock) -> None:
        """Test orchestrator initialization."""
        orchestrator = MovingHeadPlannerOrchestrator(
            provider=mock_provider,
            max_iterations=5,
            min_pass_score=6.5,
        )

        assert orchestrator.provider == mock_provider
        assert orchestrator.controller.config.max_iterations == 5
        assert orchestrator.controller.config.approval_score_threshold == 6.5

    def test_orchestrator_uses_default_specs(self, mock_provider: MagicMock) -> None:
        """Test orchestrator uses default specs when not provided."""
        orchestrator = MovingHeadPlannerOrchestrator(provider=mock_provider)

        assert orchestrator.planner_spec is not None
        assert orchestrator.judge_spec is not None
        assert orchestrator.planner_spec.name == "mh_planner"
        assert orchestrator.judge_spec.name == "mh_judge"

    @pytest.mark.asyncio
    async def test_get_cache_key(
        self, mock_provider: MagicMock, planning_context: MovingHeadPlanningContext
    ) -> None:
        """Test cache key generation."""
        orchestrator = MovingHeadPlannerOrchestrator(provider=mock_provider)

        key1 = await orchestrator.get_cache_key(planning_context)
        key2 = await orchestrator.get_cache_key(planning_context)

        # Same context should produce same key
        assert key1 == key2
        assert len(key1) == 64  # SHA256 hex digest

    @pytest.mark.asyncio
    async def test_run_validates_empty_templates(self, mock_provider: MagicMock) -> None:
        """Test run validates that templates are not empty."""
        orchestrator = MovingHeadPlannerOrchestrator(provider=mock_provider)

        # Empty templates should fail
        context = MovingHeadPlanningContext(
            audio_profile=create_test_audio_profile(),
            fixtures=FixtureContext(count=4, groups=[]),
            available_templates=[],  # Empty templates
        )

        with pytest.raises(ValueError, match="At least one template"):
            await orchestrator.run(context)

    def test_fixture_context_validates_count(self) -> None:
        """Test FixtureContext validates count >= 1 at Pydantic level."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            FixtureContext(count=0, groups=[])


class TestOrchestratorIntegration:
    """Integration tests for V2 orchestrator (mocked LLM calls)."""

    @pytest.fixture
    def mock_controller_run(self):
        """Mock the controller.run method."""
        from twinklr.core.agents.shared.judge.controller import (
            IterationContext,
            IterationResult,
        )
        from twinklr.core.agents.shared.judge.models import (
            IterationState,
            JudgeVerdict,
            VerdictStatus,
        )

        async def mock_run(*args, **kwargs):
            # Create successful result
            context = IterationContext()
            context.current_iteration = 1
            context.update_state(IterationState.COMPLETE)
            context.final_verdict = JudgeVerdict(
                status=VerdictStatus.APPROVE,
                score=8.0,
                confidence=0.9,
                strengths=["Good variety", "Musical alignment"],
                issues=[],
                overall_assessment="Plan approved",
                feedback_for_planner="No changes needed",
                iteration=1,
            )

            plan = ChoreographyPlan(
                sections=[
                    PlanSection(
                        section_name="intro",
                        start_bar=1,
                        end_bar=8,
                        template_id="sweep_lr_fan_pulse",
                    )
                ],
                overall_strategy="Test",
            )

            return IterationResult(
                success=True,
                plan=plan,
                context=context,
            )

        return mock_run

    @pytest.mark.asyncio
    async def test_successful_orchestration(
        self,
        planning_context: MovingHeadPlanningContext,
        mock_controller_run,
    ) -> None:
        """Test successful orchestration with mocked controller."""
        mock_provider = MagicMock()

        orchestrator = MovingHeadPlannerOrchestrator(provider=mock_provider)

        # Mock the controller.run method
        with patch.object(
            orchestrator.controller, "run", new=AsyncMock(side_effect=mock_controller_run)
        ):
            result = await orchestrator.run(planning_context)

        assert result.success is True
        assert result.plan is not None
        assert len(result.plan.sections) > 0
