"""The shipped pipeline command must honor AppConfig logging settings."""

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from twinklr.cli.main import run_pipeline
from twinklr.core.config.models import AppConfig


def test_run_pipeline_configures_logging_from_app_config(tmp_path: Path) -> None:
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"audio")
    job = tmp_path / "job.json"
    job.write_text("{}")
    app = tmp_path / "app.json"
    app.write_text("{}")
    args = argparse.Namespace(
        audio=str(audio),
        out=str(tmp_path / "out"),
        app_config=str(app),
        config=str(job),
        session_id=None,
        template_dir=None,
        allow_template_overrides=False,
        cmd="run",
    )
    configured = AppConfig(logging={"level": "DEBUG", "format": "LEVEL=%(levelname)s"})

    def finish_without_running(coroutine: object) -> int:
        coroutine.close()  # type: ignore[attr-defined]
        return 0

    with (
        patch("twinklr.cli.main.load_app_config", return_value=configured),
        patch("twinklr.cli.main.configure_logging") as configure,
        patch("twinklr.cli.main.asyncio.run", side_effect=finish_without_running),
        pytest.raises(SystemExit) as exit_info,
    ):
        run_pipeline(args)

    assert exit_info.value.code == 0
    configure.assert_called_once_with(level="DEBUG", format_string="LEVEL=%(levelname)s")
