"""The `twinklr run` contract after P1P-T11 ⚖.

Two user-facing changes are pinned here. First, `--xsq` is gone: the CLI no longer takes
the user's own sequence, so no run can regenerate and damage it. Second, the fixture
config is the run's real input — the fixture count, the display graph and the approval
threshold all come from configuration instead of the literals `4`, a hardcoded
three-group yard, and `7.0` on a scale the config field does not use.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from tests.golden.harness import RIGS, build_fixture_group
from twinklr.cli.main import build_arg_parser, build_display_graph, build_run_pipeline
from twinklr.core.agents.audio.profile.models import AudioProfileModel
from twinklr.core.agents.sequencer.moving_heads.context import (
    FixtureContext,
    MovingHeadPlanningContext,
)
from twinklr.core.agents.sequencer.moving_heads.orchestrator import build_planner_variables
from twinklr.core.agents.sequencer.moving_heads.stage import MovingHeadStage
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import JobConfig

_AUDIO_PROFILE_FIXTURE = (
    Path(__file__).resolve().parents[2] / "fixtures" / "audio_profile" / "audio_profile_model.json"
)


@pytest.fixture(params=["mh4_minimal", "mh8_reference"])
def rig(request: pytest.FixtureRequest) -> FixtureGroup:
    """The tracked golden rigs, as a CLI user's fixture config would supply them."""
    return build_fixture_group(RIGS[request.param])


def _pipeline_for(rig: FixtureGroup, job_config: JobConfig | None = None):
    return build_run_pipeline(
        fixture_group=rig,
        job_config=job_config or JobConfig(),
        available_templates=["sweep_lr_fan_hold"],
        xsq_output_path=Path("out/song.xsq"),
        fixture_config_path=Path("fixture_config.json"),
    )


def _stage(pipeline) -> MovingHeadStage:
    stage = next(s.stage for s in pipeline.stages if s.id == "moving_heads")
    assert isinstance(stage, MovingHeadStage)
    return stage


# --- ⚖ the CLI surface ------------------------------------------------------------


def test_run_without_xsq_argument() -> None:
    """`twinklr run` parses with no `.xsq` input at all."""
    parser = build_arg_parser()
    args = parser.parse_args(["run", "--audio", "song.mp3", "--config", "job_config.json"])

    assert args.audio == "song.mp3"
    assert not hasattr(args, "xsq")


def test_xsq_argument_is_rejected_not_ignored() -> None:
    """Passing the retired flag fails loudly.

    Accepting and ignoring a flag that used to decide what the output was built from
    would be its own silent-failure class, so the removal is a hard one.
    """
    parser = build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["run", "--audio", "song.mp3", "--xsq", "show.xsq", "--config", "job_config.json"]
        )


def test_cli_has_no_hardcoded_operative_values() -> None:
    """P7-M1: no literal fixture count, threshold or display graph left in the CLI."""
    from twinklr.cli import main

    source = inspect.getsource(main)
    assert "fixture_count=4" not in source
    assert "min_pass_score=7.0" not in source
    for role in ("OUTLINE", "MEGA_TREE"):
        assert role not in source, f"{role} is still hardcoded into the CLI's display graph"


# --- the fixture config as the real input ------------------------------------------


def test_planner_receives_real_fixture_count(rig: FixtureGroup) -> None:
    """P7-M1, asserted at the prompt-context boundary rather than the config layer.

    The count travels config → CLI → planner stage → planning context → the variable
    the planner prompt renders. An 8-head rig is described as 8 heads for the first
    time; before this task every rig was described as 4.
    """
    expected = len(rig.expand_fixtures())
    pipeline, _, _ = _pipeline_for(rig)

    stage = _stage(pipeline)
    assert stage.fixture_count == expected

    variables = build_planner_variables(
        _planning_context(stage.fixture_count),
        iteration=0,
    )
    assert variables["fixture_count"] == expected


def test_display_graph_describes_the_configured_rig(rig: FixtureGroup) -> None:
    """The graph is the rig, not the author's yard."""
    graph, mapping = build_display_graph(rig)

    assert [group.id for group in graph.groups] == ["MOVING_HEADS"]
    assert graph.groups[0].fixture_count == len(rig.expand_fixtures())
    assert mapping.entries[0].group_name == rig.xlights_group


def test_success_threshold_from_config_single_scale() -> None:
    """P7-M1's second half: one configured scale (0-100), one conversion.

    The CLI used to pass `min_pass_score=7.0` on a 0-10 scale straight past
    `agent.success_threshold`, so the documented config field had no effect on the
    shipped path whatever it was set to.
    """
    job_config = JobConfig(project_name="p")
    job_config.agent.success_threshold = 85

    pipeline, _, _ = _pipeline_for(build_fixture_group(RIGS["mh4_minimal"]), job_config)
    assert _stage(pipeline).min_pass_score == pytest.approx(8.5)

    # The field itself is the range validation: 0-100, rejected outside it.
    with pytest.raises(ValueError):
        JobConfig(project_name="p").agent.__class__(success_threshold=101)


def test_empty_rig_is_reported_not_crashed() -> None:
    """A fixture config with no fixtures fails with something the user can act on."""
    with pytest.raises(ValueError, match="declares no fixtures"):
        build_display_graph(FixtureGroup(group_id="MOVING_HEADS"))


def test_render_stage_takes_no_template(rig: FixtureGroup) -> None:
    """The pipeline's render stage has no template input to be handed."""
    pipeline, _, _ = _pipeline_for(rig)
    render_stage = next(s.stage for s in pipeline.stages if s.id == "render")

    assert not hasattr(render_stage, "xsq_template_path")


def _planning_context(fixture_count: int) -> MovingHeadPlanningContext:
    """A planning context whose only variable is the fixture count under test."""
    profile = AudioProfileModel(**json.loads(_AUDIO_PROFILE_FIXTURE.read_text(encoding="utf-8")))
    return MovingHeadPlanningContext(
        audio_profile=profile,
        fixtures=FixtureContext(count=fixture_count),
        available_templates=["sweep_lr_fan_hold"],
    )
