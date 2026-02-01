#!/usr/bin/env python3
"""Quick test script for GroupPlanner Phase 3 validation.

Tests GroupPlanner with canned fixtures (no LLM calls needed for basic validation).
For full E2E with LLM, use: scripts/demo_sequencer_pipeline.py
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from twinklr.core.agents.audio.profile.models import AudioProfileModel
from twinklr.core.agents.sequencer.group_planner.context import (
    DisplayGroupRef,
    GroupPlanningContext,
)
from twinklr.core.agents.sequencer.macro_planner.models import (
    GlobalStory,
    LayerSpec,
    LayeringPlan,
    MacroPlan,
    MacroSectionPlan,
    SongSectionRef,
    TargetSelector,
)
from twinklr.core.sequencer.templates.group_templates import (
    bootstrap_traditional,  # noqa: F401
)
from twinklr.core.sequencer.templates.group_templates.library import list_templates
from twinklr.core.sequencer.templates.models import template_ref_from_info


def load_fixture(fixture_path: Path) -> dict:
    """Load JSON fixture."""
    with fixture_path.open() as f:
        return json.load(f)


async def main():
    """Test GroupPlanner Phase 3 components."""
    print("=" * 60)
    print("GroupPlanner Phase 3 - Component Validation")
    print("=" * 60)

    # Test 1: Template Registry
    print("\n[1/5] Testing template registry...")
    template_infos = list_templates()
    print(f"✅ Loaded {len(template_infos)} templates from registry")

    # Test 2: Template → TemplateRef conversion
    print("\n[2/5] Testing TemplateRef conversion...")
    template_refs = [template_ref_from_info(info) for info in template_infos]
    print(f"✅ Converted {len(template_refs)} TemplateInfo → TemplateRef")

    # Show template metadata
    print("\n   Sample template metadata:")
    for ref in template_refs[:3]:
        print(f"   - {ref.template_id}")
        print(f"     Name: {ref.name}")
        print(f"     Type: {ref.template_type}")
        print(f"     Tags: {', '.join(ref.tags[:3])}")

    # Test 3: Load fixtures
    print("\n[3/5] Loading test fixtures...")
    fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"

    try:
        # Load audio profile
        audio_profile_path = fixtures_dir / "audio_profile" / "audio_profile_model.json"
        audio_profile_data = load_fixture(audio_profile_path)
        audio_profile = AudioProfileModel.model_validate(audio_profile_data)
        print(f"✅ Loaded AudioProfile: {audio_profile.song_identity.title}")

        # Create minimal MacroPlan with required section_plans
        section_plans = [
            MacroSectionPlan(
                section=SongSectionRef(
                    section_id="intro",
                    name="intro",
                    start_ms=0,
                    end_ms=16000,
                ),
                visual_focus="Warm, inviting opener",
                motion_density="sparse",
                energy_target="calm",
                choreography_notes="Gentle twinkle to establish mood",
                primary_layers=[0],
                rhythm_layers=[],
            )
        ]

        macro_plan = MacroPlan(
            global_story=GlobalStory(
                theme="Festive celebration with warm traditional Christmas elements",
                motifs=["twinkling lights", "warm glow", "synchronized patterns"],
                pacing_notes="Build gradually from calm intro to energetic peaks",
                color_story="Warm whites and golds with traditional reds and greens",
            ),
            layering_plan=LayeringPlan(
                strategy_notes="Two-layer approach: BASE for scene backgrounds, RHYTHM for beat-driven accents",
                layers=[
                    LayerSpec(
                        layer_index=0,
                        layer_role="BASE",
                        blend_mode="NORMAL",
                        usage_notes="Foundation layer for scene backgrounds",
                        timing_driver="BARS",
                        target_selector=TargetSelector(roles=["MATRIX"]),
                        intensity_bias=0.8,
                    ),
                    LayerSpec(
                        layer_index=1,
                        layer_role="RHYTHM",
                        blend_mode="ADD",
                        usage_notes="Beat-driven accent layer",
                        timing_driver="BEATS",
                        target_selector=TargetSelector(roles=["OUTLINE", "ARCHES"]),
                        intensity_bias=1.0,
                    ),
                ],
            ),
            section_plans=section_plans,
        )
        print(f"✅ Created test MacroPlan: {macro_plan.global_story.theme}")

    except Exception as e:
        print(f"❌ Failed to load fixtures: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Test 4: Build GroupPlanningContext
    print("\n[4/5] Building GroupPlanningContext...")

    display_group = DisplayGroupRef(
        group_id="matrix_main",
        name="Main Matrix",
        group_type="MATRIX",
        model_count=100,
        tags=["primary", "visual"],
    )

    context = GroupPlanningContext(
        audio_profile=audio_profile,
        lyric_context=None,  # Optional
        macro_plan=macro_plan,
        display_group=display_group,
        available_templates=template_refs,
        max_layers=3,
    )

    print("✅ GroupPlanningContext created successfully")
    print(f"   Group: {context.display_group.name} ({context.display_group.group_type})")
    print(f"   Templates: {len(context.available_templates)}")
    print(f"   Max layers: {context.max_layers}")

    # Test 5: Validate prompt rendering (without actual LLM call)
    print("\n[5/5] Testing prompt rendering...")

    from twinklr.core.agents.prompts.renderer import render_prompt_pack
    from twinklr.core.agents.sequencer.group_planner.specs import get_planner_spec

    spec = get_planner_spec()

    try:
        # Render system prompt
        system_prompt = render_prompt_pack(
            prompt_pack=spec.prompt_pack,
            template_name="system",
            variables={},
        )
        print(f"✅ System prompt rendered ({len(system_prompt)} chars)")

        # Render user prompt with context
        user_prompt = render_prompt_pack(
            prompt_pack=spec.prompt_pack,
            template_name="user",
            variables={
                "audio_profile": audio_profile,
                "macro_plan": macro_plan,
                "display_group": display_group,
                "available_templates": template_refs,  # Uses Phase 2 TemplateRef format
            },
        )
        print(f"✅ User prompt rendered ({len(user_prompt)} chars)")

        # Check that template metadata is in prompt
        if any(ref.name in user_prompt for ref in template_refs[:3]):
            print(f"✅ Template metadata (names) found in user prompt")
        else:
            print(f"⚠️  Template names not found in prompt (expected from Phase 2)")

    except Exception as e:
        print(f"❌ Prompt rendering failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Success!
    print("\n" + "=" * 60)
    print("✅ All Phase 3 validation tests passed!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Run full E2E with LLM:")
    print("     export OPENAI_API_KEY='your-key-here'")
    print("     uv run python scripts/demo_sequencer_pipeline.py")
    print("  2. Check outputs in artifacts/ directory")
    print("  3. Validate GroupPlan JSON structure")


if __name__ == "__main__":
    asyncio.run(main())
