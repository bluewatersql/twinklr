"""Offline deterministic full display-definition run and first XSQ golden."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from twinklr.cli.display_cmd import export_display_artifacts
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.pipeline import PipelineExecutor
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.pipeline.definition import PipelineDefinition
from twinklr.core.pipeline.display_stages import DisplayRenderStage
from twinklr.core.pipeline.display_wiring import prepare_display_pipeline
from twinklr.core.pipeline.result import success_result
from twinklr.core.sequencer.planning.group_plan import (
    LanePlan,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.planning.models import PaletteRef
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationPlan,
    GroupPlacement,
    PlanTarget,
)
from twinklr.core.sequencer.theming import ThemeRef
from twinklr.core.sequencer.theming.enums import ThemeScope
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    EffectDuration,
    IntensityLevel,
    LaneKind,
    PlanningTimeRef,
)
from twinklr.core.sequencer.vocabulary.choreography import TargetType

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
GOLDEN = REPO_ROOT / "tests" / "golden" / "fixtures" / "display_pipeline_first.xsq"


class _FixtureStage:
    """Deterministic, $0 replacement for one provider-owned pipeline boundary."""

    def __init__(self, name: str, output: object) -> None:
        self.name = name
        self._output = output

    async def execute(self, input: object, context: PipelineContext):
        return success_result(self._output, stage_name=self.name)


class _PassInputStage:
    def __init__(self, name: str) -> None:
        self.name = name

    async def execute(self, input: object, context: PipelineContext):
        return success_result(input, stage_name=self.name)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_display_pipeline_deterministic_fixture_matches_first_golden(tmp_path: Path) -> None:
    """No provider/audio/xLights process is used; the deterministic plan is the fake provider."""
    wiring = prepare_display_pipeline(
        layout_path=FIXTURES / "display_layout_a.xml",
        job_config=JobConfig(),
        catalog_dir=REPO_ROOT / "catalog" / "templates",
        song_name="fixture_song",
    )
    section_plan = SectionCoordinationPlan(
        section_id="intro_1",
        theme=ThemeRef(
            theme_id="theme.holiday.traditional",
            scope=ThemeScope.SECTION,
        ),
        palette=PaletteRef(palette_id="core.christmas_traditional"),
        lane_plans=[
            LanePlan(
                lane=LaneKind.BASE,
                target_roles=["YARD_ARCHES"],
                coordination_plans=[
                    CoordinationPlan(
                        coordination_mode=CoordinationMode.UNIFIED,
                        targets=[PlanTarget(type=TargetType.GROUP, id="YARD_ARCHES")],
                        placements=[
                            GroupPlacement(
                                placement_id="fixture_wash",
                                target=PlanTarget(
                                    type=TargetType.GROUP,
                                    id="YARD_ARCHES",
                                ),
                                template_id="gtpl_base_wash_split",
                                start=PlanningTimeRef(bar=1, beat=2),
                                duration=EffectDuration.PHRASE,
                                intensity=IntensityLevel.MED,
                            )
                        ],
                    )
                ],
            )
        ],
    )
    features = {
        "tempo_bpm": 120.0,
        "beats_s": [
            0.0,
            0.52,
            1.01,
            1.55,
            2.08,
            2.6,
            3.07,
            3.55,
            4.04,
            4.61,
            5.13,
            5.67,
            6.22,
            6.76,
            7.18,
            7.66,
            8.1,
        ],
        "bars_s": [0.0, 2.08, 4.04, 6.22, 8.1],
        "assumptions": {"beats_per_bar": 4},
    }
    replacements = {
        "profile": _FixtureStage("fixture_profile", object()),
        "macro": _FixtureStage("fixture_macro", [object()]),
        "groups": _FixtureStage("fixture_groups", section_plan),
        "holistic": _PassInputStage("fixture_holistic"),
        "holistic_corrector": _PassInputStage("fixture_holistic_corrector"),
    }
    fixture_pipeline = PipelineDefinition(
        name="display_full_definition_with_fake_provider_boundaries",
        stages=[
            replace(definition, stage=replacements[definition.id])
            if definition.id in replacements
            else definition
            for definition in wiring.pipeline.stages
        ],
    )
    assert [stage.id for stage in fixture_pipeline.stages] == [
        stage.id for stage in wiring.pipeline.stages
    ]
    assert isinstance(fixture_pipeline.get_stage("display_render").stage, DisplayRenderStage)

    bundle = SimpleNamespace(
        features=features,
        timing=SimpleNamespace(duration_ms=8000),
        lyrics=None,
        audio_path="fixture_song.wav",
    )
    analyzer = MagicMock()
    analyzer.analyze = AsyncMock(return_value=bundle)
    analyzer.aclose = AsyncMock()

    async def run_once(directory: Path):
        session = MagicMock()
        session.app_config = AppConfig()
        session.job_config = JobConfig()
        context = PipelineContext(session=session)
        with patch("twinklr.core.audio.analyzer.AudioAnalyzer", return_value=analyzer):
            result = await PipelineExecutor().execute(fixture_pipeline, "fixture_song.wav", context)
        assert result.success
        grid = context.get_state("beat_grid")
        assert isinstance(grid, BeatGrid)
        assert grid.beat_boundaries[1] == 520.0
        render_output = result.outputs["display_render"]
        event = render_output["render_result"].render_plan.groups[0].layers[0].events[0]
        assert event.start_ms == 520
        assert event.end_ms == 6520
        return export_display_artifacts(
            render_output,
            artifact_dir=directory,
            song_name="fixture_song",
        )

    first_xsq, first_trace = await run_once(tmp_path / "first")
    second_xsq, second_trace = await run_once(tmp_path / "second")
    assert first_xsq.read_bytes() == second_xsq.read_bytes()
    assert first_trace.read_bytes() == second_trace.read_bytes()
    assert (
        first_xsq.read_text(encoding="utf-8").rstrip()
        == GOLDEN.read_text(encoding="utf-8").rstrip()
    )
