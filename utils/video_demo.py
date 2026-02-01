#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import time

from openai import OpenAI

PROMPT = """
Family-friendly winter holiday animation.

A cozy snowy village at night with warm glowing windows and a decorated Christmas tree.
Style: storybook illustration, simplified, low detail, bold shapes, clean edges.
Composition: wide depth but uncluttered, large shapes, clear horizon.
Lighting: warm window glow against cool snow, strong contrast.
Avoid: text, logos, watermarks, tiny details, heavy textures.

Animation: gentle falling snow, subtle window twinkle, soft chimney steam drifting upward.
Camera: fixed shot, no cuts, no zoom, no camera motion.
""".strip()


def wait_for_video(
    client: OpenAI, video_id: str, poll_s: float = 2.0, timeout_s: float = 180.0
) -> None:
    t0 = time.time()
    while True:
        job = client.videos.retrieve(video_id)
        if job.status == "completed":
            return
        if job.status in ("failed", "canceled"):
            raise RuntimeError(f"Video job {video_id} ended with status={job.status}: {job.error}")
        if time.time() - t0 > timeout_s:
            raise TimeoutError(f"Timed out waiting for video {video_id}. Last status={job.status}")
        time.sleep(poll_s)


def mp4_to_gif_ffmpeg(mp4_path: Path, gif_path: Path, fps: int = 12, width: int = 640) -> None:
    """
    High-quality GIF conversion using palette generation.
    Requires: ffmpeg in PATH.
    """
    palette = mp4_path.with_suffix(".palette.png")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(mp4_path),
            "-vf",
            f"fps={fps},scale={width}:-1:flags=lanczos,palettegen",
            str(palette),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(mp4_path),
            "-i",
            str(palette),
            "-lavfi",
            f"fps={fps},scale={width}:-1:flags=lanczos [x]; [x][1:v] paletteuse",
            str(gif_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

    palette.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out_video_demo")
    ap.add_argument(
        "--model", default="sora-2"
    )  # allowed: sora-2, sora-2-pro :contentReference[oaicite:4]{index=4}
    ap.add_argument(
        "--seconds", default="4"
    )  # allowed: 4, 8, 12 :contentReference[oaicite:5]{index=5}
    ap.add_argument(
        "--size", default="1280x720"
    )  # allowed sizes listed in docs :contentReference[oaicite:6]{index=6}
    ap.add_argument("--fps", type=int, default=12)
    args = ap.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    client = OpenAI()

    # 1) Create video job :contentReference[oaicite:7]{index=7}
    job = client.videos.create(
        model=args.model,
        prompt=PROMPT,
        seconds=args.seconds,
        size=args.size,
    )
    video_id = job.id
    print(f"video_id={video_id}")

    # 2) Wait until completed :contentReference[oaicite:8]{index=8}
    wait_for_video(client, video_id)

    # 3) Download MP4 bytes :contentReference[oaicite:9]{index=9}
    resp = client.videos.download_content(video_id=video_id)
    mp4_bytes = resp.read()

    mp4_path = out_dir / f"{video_id}.mp4"
    mp4_path.write_bytes(mp4_bytes)
    print(f"wrote {mp4_path}")

    # 4) Convert to GIF
    gif_path = out_dir / f"{video_id}.gif"
    mp4_to_gif_ffmpeg(mp4_path, gif_path, fps=args.fps, width=640)
    print(f"wrote {gif_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
