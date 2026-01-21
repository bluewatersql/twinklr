#!/usr/bin/env python3
"""Analyze test coverage forcomponents (Component 7).

Provides detailed coverage breakdown by component and identifies areas needing improvement.
"""

import json
from pathlib import Path
import subprocess
import sys


def run_coverage():
    """Run test suite with coverage."""
    print("Running full test suite with coverage...\n")

    result = subprocess.run(
        ["pytest", "--cov=blinkb0t", "--cov-report=json", "--cov-report=term", "-q"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0 and "passed" not in result.stdout:
        print("❌ Tests failed:")
        print(result.stdout)
        print(result.stderr)
        return None

    print(result.stdout)
    return result


def analyze_coverage():
    """Analyze coverage forcomponents."""
    coverage_file = Path(".coverage.json")

    if not coverage_file.exists():
        # Try alternative name
        coverage_file = Path("coverage.json")

    if not coverage_file.exists():
        print("❌ Coverage file not found. Run pytest with --cov-report=json first.")
        return

    with coverage_file.open() as f:
        coverage_data = json.load(f)

    print("\n" + "=" * 80)
    print("Component Coverage Analysis")
    print("=" * 80 + "\n")

    # Definecomponent paths
    components = {
        "Channel Specification": [
            "blinkb0t/core/domains/sequencing/channels/models.py",
        ],
        "Channel Libraries": [
            "blinkb0t/core/domains/sequencing/channels/libraries/shutter.py",
            "blinkb0t/core/domains/sequencing/channels/libraries/color.py",
            "blinkb0t/core/domains/sequencing/channels/libraries/gobo.py",
        ],
        "Channel Integration": [
            "blinkb0t/core/domains/sequencing/channels/pipeline/",
        ],
        "LLM Agent Extensions": [
            "blinkb0t/core/agents/moving_heads/context_shaper.py",
            "blinkb0t/core/agents/moving_heads/channel_validator.py",
            "blinkb0t/core/agents/moving_heads/heuristic_validator.py",
            "blinkb0t/core/agents/moving_heads/judge_critic.py",
        ],
        "Configuration Extensions": [
            "blinkb0t/core/config/models.py",
            "blinkb0t/core/config/loader.py",
        ],
        "Template Purity": [
            "blinkb0t/core/domains/sequencing/templates/purity_validator.py",
        ],
    }

    files = coverage_data.get("files", {})
    total_statements = 0
    total_covered = 0

    for component_name, paths in components.items():
        component_statements = 0
        component_covered = 0

        for path_pattern in paths:
            # Find matching files
            for file_path, file_data in files.items():
                if path_pattern in file_path or file_path.endswith(path_pattern):
                    summary = file_data.get("summary", {})
                    num_statements = summary.get("num_statements", 0)
                    covered_lines = summary.get("covered_lines", 0)

                    component_statements += num_statements
                    component_covered += covered_lines

        if component_statements > 0:
            coverage_pct = (component_covered / component_statements) * 100
            status = "✅" if coverage_pct >= 85 else "⚠️" if coverage_pct >= 70 else "❌"

            print(
                f"{status} {component_name:30} {coverage_pct:5.1f}% "
                f"({component_covered}/{component_statements} lines)"
            )

            total_statements += component_statements
            total_covered += component_covered

    if total_statements > 0:
        overall_pct = (total_covered / total_statements) * 100
        print(f"\n{'─' * 80}")
        print(f"{'Overall':30} {overall_pct:5.1f}% ({total_covered}/{total_statements} lines)")
        print(f"{'─' * 80}\n")

        if overall_pct >= 85:
            print("✅coverage exceeds 85% target - Excellent!")
        elif overall_pct >= 70:
            print("⚠️ coverage is good but below 85% target")
        else:
            print("❌coverage needs improvement (target: 85%)")


def main():
    """Main entry point."""
    print("Test Coverage Analysis")
    print("=" * 80 + "\n")

    # Run coverage
    result = run_coverage()

    if result is None:
        return 1

    # Analyzespecific coverage
    analyze_coverage()

    return 0


if __name__ == "__main__":
    sys.exit(main())
