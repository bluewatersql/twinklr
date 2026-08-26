"""Owner-only command-line entry point for the P3-T4 macro live probe."""

from __future__ import annotations

import argparse
import asyncio
from decimal import Decimal
import json
import os
from pathlib import Path
import sys

from twinklr.core.agents.sequencer.macro_planner.live_probe import (
    DEFAULT_FIXTURE,
    ProbePreflightError,
    ProbeRequest,
    run_probe,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Owner-only P3-T4 macro live probe")
    parser.add_argument("--live", action="store_true", help="explicitly authorize one paid request")
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--expected-source-tree-hash", required=True)
    parser.add_argument("--expected-input-hash", required=True)
    parser.add_argument("--expected-catalog-hash", required=True)
    parser.add_argument("--expected-request-hash", required=True)
    parser.add_argument("--authorization-id", required=True)
    parser.add_argument("--expected-prior-ledger-hash", required=True)
    parser.add_argument("--expected-prior-attempt-hash", required=True)
    parser.add_argument("--preauthorize-usd", type=Decimal, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = _parser().parse_args(argv)
    repo_root = Path.cwd()
    fixture = repo_root / DEFAULT_FIXTURE
    request = ProbeRequest(
        repo_root=repo_root,
        fixture=fixture,
        expected_source_sha=args.expected_source_sha,
        expected_source_tree_hash=args.expected_source_tree_hash,
        expected_input_hash=args.expected_input_hash,
        expected_catalog_hash=args.expected_catalog_hash,
        expected_request_hash=args.expected_request_hash,
        authorization_id=args.authorization_id,
        expected_prior_ledger_hash=args.expected_prior_ledger_hash,
        expected_prior_attempt_hash=args.expected_prior_attempt_hash,
        preauthorize_usd=args.preauthorize_usd,
        opt_in=args.live,
        api_key=os.getenv("OPENAI_API_KEY"),
        command=[sys.executable, "-m", __name__, *argv],
    )
    try:
        attempt = asyncio.run(run_probe(request))
    except ProbePreflightError as exc:
        print(f"P3-T4 probe rejected before provider call: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(attempt, sort_keys=True))
    return 0 if attempt["outcome"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
