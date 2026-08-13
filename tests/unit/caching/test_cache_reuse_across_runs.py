"""End-to-end proof that a re-run reuses cached LLM work (P1-F4 payoff).

Two pipeline "runs" share nothing but their inputs: same audio content, same
configs, separate sessions and caches built from scratch. The second run must
find the first run's entry. Before the session ID was derived, each run invented
a UUID and wrote into a subtree the next run could not address, so the compute
function ran every time. No provider or API is involved.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel
import pytest

from twinklr.core.caching import derive_session_id
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.pipeline.execution import execute_step
from twinklr.core.session import TwinklrSession


class StagePlan(BaseModel):
    """Stand-in for an orchestration result."""

    success: bool = True
    sections: list[str] = []


@pytest.fixture
def audio_file(tmp_path: Path) -> Path:
    path = tmp_path / "song.wav"
    path.write_bytes(b"RIFF-fake-audio-content")
    return path


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    return root


def _configs(project_root: Path) -> tuple[AppConfig, JobConfig]:
    app_config = AppConfig.model_validate(
        {
            "project_root": str(project_root),
            "llm_provider": "openai",
            "llm_api_key": "test-key",
        }
    )
    job_config = JobConfig.model_validate(
        {
            "agent": {
                "max_iterations": 1,
                "llm_logging": {"enabled": False},
                "agent_cache": {"enabled": True, "cache_path": "data/cache/agent"},
            }
        }
    )
    return app_config, job_config


async def _run_stage(
    *,
    audio_file: Path,
    project_root: Path,
    cache_key: str,
    calls: list[str],
) -> PipelineContext:
    """Execute one cached stage exactly as a fresh process would."""
    app_config, job_config = _configs(project_root)
    session = TwinklrSession(
        app_config=app_config,
        job_config=job_config,
        session_id=derive_session_id(audio_path=audio_file, configs=(app_config, job_config)),
    )
    context = PipelineContext(session=session, output_dir=project_root)

    async def compute() -> StagePlan:
        calls.append(cache_key)
        return StagePlan(sections=["intro", "chorus"])

    await execute_step(
        stage_name="macro_plan",
        context=context,
        compute=compute,
        result_extractor=lambda r: r.sections,
        result_type=StagePlan,
        cache_key_fn=lambda: _static_key(cache_key),
    )
    return context


async def _static_key(value: str) -> str:
    return value


async def test_second_run_hits_cache(audio_file: Path, project_root: Path) -> None:
    calls: list[str] = []

    first = await _run_stage(
        audio_file=audio_file, project_root=project_root, cache_key="fp-1", calls=calls
    )
    second = await _run_stage(
        audio_file=audio_file, project_root=project_root, cache_key="fp-1", calls=calls
    )

    assert first.session.session_id == second.session.session_id
    assert first.metrics["macro_plan_cache_status"] == "miss"
    assert second.metrics["macro_plan_cache_status"] == "hit"
    assert second.metrics["macro_plan_from_cache"] is True
    assert calls == ["fp-1"], "the second run recomputed instead of reusing the cached plan"


async def test_changed_stage_key_misses(audio_file: Path, project_root: Path) -> None:
    """A prompt edit changes the stage's fingerprint, so the entry is not served."""
    calls: list[str] = []

    await _run_stage(
        audio_file=audio_file, project_root=project_root, cache_key="fp-1", calls=calls
    )
    second = await _run_stage(
        audio_file=audio_file,
        project_root=project_root,
        cache_key="fp-2-after-prompt-edit",
        calls=calls,
    )

    assert second.metrics["macro_plan_cache_status"] == "miss"
    assert calls == ["fp-1", "fp-2-after-prompt-edit"]


async def test_different_audio_uses_a_separate_cache_subtree(
    tmp_path: Path, audio_file: Path, project_root: Path
) -> None:
    other_audio = tmp_path / "other.wav"
    other_audio.write_bytes(b"a completely different song")
    calls: list[str] = []

    first = await _run_stage(
        audio_file=audio_file, project_root=project_root, cache_key="fp-1", calls=calls
    )
    second = await _run_stage(
        audio_file=other_audio, project_root=project_root, cache_key="fp-1", calls=calls
    )

    assert first.session.session_id != second.session.session_id
    assert second.metrics["macro_plan_cache_status"] == "miss"
    assert len(calls) == 2
