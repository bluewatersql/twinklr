"""Offline tests for frame/contact-sheet production."""

from pathlib import Path
import subprocess
from unittest.mock import patch

from PIL import Image
import pytest

from twinklr.core.reporting.evaluation.vision_frames import (
    FFmpegUnavailableError,
    FrameSampler,
    FrameSamplerConfig,
    FrameSamplingError,
    compose_contact_sheets,
    resolve_ffmpeg,
)


def test_ffmpeg_missing_is_actionable() -> None:
    with pytest.raises(FFmpegUnavailableError, match="Install ffmpeg"):
        resolve_ffmpeg(which=lambda _: None, bundled_resolver=lambda: None)


def test_explicit_ffmpeg_must_be_executable(tmp_path: Path) -> None:
    ffmpeg = tmp_path / "ffmpeg"
    ffmpeg.write_text("not executable", encoding="utf-8")

    with pytest.raises(FFmpegUnavailableError, match="not an executable"):
        resolve_ffmpeg(ffmpeg)


def test_contact_sheet_labels_frames(tmp_path: Path) -> None:
    frame_paths = []
    for index in range(9):
        path = tmp_path / f"frame_{index + 1:05d}.png"
        Image.new("RGB", (320, 180), (index * 20, 0, 0)).save(path)
        frame_paths.append(path)

    sheets = compose_contact_sheets(
        frame_paths,
        output_dir=tmp_path / "sheets",
        config=FrameSamplerConfig(contact_sheet_size=9),
    )

    assert len(sheets) == 1
    assert sheets[0].frame_indices == tuple(range(1, 10))
    assert sheets[0].path.exists()
    assert Image.open(sheets[0].path).size == (1280, 720)


def test_repeated_sampling_uses_clean_unique_output(tmp_path: Path) -> None:
    ffmpeg = tmp_path / "ffmpeg"
    ffmpeg.write_text("#!/bin/sh\n", encoding="utf-8")
    ffmpeg.chmod(0o700)
    preview = tmp_path / "preview.mp4"
    preview.write_bytes(b"preview")
    invocation = 0

    def fake_run(command: list[str], **_: object) -> None:
        nonlocal invocation
        invocation += 1
        output_pattern = Path(command[-1])
        count = 4 if invocation == 1 else 2
        for index in range(1, count + 1):
            Image.new("RGB", (320, 180), "black").save(
                output_pattern.parent / f"frame_{index:05d}.png"
            )

    sampler = FrameSampler(ffmpeg_path=ffmpeg)
    with patch(
        "twinklr.core.reporting.evaluation.vision_frames.subprocess.run",
        side_effect=fake_run,
    ):
        first = sampler.sample(preview, tmp_path / "samples")
        second = sampler.sample(preview, tmp_path / "samples")

    assert len(first) == 4
    assert len(second) == 2
    assert first[0].path.parent != second[0].path.parent


def test_sampling_timeout_is_actionable(tmp_path: Path) -> None:
    ffmpeg = tmp_path / "ffmpeg"
    ffmpeg.write_text("#!/bin/sh\n", encoding="utf-8")
    ffmpeg.chmod(0o700)
    preview = tmp_path / "preview.mp4"
    preview.write_bytes(b"preview")
    sampler = FrameSampler(
        config=FrameSamplerConfig(timeout_seconds=7),
        ffmpeg_path=ffmpeg,
    )

    with (
        patch(
            "twinklr.core.reporting.evaluation.vision_frames.subprocess.run",
            side_effect=subprocess.TimeoutExpired("ffmpeg", 7),
        ),
        pytest.raises(FrameSamplingError, match="timed out after 7 seconds"),
    ):
        sampler.sample(preview, tmp_path / "samples")
