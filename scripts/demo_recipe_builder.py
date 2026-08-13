#!/usr/bin/env python3
"""DEPRECATED shim — use ``twinklr curate-catalog`` instead.

The recipe_builder curation workflow this script used to own directly is now
a first-class ``twinklr`` CLI subcommand
(``packages/twinklr/cli/recipe_builder_cmd.py``). This script forwards its
arguments unchanged to ``twinklr curate-catalog`` so existing invocations of
``python scripts/demo_recipe_builder.py [flags]`` keep working, but it no
longer contains any pipeline logic itself.

Usage (unchanged from before, now delegating to the CLI):
    uv run python scripts/demo_recipe_builder.py --dry-run
    uv run twinklr curate-catalog --dry-run   # equivalent, preferred
"""

from __future__ import annotations

import sys

from twinklr.cli.main import main as _cli_main


def main() -> None:
    print(
        "WARNING: scripts/demo_recipe_builder.py is deprecated — "
        "use `twinklr curate-catalog` instead.",
        file=sys.stderr,
    )
    sys.argv = [sys.argv[0], "curate-catalog", *sys.argv[1:]]
    _cli_main()


if __name__ == "__main__":
    main()
