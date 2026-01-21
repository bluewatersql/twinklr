"""Fixture utility functions.

Common utilities for working with fixture IDs and semantic groupings.
"""

from __future__ import annotations


def build_semantic_groups(fixture_ids: list[str]) -> dict[str, list[str]]:
    """Build semantic group mappings from fixture IDs.

    Args:
        fixture_ids: List of fixture IDs (e.g. ["MH1", "MH2", "MH3", "MH4"])

    Returns:
        Semantic group name -> list of semantic targets (ALL/MH1..MHN).
        Used for planning richness only; applier resolves to real xLights models later.

    Example:
        >>> build_semantic_groups(["MH1", "MH2", "MH3", "MH4"])
        {
            "ALL": ["MH1", "MH2", "MH3", "MH4"],
            "LEFT": ["MH1", "MH2"],
            "RIGHT": ["MH3", "MH4"],
            "ODD": ["MH1", "MH3"],
            "EVEN": ["MH2", "MH4"],
            "CENTER": ["MH2", "MH3"],
            "OUTER": ["MH1", "MH4"],
            "INNER": ["MH2", "MH3"]
        }
    """
    n = len(fixture_ids)
    mh_ids = fixture_ids

    groups: dict[str, list[str]] = {}

    # Always provide ALL
    groups["ALL"] = mh_ids

    # Infer basic groups
    if n >= 2:
        # LEFT/RIGHT: split array in half
        groups["LEFT"] = mh_ids[: n // 2]
        groups["RIGHT"] = mh_ids[n // 2 :]

        # ODD/EVEN: alternate fixtures (MH1/MH3/... vs MH2/MH4/...)
        groups["ODD"] = mh_ids[0::2]  # indices 0, 2, 4, ... (MH1, MH3, MH5, ...)
        groups["EVEN"] = mh_ids[1::2]  # indices 1, 3, 5, ... (MH2, MH4, MH6, ...)

        if n >= 4:
            # CENTER: middle 50% (25:50:25 split)
            left_edge = n // 4
            right_edge = n - (n // 4)  # or equivalently: 3 * n // 4, but this is clearer
            groups["CENTER"] = mh_ids[left_edge:right_edge]

            # OUTER: outer 25% (first and last quarters)
            outer_count = max(1, n // 4)
            groups["OUTER"] = mh_ids[:outer_count] + mh_ids[n - outer_count :]

            # INNER: middle third (33:33:33 split)
            if n >= 6:  # Only meaningful for 6+ fixtures
                inner_left = n // 3
                inner_right = n - (n // 3)  # or equivalently: 2 * n // 3
                groups["INNER"] = mh_ids[inner_left:inner_right]
            else:
                # If there are 4 fixtures, INNER is the same as CENTER
                groups["INNER"] = groups["CENTER"]

    return groups
