#!/usr/bin/env python
"""Test harness for validating LLM responses against schemas.

Validates saved LLM responses from artifacts/data folders without calling LLM.
Use this to catch schema drift and prompt issues before spending LLM budget.

Usage:
    # Validate all cached responses
    python scripts/validation/test_schema_validation.py

    # Validate specific agent type
    python scripts/validation/test_schema_validation.py --agent section_judge

    # Validate specific artifact directory
    python scripts/validation/test_schema_validation.py --artifacts artifacts/02_rudolph_the_red_nosed_reindeer
"""

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from pydantic import ValidationError

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from twinklr.core.agents.issues import Issue  # noqa: E402
from twinklr.core.agents.sequencer.group_planner.holistic import (  # noqa: E402
    HolisticEvaluation,
)
from twinklr.core.agents.shared.judge.models import JudgeVerdict  # noqa: E402
from twinklr.core.sequencer.planning import (  # noqa: E402
    MacroPlan,
    SectionCoordinationPlan,
)

# Map agent names to their response models
AGENT_MODELS: dict[str, type] = {
    "macro_planner": MacroPlan,
    "macro_judge": JudgeVerdict,
    "section_planner": SectionCoordinationPlan,
    "section_judge": JudgeVerdict,
    "holistic_judge": HolisticEvaluation,
}


def find_llm_responses(base_path: Path, agent_filter: str | None = None) -> list[Path]:
    """Find all LLM response files in artifacts/data directories.

    Args:
        base_path: Base path to search
        agent_filter: Optional agent name to filter by

    Returns:
        List of paths to JSON/YAML files containing LLM responses
    """
    patterns = ["**/llm_calls/*.json", "**/llm_calls/*.yaml", "**/checkpoints/**/*.json"]
    files = []

    for pattern in patterns:
        for file in base_path.glob(pattern):
            if agent_filter:
                if agent_filter.lower() in file.stem.lower():
                    files.append(file)
            else:
                files.append(file)

    return sorted(files)


def extract_response_content(file_path: Path) -> dict[str, Any] | None:
    """Extract LLM response content from a file.

    Handles both raw JSON responses and wrapped log formats.

    Args:
        file_path: Path to response file

    Returns:
        Parsed response dict or None if not parseable
    """
    try:
        with file_path.open() as f:
            content = f.read()

        # Try JSON first
        if file_path.suffix == ".json":
            data = json.loads(content)

            # If it's a wrapped format with 'response' key
            if isinstance(data, dict) and "response" in data:
                return data["response"]

            # If it's a raw response
            return data

        # Try YAML
        if file_path.suffix in (".yaml", ".yml"):
            import yaml

            data = yaml.safe_load(content)
            if isinstance(data, dict) and "response" in data:
                return data["response"]
            return data

        return None
    except Exception:
        return None


def detect_agent_type(file_path: Path, response: dict[str, Any]) -> str | None:
    """Detect agent type from file path or response content.

    Args:
        file_path: Path to response file
        response: Parsed response dict

    Returns:
        Agent type name or None if unknown
    """
    path_str = str(file_path).lower()

    # Check path for agent type hints
    if "macro" in path_str and "judge" in path_str:
        return "macro_judge"
    if "macro" in path_str and "planner" in path_str:
        return "macro_planner"
    if "section" in path_str and "judge" in path_str:
        return "section_judge"
    if "section" in path_str and "planner" in path_str:
        return "section_planner"
    if "holistic" in path_str:
        return "holistic_judge"

    # Check response structure for clues
    if "section_plans" in response:
        return "macro_planner"
    if "lane_plans" in response:
        return "section_planner"
    if "status" in response and "score" in response:
        if "cross_section_issues" in response:
            return "holistic_judge"
        return "section_judge"  # or macro_judge, same model

    return None


def validate_response(response: dict[str, Any], agent_type: str) -> tuple[bool, list[str]]:
    """Validate a response against the agent's schema.

    Args:
        response: Parsed response dict
        agent_type: Agent type name

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    model_class = AGENT_MODELS.get(agent_type)
    if not model_class:
        return False, [f"Unknown agent type: {agent_type}"]

    try:
        model_class.model_validate(response)
        return True, []
    except ValidationError as e:
        errors = []
        for error in e.errors():
            loc = ".".join(str(x) for x in error["loc"])
            msg = error["msg"]
            errors.append(f"  - {loc}: {msg}")
        return False, errors


def validate_issue_standalone(issue_data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate an issue dict against the Issue model.

    Args:
        issue_data: Issue dict from response

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    try:
        Issue.model_validate(issue_data)
        return True, []
    except ValidationError as e:
        errors = []
        for error in e.errors():
            loc = ".".join(str(x) for x in error["loc"])
            msg = error["msg"]
            errors.append(f"  - {loc}: {msg}")
        return False, errors


def run_validation(
    base_paths: list[Path], agent_filter: str | None = None, verbose: bool = False
) -> tuple[int, int, int]:
    """Run validation on all found responses.

    Args:
        base_paths: Paths to search for responses
        agent_filter: Optional agent name to filter by
        verbose: Print detailed output

    Returns:
        Tuple of (total, passed, failed)
    """
    total = 0
    passed = 0
    failed = 0

    for base_path in base_paths:
        if not base_path.exists():
            if verbose:
                print(f"⚠️  Path not found: {base_path}")
            continue

        files = find_llm_responses(base_path, agent_filter)

        for file_path in files:
            response = extract_response_content(file_path)
            if response is None:
                continue

            agent_type = detect_agent_type(file_path, response)
            if agent_type is None:
                if verbose:
                    print(f"⚠️  Unknown agent type: {file_path}")
                continue

            total += 1
            is_valid, errors = validate_response(response, agent_type)

            if is_valid:
                passed += 1
                if verbose:
                    print(f"✅ {file_path.name} ({agent_type})")
            else:
                failed += 1
                print(f"❌ {file_path.name} ({agent_type})")
                for error in errors:
                    print(error)
                print()

    return total, passed, failed


def validate_sample_responses():
    """Validate sample responses embedded in this file.

    These are known good/bad responses to test schema validation.
    """
    print("=" * 60)
    print("SAMPLE RESPONSE VALIDATION")
    print("=" * 60)

    # Sample section_judge response with PLACEMENT scope (should now pass)
    sample_judge_response = {
        "status": "APPROVE",
        "score": 7.3,
        "confidence": 0.8,
        "strengths": ["Good foundation"],
        "issues": [
            {
                "issue_id": "TEST_ISSUE",
                "category": "STYLE",
                "severity": "NIT",
                "estimated_effort": "LOW",
                "scope": "PLACEMENT",  # Was failing, now valid
                "location": {"section_id": "intro_0"},
                "rule": "DON'T test - this is a sample issue",
                "message": "Test message",
                "fix_hint": "Test fix",
                "acceptance_test": "Test passes",
                "suggested_action": "PATCH",
            }
        ],
        "overall_assessment": "Test assessment",
        "feedback_for_planner": "Test feedback",
        "score_breakdown": {"test": 7.0},
        "iteration": 1,
    }

    is_valid, errors = validate_response(sample_judge_response, "section_judge")
    if is_valid:
        print("✅ Sample section_judge with PLACEMENT scope: PASSED")
    else:
        print("❌ Sample section_judge with PLACEMENT scope: FAILED")
        for error in errors:
            print(error)

    # Test Issue model standalone
    sample_issue = {
        "issue_id": "TEST",
        "category": "TIMING",
        "severity": "WARN",
        "estimated_effort": "LOW",
        "scope": "SECTION",
        "location": {},
        "rule": "DON'T test - sample rule",
        "message": "Test message",
        "fix_hint": "Fix it",
        "acceptance_test": "It passes",
        "suggested_action": "PATCH",
    }

    is_valid, errors = validate_issue_standalone(sample_issue)
    if is_valid:
        print("✅ Sample Issue model: PASSED")
    else:
        print("❌ Sample Issue model: FAILED")
        for error in errors:
            print(error)

    # Test HolisticEvaluation with score_breakdown
    sample_holistic = {
        "status": "APPROVE",
        "score": 7.8,
        "score_breakdown": {
            "story_coherence": 8.3,
            "energy_arc": 7.6,
            "visual_variety": 7.2,
        },
        "confidence": 0.72,
        "summary": "Test summary",
        "strengths": ["Good flow"],
        "cross_section_issues": [],
        "recommendations": ["Add variety"],
    }

    try:
        HolisticEvaluation.model_validate(sample_holistic)
        print("✅ Sample HolisticEvaluation with score_breakdown: PASSED")
    except Exception as e:
        print(f"❌ Sample HolisticEvaluation with score_breakdown: FAILED - {e}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Validate LLM responses against schemas without LLM calls"
    )
    parser.add_argument("--agent", type=str, help="Filter by agent type (e.g., section_judge)")
    parser.add_argument("--artifacts", type=str, help="Path to artifacts directory to validate")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all validation results")
    parser.add_argument(
        "--samples-only",
        action="store_true",
        help="Only validate embedded sample responses",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("LLM RESPONSE SCHEMA VALIDATION (No LLM Budget Used)")
    print("=" * 60)
    print()

    # Always run sample validation first
    validate_sample_responses()

    if args.samples_only:
        return

    # Determine paths to search
    if args.artifacts:
        base_paths = [Path(args.artifacts)]
    else:
        base_paths = [
            PROJECT_ROOT / "artifacts",
            PROJECT_ROOT / "data" / "cache" / "llm",
            PROJECT_ROOT / "data" / "cache" / "agents",
        ]

    print("=" * 60)
    print("CACHED RESPONSE VALIDATION")
    print("=" * 60)
    print(f"Searching: {[str(p) for p in base_paths]}")
    print()

    total, passed, failed = run_validation(base_paths, args.agent, args.verbose)

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total responses validated: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed > 0:
        print("\n⚠️  Some responses failed validation. Check schema alignment.")
        sys.exit(1)
    elif total == 0:
        print("\nℹ️  No responses found to validate.")
    else:
        print("\n✅ All responses passed validation!")


if __name__ == "__main__":
    main()
