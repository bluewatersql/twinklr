"""End-to-end: writer output is valid `eval-report` input (P1P-T10).

Exercises the full evaluable path — the checkpoint writer, the `eval-report` CLI
bridge's underlying implementation, and the real production `RenderingPipeline` and
`AudioAnalyzer` — with no LLM call and no network access. The plan is the P1P-T2
deterministic fixture (`tests/golden/harness.py`); the audio is a synthetic,
deterministically generated tone (not a real song) that only needs to be analyzable by
`AudioAnalyzer`'s local DSP.
"""

from __future__ import annotations

import json
from pathlib import Path
import wave

import numpy as np
import pytest

from tests.golden.harness import RIGS, build_fixture_group, build_plan
from twinklr.core.agents.sequencer.moving_heads.stage import MovingHeadStage
from twinklr.core.config.models import JobConfig
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.reporting.evaluation.config import EvalConfig
from twinklr.core.reporting.evaluation.generator import generate_evaluation_report
from twinklr.core.reporting.evaluation.models import EvaluationReport
from twinklr.core.session import TwinklrSession


def _write_synthetic_tone(
    path: Path, *, duration_s: float = 64.0, sample_rate: int = 22050
) -> None:
    """A deterministic click track + tone — enough for AudioAnalyzer's local DSP to run
    against, without needing a real song or any network access."""
    t = np.arange(int(sample_rate * duration_s)) / sample_rate
    beat_period = 0.5
    click = (np.mod(t, beat_period) < 0.03).astype(np.float64)
    envelope = np.exp(-np.mod(t, beat_period) * 40)
    percussion = click * envelope
    tone = 0.2 * np.sin(2 * np.pi * 220 * t)
    signal = 0.6 * percussion + tone
    signal = signal / np.max(np.abs(signal))
    pcm = (signal * 32767 * 0.8).astype(np.int16)

    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(pcm.tobytes())


@pytest.mark.slow
@pytest.mark.asyncio
async def test_eval_report_runs_on_written_checkpoint(tmp_path: Path) -> None:
    """A checkpoint written by the stage's writer feeds straight into `eval-report`
    (via `generate_evaluation_report`, the function the click command calls) with no
    hand-editing."""
    # 1. Write a checkpoint exactly as a real pipeline run would, at the stage seam.
    stage = MovingHeadStage(fixture_count=4, available_templates=["sweep_lr_fan_hold"])
    session = TwinklrSession(
        job_config=JobConfig(project_name="e2e_probe"),
        session_id="e2e-probe-session",
        project_root=tmp_path,
    )
    output_dir = tmp_path / "artifacts"
    context = PipelineContext(session=session, output_dir=output_dir)
    plan = build_plan()
    stage._handle_state({"plan": plan.model_dump(mode="json")}, context)

    checkpoint_path = output_dir / "checkpoints" / "plans" / "final.json"
    assert checkpoint_path.exists()

    # 2. Build the other eval-report inputs deterministically (P1P-T2 golden rig, no
    # LLM/network).
    fixture_path = tmp_path / "fixture_config.json"
    fixture_path.write_text(
        build_fixture_group(RIGS["mh4_minimal"]).model_dump_json(), encoding="utf-8"
    )
    audio_path = tmp_path / "tone.wav"
    _write_synthetic_tone(audio_path)

    # 3. Run the exact function the `eval-report` click/CLI bridge calls — unmodified
    # checkpoint, no hand-editing.
    report = await generate_evaluation_report(
        checkpoint_path=checkpoint_path,
        audio_path=audio_path,
        fixture_config_path=fixture_path,
        output_dir=tmp_path / "report_out",
        config=EvalConfig(),
    )

    assert isinstance(report, EvaluationReport)
    assert report.summary.sections == len(plan.sections)

    report_json_path = tmp_path / "report_out" / "report.json"
    assert report_json_path.exists()
    written = json.loads(report_json_path.read_text(encoding="utf-8"))
    assert written["summary"]["sections"] == len(plan.sections)

    # P1P-T11: evaluation reads segments and writes reports. It used to take the user's
    # sequence as a render template and drop a `temp_eval.xsq` beside their audio; the
    # report path now writes no sequence file at all.
    assert list(tmp_path.rglob("*.xsq")) == []
