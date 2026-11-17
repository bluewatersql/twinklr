"""The evaluation re-render takes no user sequence (P1P-T11).

`rerender_plan` was the third export-path caller and the easiest to miss: it passed the
user's `.xsq` into `RenderingPipeline` as a template and pointed the output at
`temp_eval.xsq` next to their audio, so generating a report both read and wrote sequence
files it had no need to touch.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests.support.mh_physical import (
    physical_catalog,
    physical_grid,
    physical_job,
    physical_rig,
    physical_sections,
)
from twinklr.core.reporting.evaluation.cli import eval_report_cli
from twinklr.core.reporting.evaluation.collect import RecordedRender
from twinklr.core.reporting.evaluation.generator import generate_evaluation_report
from twinklr.core.reporting.evaluation.rerender import rerender_plan


def test_rerender_uses_fresh_path() -> None:
    """No sequence input reaches the re-render, at any layer of the eval stack."""
    for func in (rerender_plan, generate_evaluation_report):
        parameters = inspect.signature(func).parameters
        assert "xsq_path" not in parameters, f"{func.__name__} still takes a sequence"

    assert "template_xsq" not in inspect.getsource(rerender_plan)


def test_rerender_writes_no_sequence_file() -> None:
    """The pipeline is built with no output path, so nothing is exported."""
    assert "output_path=None" in inspect.getsource(rerender_plan)


def test_eval_report_cli_has_no_xsq_option() -> None:
    """The retired input is gone from the command the user types too."""
    option_names = {name for param in eval_report_cli.params for name in param.opts}
    assert "--xsq" not in option_names
    assert {"--checkpoint", "--audio", "--fixture", "--out"} <= option_names


@pytest.mark.asyncio
async def test_rerender_passes_the_recorded_policy_to_the_pipeline(tmp_path: Path) -> None:
    """The recorded render is a required input and its policy is what the re-render's
    pipeline runs under."""
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"audio")
    fixtures = tmp_path / "fixtures.json"
    fixtures.write_text(physical_rig().model_dump_json())
    policy = physical_job(reposition_fallback="drop_accent").moving_heads
    recorded = RecordedRender(
        fingerprint="0" * 64,
        policy=policy,
        beat_grid=physical_grid(),
        admission=None,
        dark_spans=(),
        inputs={},
    )

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
        physical_catalog(),
        patch("twinklr.core.audio.analyzer.AudioAnalyzer", FakeAnalyzer),
        patch("twinklr.core.reporting.evaluation.rerender.RenderingPipeline") as pipeline,
    ):
        pipeline.return_value.render.return_value = []
        await rerender_plan(
            plan=physical_sections(("mirror_wings", 1, 2)),
            audio_path=audio,
            fixture_config_path=fixtures,
            recorded=recorded,
        )

    assert pipeline.call_args.kwargs["job_config"].moving_heads == policy
    assert pipeline.call_args.kwargs["beat_grid"] == recorded.beat_grid
    assert inspect.signature(rerender_plan).parameters["recorded"].default is (
        inspect.Parameter.empty
    )
