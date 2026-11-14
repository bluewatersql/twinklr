"""The evaluation re-render takes no user sequence (P1P-T11).

`rerender_plan` was the third export-path caller and the easiest to miss: it passed the
user's `.xsq` into `RenderingPipeline` as a template and pointed the output at
`temp_eval.xsq` next to their audio, so generating a report both read and wrote sequence
files it had no need to touch.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests.golden.harness import RIGS, build_fixture_group, build_plan
from twinklr.core.config.models import MHRenderPolicy
from twinklr.core.config.render_policy import UnsupportedRenderModeError
from twinklr.core.reporting.evaluation.cli import eval_report_cli
from twinklr.core.reporting.evaluation.collect import checkpoint_render_policy
from twinklr.core.reporting.evaluation.generator import generate_evaluation_report
from twinklr.core.reporting.evaluation.rerender import rerender_plan


def test_rerender_uses_fresh_path() -> None:
    """No sequence input reaches the re-render, at any layer of the eval stack."""
    for func in (rerender_plan, generate_evaluation_report):
        parameters = inspect.signature(func).parameters
        assert "xsq_path" not in parameters, f"{func.__name__} still takes a sequence"

    assert "template_xsq" not in inspect.getsource(rerender_plan)


def test_rerender_writes_no_sequence_file() -> None:
    """The pipeline is built with no output path, so nothing is exported.

    `tests/unit/reporting/evaluation/test_end_to_end.py` asserts the same thing from the
    outside, by running a real report and finding no `.xsq` anywhere beneath it.
    """
    assert "output_path=None" in inspect.getsource(rerender_plan)


def test_eval_report_cli_has_no_xsq_option() -> None:
    """The retired input is gone from the command the user types too."""
    option_names = {name for param in eval_report_cli.params for name in param.opts}
    assert "--xsq" not in option_names
    assert {"--checkpoint", "--audio", "--fixture", "--out"} <= option_names


@pytest.mark.asyncio
async def test_rerender_refuses_a_physical_policy_before_reading_inputs(tmp_path: Path) -> None:
    """A plan from a physical job is never re-rendered as legacy: the report analyzes
    legacy DMX curves, so the mismatch is refused before any file or audio is read."""
    with (
        patch("twinklr.core.audio.analyzer.AudioAnalyzer") as analyzer,
        pytest.raises(UnsupportedRenderModeError, match=r"eval-report.*physical_v2"),
    ):
        await rerender_plan(
            plan=build_plan(),
            audio_path=tmp_path / "missing.wav",
            fixture_config_path=tmp_path / "missing.json",
            render_policy=MHRenderPolicy(mode="physical_v2"),
        )
    analyzer.assert_not_called()


@pytest.mark.asyncio
async def test_rerender_passes_the_given_policy_to_the_pipeline(tmp_path: Path) -> None:
    """The policy is a required input and is what the re-render's pipeline runs under."""
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"audio")
    fixtures = tmp_path / "fixtures.json"
    fixtures.write_text(build_fixture_group(RIGS["mh4_minimal"]).model_dump_json())
    policy = MHRenderPolicy()

    class FakeAnalyzer:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> FakeAnalyzer:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def analyze(self, path: str) -> SimpleNamespace:
            return SimpleNamespace(features={})

    with (
        patch("twinklr.core.audio.analyzer.AudioAnalyzer", FakeAnalyzer),
        patch("twinklr.core.reporting.evaluation.rerender.BeatGrid"),
        patch("twinklr.core.reporting.evaluation.rerender.RenderingPipeline") as pipeline,
    ):
        pipeline.return_value.render.return_value = []
        await rerender_plan(
            plan=build_plan(),
            audio_path=audio,
            fixture_config_path=fixtures,
            render_policy=policy,
        )

    assert pipeline.call_args.kwargs["job_config"].moving_heads == policy
    assert inspect.signature(rerender_plan).parameters["render_policy"].default is (
        inspect.Parameter.empty
    )


@pytest.mark.asyncio
async def test_eval_report_refuses_a_physical_checkpoint_before_analysis(tmp_path: Path) -> None:
    """A checkpoint written by a physical job names its mode; the report refuses it
    before reading audio, instead of re-rendering the plan as legacy."""
    checkpoint = tmp_path / "final.json"
    checkpoint.write_text(
        json.dumps(
            {
                "run_id": "physical-run",
                "plan": build_plan().model_dump(mode="json"),
                "render_mode": "physical_v2",
            }
        )
    )
    with (
        patch("twinklr.core.audio.analyzer.AudioAnalyzer") as analyzer,
        pytest.raises(UnsupportedRenderModeError, match="physical_v2"),
    ):
        await generate_evaluation_report(
            checkpoint_path=checkpoint,
            audio_path=tmp_path / "song.wav",
            fixture_config_path=tmp_path / "fixtures.json",
            output_dir=tmp_path / "out",
        )
    analyzer.assert_not_called()


def test_checkpoint_without_a_mode_is_legacy() -> None:
    assert checkpoint_render_policy({"plan": {}}) == MHRenderPolicy()
    assert checkpoint_render_policy({"render_mode": "physical_v2"}).mode == "physical_v2"
