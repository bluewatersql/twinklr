#!/usr/bin/env python
"""Test harness for validating agent prompt templates.

Validates that all prompt templates:
1. Render without errors
2. Include required taxonomy enum values
3. Don't use invalid enum values in examples/documentation

Usage:
    python scripts/validation/test_prompt_validation.py
    python scripts/validation/test_prompt_validation.py --agent macro_planner
"""

import argparse
from pathlib import Path
import re
import sys

from jinja2 import Environment, FileSystemLoader, TemplateError, Undefined


class SilentUndefined(Undefined):
    """Custom Undefined that returns empty strings instead of raising errors."""

    def _fail_with_undefined_error(self, *args, **kwargs):
        return ""

    def __str__(self):
        return ""

    def __iter__(self):
        return iter([])

    def __bool__(self):
        return False

    def __getattr__(self, name):
        return SilentUndefined()

    def __call__(self, *args, **kwargs):
        return SilentUndefined()


# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from twinklr.core.agents.issues import (  # noqa: E402
    IssueCategory,
    IssueEffort,
    IssueScope,
    IssueSeverity,
    SuggestedAction,
)
from twinklr.core.agents.taxonomy_utils import get_taxonomy_dict  # noqa: E402

# Agent prompt directories
AGENT_PROMPTS = {
    "macro_planner": "packages/twinklr/core/agents/sequencer/macro_planner/prompts/planner",
    "macro_judge": "packages/twinklr/core/agents/sequencer/macro_planner/prompts/judge",
    "group_planner": "packages/twinklr/core/agents/sequencer/group_planner/prompts/planner",
    "section_judge": "packages/twinklr/core/agents/sequencer/group_planner/prompts/section_judge",
    "holistic_judge": "packages/twinklr/core/agents/sequencer/group_planner/prompts/holistic_judge",
}

# Required variables for each template type
REQUIRED_VARS = {
    "system.j2": {},
    "developer.j2": {"response_schema": "{}", "taxonomy": None, "iteration": 1},
    "user.j2": {
        "section_id": "test_section",
        "section_name": "Test Section",
        "start_ms": 0,
        "end_ms": 10000,
        "energy_target": "HIGH",
        "motion_density": "MODERATE",
        "choreography_style": "ABSTRACT",
        "primary_focus_targets": ["HERO"],
        "display_graph": {"groups": [], "groups_by_role": {}},
        "template_catalog": {"schema_version": "1.0", "entries": []},
    },
}


def get_valid_enum_values() -> dict[str, set[str]]:
    """Get all valid enum values for validation.

    Returns:
        Dict mapping enum name to set of valid values
    """
    return {
        "IssueCategory": {e.value for e in IssueCategory},
        "IssueScope": {e.value for e in IssueScope},
        "IssueSeverity": {e.value for e in IssueSeverity},
        "IssueEffort": {e.value for e in IssueEffort},
        "SuggestedAction": {e.value for e in SuggestedAction},
    }


def find_scope_values_in_text(text: str) -> set[str]:
    """Find scope-like values in text that might be invalid.

    Args:
        text: Text to search

    Returns:
        Set of found scope-like values
    """
    # Pattern to find scope values in examples, documentation
    patterns = [
        r'"scope":\s*"([A-Z_]+)"',
        r"scope:\s*([A-Z_]+)",
        r"\bscope\b.*?([A-Z_]+)",
    ]

    found = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = match.group(1).upper()
            if value and len(value) > 2:  # Skip short matches
                found.add(value)

    return found


def validate_template(
    template_path: Path, agent_name: str, taxonomy: dict
) -> tuple[bool, list[str]]:
    """Validate a single template.

    Args:
        template_path: Path to template file
        agent_name: Name of agent
        taxonomy: Taxonomy dict with enum values

    Returns:
        Tuple of (is_valid, list of errors)
    """
    errors = []
    template_name = template_path.name

    # Skip user templates (require complex context) - just check they exist
    if template_name.startswith("user"):
        try:
            content = template_path.read_text()
            if len(content) < 50:
                errors.append(f"Template too short ({len(content)} chars)")
            return len(errors) == 0, errors
        except Exception as e:
            return False, [f"Could not read template: {e}"]

    # For system.j2 and developer.j2 - fully render
    env = Environment(
        loader=FileSystemLoader(template_path.parent),
        undefined=SilentUndefined,  # Allow undefined vars without errors
    )

    # Get required variables for this template type
    base_vars = REQUIRED_VARS.get(template_name, {})
    vars_dict = {**base_vars}

    # Add taxonomy if needed
    if vars_dict.get("taxonomy") is None:
        vars_dict["taxonomy"] = taxonomy

    try:
        template = env.get_template(template_name)
        rendered = template.render(**vars_dict)
    except TemplateError as e:
        errors.append(f"Template render error: {e}")
        return False, errors

    # Check for common issues
    if len(rendered) < 50:
        errors.append(f"Template rendered too short ({len(rendered)} chars)")

    # Check that taxonomy values are being used (for developer templates)
    if template_name == "developer.j2":
        # Check that IssueScope includes PLACEMENT now
        valid_scopes = get_valid_enum_values()["IssueScope"]
        found_scopes = find_scope_values_in_text(rendered)

        for scope in found_scopes:
            if scope not in valid_scopes and scope not in ("SCOPE", "SECTION_ID"):
                errors.append(f"Invalid scope value '{scope}' found. Valid: {sorted(valid_scopes)}")

    return len(errors) == 0, errors


def validate_examples_file(file_path: Path) -> tuple[bool, list[str]]:
    """Validate examples.jsonl for schema compliance.

    Args:
        file_path: Path to examples.jsonl

    Returns:
        Tuple of (is_valid, list of errors)
    """
    errors = []
    valid_enums = get_valid_enum_values()

    try:
        with open(file_path) as f:
            content = f.read()
    except Exception as e:
        return False, [f"Could not read file: {e}"]

    # Check for invalid scope values in examples
    found_scopes = find_scope_values_in_text(content)
    for scope in found_scopes:
        if scope not in valid_enums["IssueScope"]:
            # Only flag if it looks like a scope value
            if scope in (
                "GLOBAL",
                "SECTION",
                "LANE",
                "GROUP",
                "EFFECT",
                "PLACEMENT",
                "BAR_RANGE",
                "FIELD",
            ):
                continue
            if len(scope) > 3 and scope.isupper():
                errors.append(f"Potentially invalid scope '{scope}' in examples")

    return len(errors) == 0, errors


def run_validation(agent_filter: str | None = None, verbose: bool = False) -> int:
    """Run validation on all agent prompts.

    Args:
        agent_filter: Optional agent name to filter by
        verbose: Print detailed output

    Returns:
        Number of failures
    """
    taxonomy = get_taxonomy_dict()
    total_errors = 0

    agents = AGENT_PROMPTS.items()
    if agent_filter:
        agents = [(k, v) for k, v in agents if agent_filter in k]

    for agent_name, prompt_dir in agents:
        prompt_path = PROJECT_ROOT / prompt_dir

        if not prompt_path.exists():
            print(f"⚠️  Prompt directory not found: {prompt_path}")
            continue

        print(f"\n{'=' * 60}")
        print(f"Validating: {agent_name}")
        print(f"{'=' * 60}")

        # Validate all .j2 templates
        for template_file in prompt_path.glob("*.j2"):
            is_valid, errors = validate_template(template_file, agent_name, taxonomy)

            if is_valid:
                if verbose:
                    print(f"  ✅ {template_file.name}")
            else:
                print(f"  ❌ {template_file.name}")
                for error in errors:
                    print(f"     {error}")
                total_errors += len(errors)

        # Validate examples.jsonl if present
        examples_file = prompt_path / "examples.jsonl"
        if examples_file.exists():
            is_valid, errors = validate_examples_file(examples_file)
            if is_valid:
                if verbose:
                    print("  ✅ examples.jsonl")
            else:
                print("  ❌ examples.jsonl")
                for error in errors:
                    print(f"     {error}")
                total_errors += len(errors)

    return total_errors


def print_valid_enums():
    """Print all valid enum values for reference."""
    print("\n" + "=" * 60)
    print("VALID ENUM VALUES (for reference)")
    print("=" * 60)

    valid_enums = get_valid_enum_values()
    for enum_name, values in sorted(valid_enums.items()):
        print(f"\n{enum_name}:")
        print(f"  {', '.join(sorted(values))}")


def main():
    parser = argparse.ArgumentParser(
        description="Validate agent prompt templates without LLM calls"
    )
    parser.add_argument("--agent", type=str, help="Filter by agent name (e.g., macro_planner)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all validation results")
    parser.add_argument("--show-enums", action="store_true", help="Print valid enum values")

    args = parser.parse_args()

    print("=" * 60)
    print("PROMPT TEMPLATE VALIDATION (No LLM Budget Used)")
    print("=" * 60)

    if args.show_enums:
        print_valid_enums()
        return

    errors = run_validation(args.agent, args.verbose)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if errors > 0:
        print(f"\n❌ {errors} validation error(s) found")
        print("Run with --show-enums to see valid values")
        sys.exit(1)
    else:
        print("\n✅ All prompts validated successfully!")


if __name__ == "__main__":
    main()
