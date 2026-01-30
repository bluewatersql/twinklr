"""Test planner template rendering on first iteration (no iteration var)."""

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from twinklr.core.agents.audio.profile.models import AudioProfileModel

# Load AudioProfile
profile_path = Path("artifacts/audio_profile_demo_output.json")
with profile_path.open() as f:
    profile_data = json.load(f)

audio_profile = AudioProfileModel.model_validate(profile_data)

# Setup Jinja2 environment
template_dir = Path("packages/twinklr/core/agents/sequencer/macro_planner/prompts/planner")
env = Environment(
    loader=FileSystemLoader(str(template_dir)),
    undefined=StrictUndefined,
)

# Load and render user template
template = env.get_template("user.j2")

# Prepare variables AS THE CONTROLLER DOES ON FIRST ITERATION
# (no iteration, no feedback - these are only added on iteration > 0)
variables = {
    "audio_profile": audio_profile.model_dump(mode="python"),
    # Note: iteration and feedback NOT provided on first iteration!
}

try:
    rendered = template.render(**variables)
    print("✅ First iteration template rendered successfully!")
    print(f"   Length: {len(rendered)} characters")
except Exception as e:
    print(f"❌ First iteration template rendering failed: {e}")
    import traceback

    traceback.print_exc()
