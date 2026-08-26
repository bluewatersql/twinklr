"""Tests for deterministic cache identity (session ID + cache-root anchoring).

Pins P1-F4 (a random session ID put every run's cache entries in a subtree no
later run could address) and P1-M3 (the cache root resolved against the process
working directory).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel
import pytest

from twinklr.core.caching import CacheKey, config_fingerprint, derive_session_id
from twinklr.core.caching.backends.fs import FSCache
from twinklr.core.caching.backends.null import NullCache
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.config.paths import PROJECT_ROOT_ENV_VAR, resolve_project_root
from twinklr.core.io import absolute_path, anchored_path
from twinklr.core.session import TwinklrSession


def _app_config(**overrides: object) -> AppConfig:
    payload: dict[str, object] = {
        "llm_provider": "openai",
        "llm_api_key": "test-key",
        "llm_base_url": "https://example.local/v1",
    }
    payload.update(overrides)
    return AppConfig.model_validate(payload)


def _job_config(**overrides: object) -> JobConfig:
    payload: dict[str, object] = {
        "agent": {
            "max_iterations": 1,
            "llm_logging": {"enabled": False},
            "agent_cache": {"enabled": True, "cache_path": "data/cache/agent"},
        }
    }
    payload.update(overrides)
    return JobConfig.model_validate(payload)


@pytest.fixture
def audio_file(tmp_path: Path) -> Path:
    path = tmp_path / "song.wav"
    path.write_bytes(b"RIFF-fake-audio-content")
    return path


class TestDerivedSessionId:
    """P1-F4: the ID must be a function of the job's inputs."""

    def test_session_id_is_deterministic_for_same_inputs(self, audio_file: Path) -> None:
        app_config = _app_config()
        job_config = _job_config()

        first = derive_session_id(audio_path=audio_file, configs=(app_config, job_config))
        second = derive_session_id(audio_path=audio_file, configs=(app_config, job_config))

        assert first == second

    def test_session_id_is_stable_across_processes(self, audio_file: Path) -> None:
        """Two interpreters must agree, not just two calls in one process."""
        import json
        import subprocess
        import sys

        script = (
            "import json,sys;"
            "from twinklr.core.caching import derive_session_id;"
            "from twinklr.core.config.models import AppConfig, JobConfig;"
            "payload = json.loads(sys.argv[1]);"
            "print(derive_session_id("
            "audio_path=payload['audio'],"
            "configs=(AppConfig.model_validate(payload['app']),"
            "JobConfig.model_validate(payload['job']))))"
        )
        payload = json.dumps(
            {
                "audio": str(audio_file),
                "app": {"llm_provider": "openai", "llm_api_key": "test-key"},
                "job": {"agent": {"max_iterations": 1}},
            }
        )

        runs = [
            subprocess.run(
                [sys.executable, "-c", script, payload],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            for _ in range(2)
        ]

        assert runs[0] == runs[1]
        assert runs[0].startswith("sess_")

    def test_session_id_changes_with_audio_or_config(self, tmp_path: Path) -> None:
        original = tmp_path / "a.wav"
        original.write_bytes(b"audio-one")
        different = tmp_path / "b.wav"
        different.write_bytes(b"audio-two")

        app_config = _app_config()
        job_config = _job_config()

        baseline = derive_session_id(audio_path=original, configs=(app_config, job_config))
        other_audio = derive_session_id(audio_path=different, configs=(app_config, job_config))
        other_config = derive_session_id(
            audio_path=original,
            configs=(app_config, _job_config(agent={"max_iterations": 7})),
        )

        assert other_audio != baseline
        assert other_config != baseline

    def test_session_id_ignores_audio_location(self, tmp_path: Path) -> None:
        """Content is hashed, not the path — moving the file must not orphan the cache."""
        first = tmp_path / "one" / "song.wav"
        second = tmp_path / "two" / "renamed.wav"
        for path in (first, second):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"identical-bytes")

        configs = (_app_config(), _job_config())
        assert derive_session_id(audio_path=first, configs=configs) == derive_session_id(
            audio_path=second, configs=configs
        )

    def test_session_id_ignores_environment_only_config(self, audio_file: Path) -> None:
        """Relocating the checkout or rotating a key must not orphan the cache."""
        configs_here = (_app_config(project_root="/somewhere"), _job_config())
        configs_there = (_app_config(project_root="/elsewhere"), _job_config())

        assert derive_session_id(audio_path=audio_file, configs=configs_here) == derive_session_id(
            audio_path=audio_file, configs=configs_there
        )

    def test_session_id_ignores_cache_directory(self, audio_file: Path) -> None:
        """Moving the machine-local cache must not fork semantic cache identity."""
        first = (_app_config(cache_dir="/tmp/cache-one"), _job_config())
        second = (_app_config(cache_dir="/tmp/cache-two"), _job_config())

        assert derive_session_id(audio_path=audio_file, configs=first) == derive_session_id(
            audio_path=audio_file, configs=second
        )

    def test_config_fingerprint_masks_secrets(self) -> None:
        fingerprint = config_fingerprint(_app_config(llm_api_key="super-secret"))
        assert "super-secret" not in fingerprint


class TestCacheRootAnchoring:
    """P1-M3: the cache root must not depend on the working directory."""

    def test_cache_root_is_cwd_independent(self, tmp_path: Path, monkeypatch) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        app_config = _app_config(project_root=str(project_root))
        job_config = _job_config()

        monkeypatch.chdir(project_root)
        from_project = TwinklrSession(
            app_config=app_config, job_config=job_config, session_id="s1"
        ).agent_cache.root

        monkeypatch.chdir(elsewhere)
        from_elsewhere = TwinklrSession(
            app_config=app_config, job_config=job_config, session_id="s1"
        ).agent_cache.root

        assert from_project == from_elsewhere
        assert Path(from_project) == project_root / "data" / "cache" / "agent"

    @pytest.mark.parametrize(
        ("config_path", "project_root", "cache_dir", "expected_parts"),
        (
            (
                "app.project_root",
                "configured-root",
                "audio-cache",
                ("configured-root", "audio-cache"),
            ),
            ("app.cache_dir", None, "changed-audio-cache", ("changed-audio-cache",)),
        ),
        ids=("app.project_root", "app.cache_dir"),
    )
    def test_app_cache_path_changes_audio_analyzer_cache_root(
        self,
        tmp_path: Path,
        config_path: str,
        project_root: str | None,
        cache_dir: str,
        expected_parts: tuple[str, ...],
    ) -> None:
        from twinklr.core.audio.analyzer import AudioAnalyzer

        configured_root = tmp_path / project_root if project_root else tmp_path
        configured_root.mkdir(exist_ok=True)
        config = _app_config(project_root=str(configured_root), cache_dir=cache_dir)
        analyzer = AudioAnalyzer(config, _job_config())

        assert Path(analyzer.cache.root) == configured_root / cache_dir, config_path
        assert all(part in Path(analyzer.cache.root).parts for part in expected_parts)

    def test_project_root_precedence(self, tmp_path: Path, monkeypatch) -> None:
        configured = tmp_path / "configured"
        fallback = tmp_path / "fallback"
        from_env = tmp_path / "env"
        for path in (configured, fallback, from_env):
            path.mkdir()

        monkeypatch.setenv(PROJECT_ROOT_ENV_VAR, str(from_env))

        assert resolve_project_root(_app_config(project_root=str(configured)), fallback) == (
            configured
        )
        assert resolve_project_root(_app_config(), fallback) == fallback
        assert resolve_project_root(_app_config()) == from_env

        monkeypatch.delenv(PROJECT_ROOT_ENV_VAR)
        monkeypatch.chdir(tmp_path)
        assert resolve_project_root(_app_config()) == Path.cwd().resolve()

    def test_absolute_path_rejects_relative_input(self) -> None:
        """The old guard resolved first, so it could never fire."""
        with pytest.raises(ValueError, match="must be absolute"):
            absolute_path("data/cache/agent")

        assert Path(absolute_path("/tmp/cache")).is_absolute()

    def test_anchored_path_resolves_relative_against_root(self) -> None:
        assert Path(anchored_path("data/cache", "/projects/twinklr")) == Path(
            "/projects/twinklr/data/cache"
        )
        assert Path(anchored_path("/opt/shared/cache", "/projects/twinklr")) == Path(
            "/opt/shared/cache"
        )

        with pytest.raises(ValueError, match="root must be absolute"):
            anchored_path("data/cache", "relative/root")


@pytest.mark.parametrize(
    ("config_path", "cache_payload", "expected_type", "expected_suffix"),
    (
        ("job.agent.agent_cache", {"enabled": False}, NullCache, None),
        ("job.agent.agent_cache.enabled", {"enabled": False}, NullCache, None),
        (
            "job.agent.agent_cache.cache_path",
            {"enabled": True, "cache_path": "changed-cache"},
            FSCache,
            "changed-cache",
        ),
    ),
    ids=(
        "job.agent.agent_cache",
        "job.agent.agent_cache.enabled",
        "job.agent.agent_cache.cache_path",
    ),
)
def test_agent_cache_field_changes_session_cache_owner(
    tmp_path: Path,
    config_path: str,
    cache_payload: dict[str, object],
    expected_type: type[object],
    expected_suffix: str | None,
) -> None:
    job = _job_config(agent={"agent_cache": cache_payload, "llm_logging": {"enabled": False}})
    cache = TwinklrSession(
        app_config=_app_config(project_root=str(tmp_path)), job_config=job, session_id="probe"
    ).agent_cache

    assert isinstance(cache, expected_type), config_path
    if expected_suffix is not None:
        assert Path(cache.root).name == expected_suffix  # type: ignore[union-attr]


class _CacheProbe(BaseModel):
    value: str


@pytest.mark.asyncio
async def test_agent_cache_ttl_changes_real_session_expiry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _job_config(
        agent={
            "agent_cache": {
                "enabled": True,
                "cache_path": "ttl-cache",
                "ttl_seconds": 10.0,
            },
            "llm_logging": {"enabled": False},
        }
    )
    cache = TwinklrSession(
        app_config=_app_config(project_root=str(tmp_path)), job_config=job, session_id="probe"
    ).agent_cache
    assert isinstance(cache, FSCache)
    key = CacheKey(
        domain="probe",
        session_id="probe",
        step_id="step",
        step_version="1",
        input_fingerprint="input",
    )
    monkeypatch.setattr("twinklr.core.caching.backends.fs.time.time", lambda: 100.0)
    await cache.store(key, _CacheProbe(value="fresh"))
    monkeypatch.setattr("twinklr.core.caching.backends.fs.time.time", lambda: 111.0)

    assert await cache.load(key, _CacheProbe) is None
