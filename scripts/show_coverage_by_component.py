#!/usr/bin/env python3
"""Show test coverage breakdown by major component.

This script analyzes coverage.json and provides a hierarchical view
of test coverage organized by major system components.

Usage:
    uv run python scripts/show_coverage_by_component.py
    uv run python scripts/show_coverage_by_component.py --detailed
    uv run python scripts/show_coverage_by_component.py --threshold 80
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any


@dataclass
class FileCoverage:
    """Coverage stats for a single file."""

    path: str
    covered_lines: int
    total_lines: int
    missing_lines: int
    percentage: float

    def __str__(self) -> str:
        status = "✓" if self.percentage >= 80 else "⚠" if self.percentage >= 65 else "✗"
        return f"{status} {self.path}: {self.percentage:5.1f}% ({self.covered_lines}/{self.total_lines})"


@dataclass
class ComponentCoverage:
    """Coverage stats for a component (group of related files)."""

    name: str
    files: list[FileCoverage]
    total_covered: int
    total_lines: int
    percentage: float

    @property
    def file_count(self) -> int:
        return len(self.files)

    def __str__(self) -> str:
        status = "✓" if self.percentage >= 80 else "⚠" if self.percentage >= 65 else "✗"
        return (
            f"{status} {self.name}: {self.percentage:5.1f}% "
            f"({self.total_covered}/{self.total_lines} lines, {self.file_count} files)"
        )


def parse_coverage_json(coverage_path: Path) -> dict[str, Any]:
    """Load and parse coverage.json file."""
    if not coverage_path.exists():
        print(f"Error: Coverage file not found at {coverage_path}")
        print("Run 'make test' or 'uv run pytest --cov' first to generate coverage data")
        sys.exit(1)

    with coverage_path.open() as f:
        return json.load(f)


def extract_file_coverage(file_path: str, file_data: dict[str, Any]) -> FileCoverage:
    """Extract coverage stats for a single file."""
    summary = file_data.get("summary", {})
    covered_lines = summary.get("covered_lines", 0)
    total_lines = summary.get("num_statements", 0)
    missing_lines = summary.get("missing_lines", 0)

    percentage = (covered_lines / total_lines * 100) if total_lines > 0 else 0.0

    return FileCoverage(
        path=file_path,
        covered_lines=covered_lines,
        total_lines=total_lines,
        missing_lines=missing_lines,
        percentage=percentage,
    )


def categorize_file(file_path: str) -> str:
    """Determine which major component a file belongs to."""
    # Normalize path separators
    path = file_path.replace("\\", "/")

    # Check if it's a twinklr core package file
    if "twinklr/core/" not in path:
        return "other"

    # Extract the part after twinklr/core/
    after_core = path.split("twinklr/core/")[1]
    parts = after_core.split("/")

    if not parts:
        return "other"

    component = parts[0]

    # Major components at top level
    major_components = [
        "agents",
        "audio",
        "sequencer",
        "curves",
        "formats",
        "config",
        "api",
        "utils",
        "parsers",
        "resolvers",
    ]

    # Handle domains/ subfolder - look one level deeper
    if component == "domains" and len(parts) > 1:
        subcomponent = parts[1]
        if subcomponent in major_components:
            return subcomponent
        return f"domains/{subcomponent}"

    # Handle infrastructure/ subfolder
    if component == "infrastructure" and len(parts) > 1:
        subcomponent = parts[1]
        if subcomponent in major_components:
            return subcomponent
        return f"infrastructure/{subcomponent}"

    if component in major_components:
        return component

    # For session.py and other top-level files
    if component.endswith(".py"):
        return component

    return f"other/{component}"


def group_by_component(coverage_data: dict[str, Any]) -> dict[str, list[FileCoverage]]:
    """Group file coverage data by major component."""
    files = coverage_data.get("files", {})
    components: dict[str, list[FileCoverage]] = defaultdict(list)

    for file_path, file_data in files.items():
        # Skip test files and __init__.py
        if "/tests/" in file_path or file_path.endswith("__init__.py"):
            continue

        coverage = extract_file_coverage(file_path, file_data)

        # Skip files with no executable lines
        if coverage.total_lines == 0:
            continue

        component = categorize_file(file_path)
        components[component].append(coverage)

    return components


def calculate_component_coverage(
    component_name: str, files: list[FileCoverage]
) -> ComponentCoverage:
    """Calculate aggregate coverage for a component."""
    total_covered = sum(f.covered_lines for f in files)
    total_lines = sum(f.total_lines for f in files)
    percentage = (total_covered / total_lines * 100) if total_lines > 0 else 0.0

    # Sort files by coverage percentage (lowest first)
    sorted_files = sorted(files, key=lambda f: f.percentage)

    return ComponentCoverage(
        name=component_name,
        files=sorted_files,
        total_covered=total_covered,
        total_lines=total_lines,
        percentage=percentage,
    )


def print_summary(components: dict[str, ComponentCoverage], show_detailed: bool = False) -> None:
    """Print coverage summary by component."""
    print("\n" + "=" * 80)
    print("TEST COVERAGE BY COMPONENT")
    print("=" * 80 + "\n")

    # Sort components by name
    sorted_components = sorted(components.items(), key=lambda x: x[0])

    # Calculate overall stats
    total_covered = sum(c.total_covered for c in components.values())
    total_lines = sum(c.total_lines for c in components.values())
    overall_percentage = (total_covered / total_lines * 100) if total_lines > 0 else 0.0

    # Print component summaries
    for _, component in sorted_components:
        print(component)

        if show_detailed:
            # Show individual files, focusing on those with low coverage
            low_coverage_files = [f for f in component.files if f.percentage < 80]
            high_coverage_files = [f for f in component.files if f.percentage >= 80]

            if low_coverage_files:
                print("\n  Files needing attention (< 80%):")
                for file in low_coverage_files[:10]:  # Show top 10 worst
                    print(f"    {file}")

            if show_detailed and high_coverage_files:
                print(f"\n  Well-covered files: {len(high_coverage_files)}")

            print()

    # Print overall summary
    print("=" * 80)
    status = "✓" if overall_percentage >= 80 else "⚠" if overall_percentage >= 65 else "✗"
    print(f"{status} OVERALL: {overall_percentage:5.1f}% ({total_covered}/{total_lines} lines)")
    print("=" * 80 + "\n")

    # Print legend
    print("Legend:")
    print("  ✓ = >= 80% (Good)")
    print("  ⚠ = 65-79% (Acceptable)")
    print("  ✗ = < 65% (Needs Improvement)")
    print()


def print_needs_attention(
    components: dict[str, ComponentCoverage], threshold: float = 65.0
) -> None:
    """Print files/components that need attention."""
    print("\n" + "=" * 80)
    print(f"COMPONENTS BELOW {threshold}% COVERAGE")
    print("=" * 80 + "\n")

    needs_attention = [
        (name, comp) for name, comp in components.items() if comp.percentage < threshold
    ]

    if not needs_attention:
        print(f"✓ All components meet the {threshold}% coverage threshold!")
        return

    # Sort by percentage (lowest first)
    needs_attention.sort(key=lambda x: x[1].percentage)

    for component_name, component in needs_attention:
        print(f"\n{component_name}: {component.percentage:.1f}%")
        print(f"  Total: {component.total_covered}/{component.total_lines} lines")
        print(f"  Files: {component.file_count}")

        # Show worst files
        worst_files = component.files[:5]
        if worst_files:
            print("  Worst files:")
            for file in worst_files:
                print(f"    - {Path(file.path).name}: {file.percentage:.1f}%")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Show test coverage breakdown by major component")
    parser.add_argument(
        "--detailed",
        "-d",
        action="store_true",
        help="Show detailed file-level breakdown",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=65.0,
        help="Coverage threshold for highlighting (default: 65.0)",
    )
    parser.add_argument(
        "--coverage-file",
        "-f",
        type=Path,
        default=Path("coverage.json"),
        help="Path to coverage.json file (default: coverage.json)",
    )

    args = parser.parse_args()

    # Load coverage data
    coverage_data = parse_coverage_json(args.coverage_file)

    # Group by component
    component_files = group_by_component(coverage_data)

    # Calculate component coverage
    components = {
        name: calculate_component_coverage(name, files) for name, files in component_files.items()
    }

    # Print summary
    print_summary(components, show_detailed=args.detailed)

    # Print components needing attention
    if args.threshold > 0:
        print_needs_attention(components, threshold=args.threshold)


if __name__ == "__main__":
    main()
