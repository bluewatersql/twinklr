"""Demo script for Phase 0: Verify checkpoint loading and plan extraction."""

from pathlib import Path

from blinkb0t.core.reporting.evaluation.collect import (
    build_run_metadata,
    extract_plan,
    load_checkpoint,
)
from blinkb0t.core.reporting.evaluation.config import EvalConfig

# Use the actual checkpoint from artifacts
CHECKPOINT_PATH = Path("artifacts/need_a_favor/checkpoints/plans/need_a_favor_final.json")


def main():
    """Demonstrate Phase 0 functionality."""
    print("=" * 70)
    print("Phase 0 Demo: Checkpoint Loading & Plan Extraction")
    print("=" * 70)
    print()

    # Check if checkpoint exists
    if not CHECKPOINT_PATH.exists():
        print(f"❌ Checkpoint not found: {CHECKPOINT_PATH}")
        print("   Run the demo.py script first to generate checkpoints.")
        return

    # Step 1: Load checkpoint
    print(f"📂 Loading checkpoint: {CHECKPOINT_PATH.name}")
    checkpoint_data = load_checkpoint(CHECKPOINT_PATH)
    print(f"   ✓ Loaded checkpoint with keys: {list(checkpoint_data.keys())}")
    print()

    # Step 2: Extract plan
    print("📋 Extracting choreography plan...")
    plan = extract_plan(checkpoint_data)
    print(f"   ✓ Plan has {len(plan.sections)} sections")
    print(f"   ✓ Overall strategy: {plan.overall_strategy[:80]}...")
    print()

    # Step 3: Build metadata
    print("🔍 Building run metadata...")
    metadata = build_run_metadata(CHECKPOINT_PATH, checkpoint_data)
    print(f"   ✓ Run ID: {metadata.run_id}")
    print(f"   ✓ Timestamp: {metadata.timestamp}")
    print(f"   ✓ Git SHA: {metadata.git_sha or 'N/A'}")
    print(f"   ✓ Engine version: {metadata.engine_version}")
    print(f"   ✓ Checkpoint path: {metadata.checkpoint_path.name}")
    print()

    # Step 4: Show section details
    print("📊 Section Details:")
    print("-" * 70)
    for i, section in enumerate(plan.sections, 1):
        print(f"{i}. {section.section_name} (bars {section.start_bar}-{section.end_bar})")
        print(f"   Role: {section.section_role}, Energy: {section.energy_level}")

        if section.segments:
            print(f"   Segmented: {len(section.segments)} segments")
            for seg in section.segments:
                print(
                    f"     - Segment {seg.segment_id}: {seg.template_id} "
                    f"(bars {seg.start_bar}-{seg.end_bar})"
                )
        else:
            print(f"   Template: {section.template_id}")
            if section.preset_id:
                print(f"   Preset: {section.preset_id}")

        print()

    # Step 5: Demo config
    print("⚙️  Configuration:")
    print("-" * 70)
    config = EvalConfig()
    print(f"   Samples per bar: {config.samples_per_bar}")
    print(f"   Clamp warning threshold: {config.clamp_warning_threshold * 100}%")
    print(f"   Clamp error threshold: {config.clamp_error_threshold * 100}%")
    print(f"   Loop delta threshold: {config.loop_delta_threshold}")
    print(f"   Output formats: {', '.join(config.output_format)}")
    print()

    # Summary
    print("=" * 70)
    print("✅ Phase 0 Complete!")
    print("=" * 70)
    print()
    print("Successfully demonstrated:")
    print("  • Checkpoint loading from JSON")
    print("  • ChoreographyPlan extraction and validation")
    print("  • Run metadata generation")
    print("  • Configuration model")
    print()
    print("Next: Phase 1 - Re-rendering, curve extraction, and report generation")


if __name__ == "__main__":
    main()
