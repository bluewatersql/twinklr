"""Shared display-element type identification.

The corpus propensity miner and catalog coverage report both use this module so
their model-type identities cannot drift apart.
"""

from __future__ import annotations

import re

# Known model type patterns in target names (order matters — first match wins).
MODEL_TYPE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("megatree", r"mega\s*tree"),
    ("matrix", r"matrix"),
    ("arch", r"arch"),
    ("candy_cane", r"candy\s*cane"),
    ("snowflake", r"snowflake"),
    ("wreath", r"wreath"),
    ("star", r"star"),
    ("icicle", r"icicle"),
    ("spiral", r"spiral"),
    ("mini_tree", r"mini\s*tree"),
    ("fence", r"fence"),
    ("roofline", r"roof\s*line"),
    ("window", r"window"),
    ("bush", r"bush"),
    ("pillar", r"pillar"),
    ("stake", r"stake"),
    ("spinner", r"spinner"),
    ("flood", r"flood"),
    ("pixel_tree", r"pixel\s*tree"),
)


def extract_model_type(value: str) -> str | None:
    """Return the first matching canonical type for a free-text model name."""
    normalized = value.lower().strip()
    for model_type, pattern in MODEL_TYPE_PATTERNS:
        if re.search(pattern, normalized):
            return model_type
    return None
