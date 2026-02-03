"""Tests for MovingHeadStage."""

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
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    PlanSection,
)
from twinklr.core.agents.sequencer.moving_heads.stage import MovingHeadStage


def create_test_audio_profile() -> AudioProfileModel:
    """Create a minimal audio profile for testing."""
    sections = [
        SongSectionRef(section_id="intro", name="intro", start_ms=0, end_ms=15000),
        SongSectionRef(section_id="verse_1", name="verse", start_ms=15000, end_ms=45000),
        SongSectionRef(section_id="chorus_1", name="chorus", start_ms=45000, end_ms=75000),
    ]

    song_identity = SongIdentity(
        title="Test Song",
        artist="Test Artist",
        duration_ms=75000,
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
            mean_energy=0.5,
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


def create_mock_beat_grid() -> MagicMock:
    """Create a mock BeatGrid for testing."""
    beat_grid = MagicMock()
    beat_grid.tempo_bpm = 120.0
    beat_grid.beats_per_bar = 4
    beat_grid.total_bars = 38
    beat_grid.ms_per_bar = 2000.0
    beat_grid.duration_ms = 75000.0
    return beat_grid


class TestMovingHeadStageInit:
    """Tests for MovingHeadStage initialization."""

    def test_init_with_required_params(self) -> None:
        """Test initialization with required parameters."""
        stage = MovingHeadStage(
            fixture_count=4,
            available_templates=["sweep_lr_fan_pulse", "circle_fan_hold"],
        )

        assert stage.fixture_count == 4
        assert len(stage.available_templates) == 2
        assert stage.fixture_groups == []
        assert stage.max_iterations == 3
        assert stage.min_pass_score == 7.0

    def test_init_with_all_params(self) -> None:
        """Test initialization with all parameters."""
        stage = MovingHeadStage(
            fixture_count=8,
            available_templates=["template1", "template2", "template3"],
            fixture_groups=[{"id": "front", "fixtures": [1, 2]}],
            max_iterations=5,
            min_pass_score=6.0,
        )

        assert stage.fixture_count == 8
        assert len(stage.available_templates) == 3
        assert len(stage.fixture_groups) == 1
        assert stage.max_iterations == 5
        assert stage.min_pass_score == 6.0

    def test_name_property(self) -> None:
        """Test stage name property."""
        stage = MovingHeadStage(fixture_count=4, available_templates=["template1"])
        assert stage.name == "moving_head_planner"


class TestMovingHeadStageExecute:
    """Tests for MovingHeadStage.execute method."""

    @pytest.fixture
    def stage(self) -> MovingHeadStage:
        """Create a test stage."""
        return MovingHeadStage(
            fixture_count=4,
            available_templates=["sweep_lr_fan_pulse", "circle_fan_hold"],
        )

    @pytest.fixture
    def mock_context(self) -> MagicMock:
        """Create a mock pipeline context."""
        context = MagicMock()
        context.provider = MagicMock()
        context.llm_logger = MagicMock()
        context.job_config = MagicMock()
        context.job_config.agent.max_iterations = 3
        context.set_state = MagicMock()
        context.add_metric = MagicMock()
        return context

    @pytest.fixture
    def valid_input(self) -> dict:
        """Create valid input for the stage.

        Per V2 spec, inputs=["audio", "profile", "lyrics", "macro"]:
        - audio: SongBundle (from AudioAnalysisStage, for BeatGrid)
        - profile: AudioProfileModel (from AudioProfileStage)
        - lyrics: LyricContextModel | None (from LyricsStage, optional)
        - macro: list[MacroSectionPlan] | None (from MacroPlannerStage)
        """
        # Create mock audio bundle with features for BeatGrid
        audio_bundle = MagicMock()
        audio_bundle.features = {
            "rhythm": {"tempo": 120.0},
            "sr": 22050,
            "hop_length": 512,
            "duration_s": 180.0,
        }
        return {
            "audio": audio_bundle,
            "profile": create_test_audio_profile(),
            "lyrics": None,  # Optional, may be None
            "macro": None,  # Optional for now (stubbed)
        }

    @pytest.mark.asyncio
    async def test_execute_missing_audio(
        self, stage: MovingHeadStage, mock_context: MagicMock
    ) -> None:
        """Test execute fails with missing audio bundle."""
        result = await stage.execute(
            {"profile": create_test_audio_profile(), "lyrics": None, "macro": None},
            mock_context,
        )

        assert result.success is False
        assert "Missing required input" in (result.error or "")

    @pytest.mark.asyncio
    async def test_execute_missing_profile(
        self, stage: MovingHeadStage, mock_context: MagicMock
    ) -> None:
        """Test execute fails with missing profile."""
        audio_bundle = MagicMock()
        audio_bundle.features = {"rhythm": {"tempo": 120.0}}
        result = await stage.execute(
            {"audio": audio_bundle, "lyrics": None, "macro": None}, mock_context
        )

        assert result.success is False
        assert "Missing required input" in (result.error or "")

    @pytest.mark.asyncio
    async def test_execute_stores_planning_context(
        self, stage: MovingHeadStage, mock_context: MagicMock, valid_input: dict
    ) -> None:
        """Test execute stores planning context in state."""
        from twinklr.core.agents.shared.judge.controller import (
            IterationContext,
            IterationResult,
        )
        from twinklr.core.agents.shared.judge.models import (
            IterationState,
            JudgeVerdict,
            VerdictStatus,
        )

        # Mock the execute_step to return a successful result
        mock_result = IterationResult(
            success=True,
            plan=ChoreographyPlan(
                sections=[
                    PlanSection(
                        section_name="intro",
                        start_bar=1,
                        end_bar=8,
                        template_id="sweep_lr_fan_pulse",
                    )
                ],
                overall_strategy="Test",
            ),
            context=IterationContext(
                current_iteration=1,
                state=IterationState.COMPLETE,
                total_tokens_used=1000,
            ),
        )
        mock_result.context.final_verdict = JudgeVerdict(
            status=VerdictStatus.APPROVE,
            score=8.0,
            confidence=0.9,
            strengths=["Good"],
            issues=[],
            overall_assessment="Approved",
            feedback_for_planner="",
            iteration=1,
        )

        with patch(
            "twinklr.core.pipeline.execution.execute_step",
            new=AsyncMock(return_value=MagicMock(success=True, output=mock_result.plan)),
        ):
            await stage.execute(valid_input, mock_context)

        # Verify planning context was stored
        calls = list(mock_context.set_state.call_args_list)
        state_keys = [call[0][0] for call in calls]
        assert "mh_planning_context" in state_keys


class TestMovingHeadStageStateHandler:
    """Tests for MovingHeadStage state handler."""

    @pytest.fixture
    def stage(self) -> MovingHeadStage:
        """Create a test stage."""
        return MovingHeadStage(fixture_count=4, available_templates=["template1"])

    def test_handle_state_with_model(self, stage: MovingHeadStage) -> None:
        """Test state handler with Pydantic model result."""
        from twinklr.core.agents.shared.judge.controller import (
            IterationContext,
            IterationResult,
        )

        mock_context = MagicMock()
        plan = ChoreographyPlan(
            sections=[
                PlanSection(
                    section_name="intro",
                    start_bar=1,
                    end_bar=8,
                    template_id="template1",
                )
            ],
            overall_strategy="Test",
        )
        result = IterationResult(
            success=True,
            plan=plan,
            context=IterationContext(),
        )

        stage._handle_state(result, mock_context)

        mock_context.set_state.assert_called_with("choreography_plan", plan)

    def test_handle_state_with_dict(self, stage: MovingHeadStage) -> None:
        """Test state handler with dict result (from cache)."""
        mock_context = MagicMock()
        result = {
            "success": True,
            "plan": {"sections": [], "overall_strategy": "Test"},
            "context": {},
        }

        stage._handle_state(result, mock_context)

        mock_context.set_state.assert_called_once()


class TestMovingHeadStageMetricsHandler:
    """Tests for MovingHeadStage metrics handler."""

    @pytest.fixture
    def stage(self) -> MovingHeadStage:
        """Create a test stage."""
        return MovingHeadStage(fixture_count=4, available_templates=["template1"])

    def test_handle_metrics_with_model(self, stage: MovingHeadStage) -> None:
        """Test metrics handler with Pydantic model result."""
        from twinklr.core.agents.shared.judge.controller import (
            IterationContext,
            IterationResult,
        )
        from twinklr.core.agents.shared.judge.models import (
            IterationState,
            JudgeVerdict,
            VerdictStatus,
        )

        mock_context = MagicMock()
        plan = ChoreographyPlan(
            sections=[
                PlanSection(
                    section_name="intro",
                    start_bar=1,
                    end_bar=8,
                    template_id="template1",
                ),
                PlanSection(
                    section_name="verse",
                    start_bar=9,
                    end_bar=24,
                    template_id="template1",
                ),
            ],
            overall_strategy="Test",
        )
        iter_ctx = IterationContext(
            current_iteration=2,
            state=IterationState.COMPLETE,
            total_tokens_used=1500,
        )
        iter_ctx.final_verdict = JudgeVerdict(
            status=VerdictStatus.APPROVE,
            score=8.5,
            confidence=0.9,
            strengths=[],
            issues=[],
            overall_assessment="Good",
            feedback_for_planner="",
            iteration=2,
        )
        result = IterationResult(
            success=True,
            plan=plan,
            context=iter_ctx,
        )

        stage._handle_metrics(result, mock_context)

        # Check metrics were added
        metric_calls = {call[0][0]: call[0][1] for call in mock_context.add_metric.call_args_list}
        assert metric_calls.get("mh_section_count") == 2
        assert metric_calls.get("mh_iterations") == 2
        assert metric_calls.get("mh_tokens") == 1500
        assert metric_calls.get("mh_score") == 8.5

    def test_handle_metrics_with_dict(self, stage: MovingHeadStage) -> None:
        """Test metrics handler with dict result (from cache)."""
        mock_context = MagicMock()
        result = {
            "success": True,
            "plan": {
                "sections": [{"section_name": "intro", "template_id": "t1"}],
                "overall_strategy": "Test",
            },
            "context": {
                "current_iteration": 1,
                "total_tokens_used": 500,
                "final_verdict": {"score": 7.5},
            },
        }

        stage._handle_metrics(result, mock_context)

        metric_calls = {call[0][0]: call[0][1] for call in mock_context.add_metric.call_args_list}
        assert metric_calls.get("mh_section_count") == 1
        assert metric_calls.get("mh_iterations") == 1
        assert metric_calls.get("mh_tokens") == 500
        assert metric_calls.get("mh_score") == 7.5
