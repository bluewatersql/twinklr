"""Test planner template rendering on second iteration (with iteration var)."""

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

# Prepare variables AS THE CONTROLLER DOES ON SECOND+ ITERATION
variables = {
    "audio_profile": audio_profile.model_dump(mode="python"),
    "iteration": 2,  # Provided on iteration > 0
    "feedback": "Previous plan needs more variety in template selection.",
}

try:
    rendered = template.render(**variables)
    print("✅ Second iteration template rendered successfully!")
    print(f"   Length: {len(rendered)} characters")

    # Check that iteration context is present
    if "Iteration Context" in rendered:
        print("✅ Iteration context section present")
    if "iteration 2" in rendered:
        print("✅ Iteration number displayed correctly")
    if "Previous plan needs more variety" in rendered:
        print("✅ Feedback included correctly")
except Exception as e:
    print(f"❌ Second iteration template rendering failed: {e}")
    import traceback

    traceback.print_exc()
