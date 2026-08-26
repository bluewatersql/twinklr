#!/usr/bin/env python3
"""Validate an owner-local MH corpus prerequisite without parsing corpus content."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from pydantic import ValidationError

from twinklr.core.feature_engineering.mh_corpus_manifest import validate_mh_corpus_manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--p2k-evidence", type=Path, required=True)
    parser.add_argument("--evidence-out", type=Path, required=True)
    parser.add_argument(
        "--require-sufficient",
        action="store_true",
        help="Fail unless the owner declared sufficient and all declared minima are met.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        evidence = validate_mh_corpus_manifest(
            args.manifest,
            p2k_evidence_path=args.p2k_evidence,
            evidence_path=args.evidence_out,
            require_sufficient=args.require_sufficient,
            repository_root=Path(__file__).resolve().parents[1],
        )
    except (ValueError, ValidationError) as error:
        print(f"MH corpus manifest rejected: {error}", file=sys.stderr)
        return 2
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
