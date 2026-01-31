from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex
import subprocess
import sys


@dataclass(frozen=True)
class Job:
    cmd: list[str]
    label: str


def run(job: Job) -> int:
    print("\n" + "=" * 100)
    print(f"RUN: {job.label}")
    print("CMD:", shlex.join(job.cmd))
    print("=" * 100)

    # stream output live; return code captured
    p = subprocess.run(job.cmd)
    if p.returncode != 0:
        print(f"\nFAILED: {job.label} (exit={p.returncode})")
    else:
        print(f"\nOK: {job.label}")
    return p.returncode


def main() -> int:
    python = sys.executable  # use the same venv/interpreter you used to launch this script

    tracks = [
        "data/music/01 - A Holly Jolly Christmas.mp3",
        "data/music/02 - Animals (Radio Edit) [Explicit].mp3",
        "data/music/02 - Rudolph the Red-Nosed Reindeer.mp3",
        "data/music/Christmas Can-Can.mp3",
        "data/music/Need A Favor.mp3",
    ]

    jobs: list[Job] = []

    # demo_audio_profile for each track, --no-cache
    for t in tracks:
        # jobs.append(
        #     Job(
        #         cmd=[python, "scripts/test_audio_pipeline.py", t, "--enable-all", "--no-cache"],
        #         label=f"test_audio_pipeline | {Path(t).name}",
        #     )
        # )

        jobs.append(
            Job(
                cmd=[python, "scripts/demo_audio_profile.py", t],
                label=f"demo_audio_profile | {Path(t).name}",
            )
        )

    # run sequentially; stop on first failure
    for job in jobs:
        rc = run(job)
        if rc != 0:
            return rc

    print("\nALL DONE ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
