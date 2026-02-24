#!/usr/bin/env python3
"""Combined validator for schema and prompt artifacts.

Usage examples:
    uv run python scripts/validation/validate_agent_artifacts.py --schemas
    uv run python scripts/validation/validate_agent_artifacts.py --prompts
    uv run python scripts/validation/validate_agent_artifacts.py --all
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Literal

ValidationCheck = Literal["schemas", "prompts"]


def selected_checks(
    *, run_schemas: bool, run_prompts: bool, run_all: bool
) -> tuple[ValidationCheck, ...]:
    """Return the validation checks to execute."""
    if run_all or (not run_schemas and not run_prompts):
        return ("schemas", "prompts")
    checks: list[ValidationCheck] = []
    if run_schemas:
        checks.append("schemas")
    if run_prompts:
        checks.append("prompts")
    return tuple(checks)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Validate agent schemas/prompts without making LLM calls"
    )
    parser.add_argument("--schemas", action="store_true", help="Run schema response validation")
    parser.add_argument("--prompts", action="store_true", help="Run prompt template validation")
    parser.add_argument("--all", action="store_true", help="Run both schema and prompt validation")
    parser.add_argument("--agent", type=str, help="Filter by agent name/type (passed through)")
    parser.add_argument("--artifacts", type=str, help="Artifacts path (schema validation only)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--samples-only",
        action="store_true",
        help="Validate only embedded schema samples (schema validation only)",
    )
    parser.add_argument(
        "--show-enums",
        action="store_true",
        help="Print prompt enum values (prompt validation only)",
    )
    return parser.parse_args()


def _build_command(check: ValidationCheck, args: argparse.Namespace, repo_root: Path) -> list[str]:
    """Build subprocess command for an underlying validator."""
    if check == "schemas":
        script_path = repo_root / "scripts" / "validation" / "test_schema_validation.py"
        command = [sys.executable, str(script_path)]
        if args.agent:
            command.extend(["--agent", args.agent])
        if args.artifacts:
            command.extend(["--artifacts", args.artifacts])
        if args.verbose:
            command.append("--verbose")
        if args.samples_only:
            command.append("--samples-only")
        return command

    script_path = repo_root / "scripts" / "validation" / "test_prompt_validation.py"
    command = [sys.executable, str(script_path)]
    if args.agent:
        command.extend(["--agent", args.agent])
    if args.verbose:
        command.append("--verbose")
    if args.show_enums:
        command.append("--show-enums")
    return command


def main() -> int:
    """CLI entry point."""
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    checks = selected_checks(
        run_schemas=args.schemas,
        run_prompts=args.prompts,
        run_all=args.all,
    )

    if (args.artifacts or args.samples_only) and "schemas" not in checks:
        print("Note: --artifacts/--samples-only only apply to schema validation and were ignored.")
    if args.show_enums and "prompts" not in checks:
        print("Note: --show-enums only applies to prompt validation and was ignored.")

    exit_code = 0
    for check in checks:
        command = _build_command(check, args, repo_root)
        print(f"\n=== Running {check} validation ===")
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            exit_code = result.returncode

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
