#!/usr/bin/env python3
"""Simple debug script to test context shaping."""

import asyncio
from pathlib import Path

# Add packages to path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from twinklr.core.agents.audio.profile.context import shape_context
from twinklr.core.audio.analyzer import AudioAnalyzer
from twinklr.core.config import load_app_config, load_job_config


async def main():
    print("Loading configs...")
    app_config = load_app_config()
    # Use empty job config to avoid validation issues
    job_config_dict = {
        "agent": {"max_iterations": 3, "llm_logging": {"enabled": False}},
        "checkpoint": {"enabled": False},
        "fixture_config_path": "doc/configs/fixture_config.example.json",
    }
    job_config = load_job_config(job_config_dict)

    print("Analyzing audio...")
    analyzer = AudioAnalyzer(app_config, job_config)
    bundle = await analyzer.analyze("data/music/Need A Favor.mp3")

    print(f"Sections: {len(bundle.features['structure']['sections'])}")

    print("\nShaping context...")
    shaped = shape_context(bundle)

    print(f"Shaped sections: {len(shaped['sections'])}")
    print(f"Shaped energy profiles: {len(shaped['energy']['section_profiles'])}")

    # Check each section profile
    for i, prof in enumerate(shaped["energy"]["section_profiles"]):
        curve = prof["energy_curve"]
        timestamps = [p["t_ms"] for p in curve]
        is_mono = all(timestamps[j] <= timestamps[j + 1] for j in range(len(timestamps) - 1))

        status = "✅" if is_mono else "❌"
        print(
            f"{status} Section {i} ({prof['section_id']}): {len(curve)} points, monotonic={is_mono}"
        )

        if not is_mono:
            print(f"   Timestamps: {timestamps}")
            for j in range(len(timestamps) - 1):
                if timestamps[j] > timestamps[j + 1]:
                    print(f"   BAD: {timestamps[j]} -> {timestamps[j + 1]} at index {j}")


if __name__ == "__main__":
    asyncio.run(main())
