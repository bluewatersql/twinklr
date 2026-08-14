"""ffmpeg frame sampling and Pillow contact-sheet composition."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict, Field


class FFmpegUnavailableError(RuntimeError):
    """Raised when neither an explicit, system nor bundled ffmpeg can be found."""


class FrameSamplingError(RuntimeError):
    """Raised when ffmpeg cannot produce sampled frames."""


class FrameSamplerConfig(BaseModel):
    """Sampling/resolution settings and contact-sheet cost dial."""

    frames_per_second: float = Field(default=2.0, ge=2.0, le=4.0)
    width: int = Field(default=1280, ge=320, le=3840)
    height: int = Field(default=720, ge=180, le=2160)
    contact_sheet_size: int = Field(default=12, ge=9, le=16)
    use_contact_sheets: bool = False
    timeout_seconds: int = Field(default=300, gt=0, le=1800)

    model_config = ConfigDict(extra="forbid", frozen=True)


class SampledFrame(BaseModel):
    """One timestamp-labeled video sample."""

    index: int = Field(ge=1)
    timestamp_ms: int = Field(ge=0)
    path: Path
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @property
    def label(self) -> str:
        return f"Frame {self.index} · {_format_timestamp(self.timestamp_ms)}"


class ContactSheet(BaseModel):
    """A fixed-resolution contact sheet carrying 9-16 labeled frames."""

    index: int = Field(ge=1)
    path: Path
    frame_indices: tuple[int, ...]
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class FrameSampler:
    """Sample preview video frames with one resolved ffmpeg binary."""

    config: FrameSamplerConfig = field(default_factory=FrameSamplerConfig)
    ffmpeg_path: Path | None = None

    def sample(self, video_path: Path, output_dir: Path) -> list[SampledFrame]:
        if not video_path.is_file():
            raise FileNotFoundError(f"Preview video not found: {video_path}")
        ffmpeg = resolve_ffmpeg(self.ffmpeg_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        run_dir = Path(tempfile.mkdtemp(prefix="sample-", dir=output_dir))
        output_pattern = run_dir / "frame_%05d.png"
        command = [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-vf",
            (
                f"fps={self.config.frames_per_second:g},"
                f"scale={self.config.width}:{self.config.height}:"
                "force_original_aspect_ratio=decrease"
            ),
            "-vsync",
            "vfr",
            "-y",
            str(output_pattern),
        ]
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            raise FrameSamplingError(
                f"ffmpeg sampling timed out after {self.config.timeout_seconds} seconds for "
                f"{video_path}; lower the sampling rate/resolution or raise timeout_seconds."
            ) from error
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or "unknown ffmpeg error").strip()
            raise FrameSamplingError(f"ffmpeg could not sample {video_path}: {detail}") from error
        paths = sorted(run_dir.glob("frame_*.png"))
        if not paths:
            raise FrameSamplingError(f"ffmpeg produced no frames for preview video: {video_path}")
        samples = []
        for index, path in enumerate(paths, start=1):
            with Image.open(path) as image:
                width, height = image.size
            samples.append(
                SampledFrame(
                    index=index,
                    timestamp_ms=round((index - 1) * 1000 / self.config.frames_per_second),
                    path=path,
                    width=width,
                    height=height,
                )
            )
        return samples


def resolve_ffmpeg(
    explicit_path: Path | None = None,
    *,
    which: Callable[[str], str | None] = shutil.which,
    bundled_resolver: Callable[[], str | None] | None = None,
) -> Path:
    """Resolve explicit, system, then imageio-bundled ffmpeg truthfully."""
    if explicit_path is not None:
        if _is_executable(explicit_path):
            return explicit_path
        raise FFmpegUnavailableError(
            f"Configured ffmpeg path is not an executable file: {explicit_path}"
        )
    system_path = which("ffmpeg")
    if system_path and _is_executable(Path(system_path)):
        return Path(system_path)
    resolver = bundled_resolver or _bundled_ffmpeg
    bundled_path = resolver()
    if bundled_path and _is_executable(Path(bundled_path)):
        return Path(bundled_path)
    raise FFmpegUnavailableError(
        "No ffmpeg executable is available. Install ffmpeg on PATH or install the "
        "imageio-ffmpeg bundle used by Twinklr, then retry frame sampling."
    )


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def compose_contact_sheets(
    frame_paths: list[Path],
    *,
    output_dir: Path,
    config: FrameSamplerConfig | None = None,
) -> list[ContactSheet]:
    """Compose fixed-resolution, timestamp-labeled 3x3/4x4 contact sheets."""
    config = config or FrameSamplerConfig()
    if not frame_paths:
        raise ValueError("At least one frame is required to compose contact sheets")
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="sheets-", dir=output_dir))
    columns = 3 if config.contact_sheet_size == 9 else 4
    rows = (config.contact_sheet_size + columns - 1) // columns
    cell_width = config.width // columns
    cell_height = config.height // rows
    sheets = []
    for sheet_index, offset in enumerate(
        range(0, len(frame_paths), config.contact_sheet_size), start=1
    ):
        group = frame_paths[offset : offset + config.contact_sheet_size]
        canvas = Image.new("RGB", (config.width, config.height), "black")
        for local_index, path in enumerate(group):
            frame_index = offset + local_index + 1
            with Image.open(path) as source:
                image = source.convert("RGB")
                image.thumbnail((cell_width, cell_height), Image.Resampling.LANCZOS)
                x = (local_index % columns) * cell_width + (cell_width - image.width) // 2
                y = (local_index // columns) * cell_height + (cell_height - image.height) // 2
                canvas.paste(image, (x, y))
            draw = ImageDraw.Draw(canvas)
            label = f"Frame {frame_index}"
            timestamp_ms = round((frame_index - 1) * 1000 / config.frames_per_second)
            label = f"Frame {frame_index} · {_format_timestamp(timestamp_ms)}"
            label_x = (local_index % columns) * cell_width + 6
            label_y = (local_index // columns) * cell_height + 6
            draw.rectangle((label_x - 3, label_y - 3, label_x + 145, label_y + 14), fill="black")
            draw.text((label_x, label_y), label, fill="white")
        output_path = run_dir / f"contact_sheet_{sheet_index:03d}.png"
        canvas.save(output_path, format="PNG")
        sheets.append(
            ContactSheet(
                index=sheet_index,
                path=output_path,
                frame_indices=tuple(range(offset + 1, offset + len(group) + 1)),
                width=config.width,
                height=config.height,
            )
        )
    return sheets


def _bundled_ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg

        resolved = imageio_ffmpeg.get_ffmpeg_exe()
        return str(resolved) if resolved else None
    except (ImportError, RuntimeError):
        return None


def _format_timestamp(timestamp_ms: int) -> str:
    minutes, remainder = divmod(timestamp_ms, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
