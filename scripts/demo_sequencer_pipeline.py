#!/usr/bin/env python3
"""Compatibility shim for the former display demo.

The production CLI now owns display wiring. This script deliberately has no second
pipeline definition; existing callers are forwarded to ``twinklr display``.
"""

from __future__ import annotations

import sys

from twinklr.cli.main import main

if __name__ == "__main__":
    sys.argv.insert(1, "display")
    main()
