"""Builtin motif definitions.

Builds motif catalog from registered tag definitions (motif.* tags) with
curated metadata overrides for planner/judge guidance.

Design:
- Motifs are structured (stable IDs + controlled tags), not prose-only.
- Catalog is complete by construction (derived from TAG_REGISTRY).
- Overrides provide optional energy preferences and usage notes.

Usage:
- MacroPlanner: Reference motifs by motif_id (stable).
- Section/Group planners: Expand motif_ids -> tags for template matching.
- Validators/Judges: Enforce motif_id validity + recurrence/coverage rules.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from twinklr.core.sequencer.theming.catalog import MOTIF_REGISTRY, TAG_REGISTRY
from twinklr.core.sequencer.theming.enums import TagCategory
from twinklr.core.sequencer.theming.models import MotifDefinition
from twinklr.core.sequencer.vocabulary.energy import EnergyTarget

# =============================================================================
# Curated overrides for motif metadata
# =============================================================================
# Keys are motif_id (tag without "motif." prefix)
# Values: preferred_energy, usage_notes, additional tags, description override
MOTIF_OVERRIDES: dict[str, dict[str, Any]] = {
    "abstract": {
        "preferred_energy": [EnergyTarget.MED],
        "usage_notes": "Non-representational visuals (shapes/patterns), no literal objects. Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "geometric": {
        "preferred_energy": [EnergyTarget.MED],
        "usage_notes": "Geometric shapes and structured patterns. Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "spiral": {
        "preferred_energy": [EnergyTarget.MED, EnergyTarget.HIGH],
        "usage_notes": "Spiral pattern with continuous curves; good for polar mapping. Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability. Favor continuous bands for polar mapping; ensure smooth wrap with no seams.",
    },
    "helix": {
        "preferred_energy": [EnergyTarget.MED, EnergyTarget.HIGH],
        "usage_notes": "Helical wrap / corkscrew banding (mega-tree friendly). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability. Favor continuous bands for polar mapping; ensure smooth wrap with no seams.",
    },
    "radial_rays": {
        "preferred_energy": [EnergyTarget.MED, EnergyTarget.HIGH],
        "usage_notes": "Radial rays / spokes from a center (starburst-like). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "concentric_rings": {
        "preferred_energy": [EnergyTarget.MED, EnergyTarget.HIGH],
        "usage_notes": "Concentric circles/rings expanding from center. Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "wave_bands": {
        "preferred_energy": [EnergyTarget.MED, EnergyTarget.HIGH],
        "usage_notes": "Waves as large bands/stripes (sinusoidal feel). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "zigzag": {
        "preferred_energy": [EnergyTarget.MED, EnergyTarget.HIGH],
        "usage_notes": "Zig-zag bands (not too dense). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "chevrons": {
        "preferred_energy": [EnergyTarget.MED, EnergyTarget.HIGH],
        "usage_notes": "Chevron patterns (large, rhythmic). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "stripes": {
        "preferred_energy": [EnergyTarget.MED, EnergyTarget.HIGH],
        "usage_notes": "Bold stripes/bands (clean edges, simple). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "gradient_bands": {
        "preferred_energy": [EnergyTarget.MED, EnergyTarget.HIGH],
        "usage_notes": "Large gradient bands (few stops, not muddy). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "grid": {
        "preferred_energy": [EnergyTarget.MED, EnergyTarget.HIGH],
        "usage_notes": "Grid/cell structure (blocky tiles). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "checker": {
        "preferred_energy": [EnergyTarget.MED, EnergyTarget.HIGH],
        "usage_notes": "Checkerboard pattern (large squares, high contrast). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "dots": {
        "preferred_energy": [EnergyTarget.MED],
        "usage_notes": "Large dots/blobs (sparse, legible). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "confetti": {
        "preferred_energy": [EnergyTarget.MED],
        "usage_notes": "Simple confetti bits (large, sparse, clean). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "particles": {
        "preferred_energy": [EnergyTarget.MED],
        "usage_notes": "Particle field with controlled density (not noisy). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "bokeh": {
        "preferred_energy": [EnergyTarget.LOW, EnergyTarget.MED],
        "usage_notes": "Soft bokeh circles/blobs (large, uncluttered). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "sparkles": {
        "preferred_energy": [EnergyTarget.MED, EnergyTarget.HIGH],
        "usage_notes": "Sparkle/glint accents (large, sparse; avoid tiny stars). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability. Best as accents/highlights; keep sparkles large and sparse.",
    },
    "stars": {
        "preferred_energy": [EnergyTarget.MED, EnergyTarget.HIGH],
        "usage_notes": "Star shapes (simple, bold). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability. Best as accents/highlights; keep sparkles large and sparse.",
    },
    "light_trails": {
        "preferred_energy": [EnergyTarget.MED, EnergyTarget.HIGH],
        "usage_notes": "Light trail ribbons / streaks (clean, not smoky). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "ribbons": {
        "preferred_energy": [EnergyTarget.MED],
        "usage_notes": "Ribbon bands (broad, flowing, high readability). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "flares": {
        "preferred_energy": [EnergyTarget.HIGH],
        "usage_notes": "Lens flare-like blooms (controlled, not overdone). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability. Best as accents/highlights; keep sparkles large and sparse.",
    },
    "lightning": {
        "preferred_energy": [EnergyTarget.HIGH],
        "usage_notes": "Stylized lightning bolts (bold, simple silhouette). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "fire": {
        "preferred_energy": [EnergyTarget.HIGH],
        "usage_notes": "Stylized flame shapes (bold, simple, high contrast). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "ice": {
        "preferred_energy": [EnergyTarget.MED],
        "usage_notes": "Icy crystalline shapes (kept large and clean). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "crystals": {
        "preferred_energy": [EnergyTarget.MED],
        "usage_notes": "Geometric crystal shards (low detail, clean facets). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "clouds": {
        "preferred_energy": [EnergyTarget.LOW, EnergyTarget.MED],
        "usage_notes": "Simple cloud forms (not detailed, not foggy noise). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "smoke": {
        "preferred_energy": [EnergyTarget.LOW, EnergyTarget.MED],
        "usage_notes": "Stylized smoke wisps (simple, low noise). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "water": {
        "preferred_energy": [EnergyTarget.LOW, EnergyTarget.MED],
        "usage_notes": "Stylized water waves (simple bands, clean). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "cosmic": {
        "preferred_energy": [EnergyTarget.MED],
        "usage_notes": "Space/cosmic motifs (stars/nebula-like but simplified). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "snowflakes": {
        "preferred_energy": [EnergyTarget.MED],
        "usage_notes": "Snowflake shapes (simple, large, high contrast). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability. Keep snowflakes simple and oversized; limit count to avoid noise.",
    },
    "ornaments": {
        "preferred_energy": [EnergyTarget.MED],
        "usage_notes": "Simple ornament/bauble shapes (large, uncluttered). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability.",
    },
    "candy_stripes": {
        "preferred_energy": [EnergyTarget.MED],
        "usage_notes": "Candy-like stripes (no literal characters required). Use large, high-contrast forms; avoid fine detail; keep density controlled for LED readability. Prefer bold red/white (or theme palette) stripes; avoid tiny striping.",
    },
}


def _register_motifs() -> None:
    """Build and register motifs from TAG_REGISTRY.

    Derives motifs from motif.* tags and applies MOTIF_OVERRIDES
    for enhanced metadata.
    """
    import logging

    logger = logging.getLogger(__name__)

    # Collect all motif.* tags from TAG_REGISTRY
    motif_tags = TAG_REGISTRY.find_by_category(TagCategory.MOTIF)
    logger.debug(f"Found {len(motif_tags)} motif tags to register")

    for tag_info in motif_tags:
        # Get full tag definition
        tag_def = TAG_REGISTRY.get(tag_info.tag)

        # Extract motif_id from tag (remove "motif." prefix)
        if not tag_def.tag.startswith("motif."):
            continue

        motif_id = tag_def.tag.removeprefix("motif.")

        # Start with base data from tag definition
        base_data = {
            "motif_id": motif_id,
            "tags": [tag_def.tag],
            "description": tag_def.description or "",
            "preferred_energy": [],
            "usage_notes": "",
        }

        # Apply overrides if present
        override = MOTIF_OVERRIDES.get(motif_id, {})

        # Merge with explicit field handling for type safety
        motif_data = {
            "motif_id": base_data["motif_id"],
            "tags": base_data["tags"],
            "description": base_data["description"],
            "preferred_energy": base_data["preferred_energy"],
            "usage_notes": base_data["usage_notes"],
        }

        # Apply overrides
        for k, v in override.items():
            if k == "tags" and isinstance(v, list):
                # Additive: merge with base tags
                motif_data["tags"] = sorted(set(motif_data["tags"]) | set(v))
            elif k in motif_data:
                motif_data[k] = v  # type: ignore[literal-required]

        # Create and register motif definition
        motif = MotifDefinition(**motif_data)  # type: ignore[arg-type]

        # Validate that at least one motif.* tag is present
        if not any(t.startswith("motif.") for t in motif.tags):
            raise ValueError(
                f"MotifDefinition '{motif.motif_id}' tags must include at least one 'motif.*' tag"
            )

        MOTIF_REGISTRY.register(motif)


# =============================================================================
# Utility functions for planners/validators
# =============================================================================


def assert_valid_motif_ids(motif_ids: Iterable[str]) -> None:
    """Validate that all motif_ids exist in registry.

    Args:
        motif_ids: Motif identifiers to validate.

    Raises:
        ValueError: If any motif_id is not registered.
    """
    unknown = [m for m in motif_ids if not MOTIF_REGISTRY.has(m)]
    if unknown:
        raise ValueError(f"Unknown motif_id(s): {unknown}")


def expand_motif_ids_to_tags(motif_ids: Iterable[str]) -> list[str]:
    """Expand motif_ids to their template-matching tags.

    Args:
        motif_ids: Motif identifiers to expand.

    Returns:
        Deduplicated, sorted list of all tags from the motifs.

    Raises:
        ValueError: If any motif_id is invalid.
    """
    assert_valid_motif_ids(motif_ids)
    tags: set[str] = set()
    for mid in motif_ids:
        motif = MOTIF_REGISTRY.get(mid)
        tags.update(motif.tags)
    return sorted(tags)


def motif_ids_from_tags(tags: Iterable[str]) -> list[str]:
    """Extract motif_ids from tags.

    Best-effort mapping of motif.* tags -> motif_ids.

    Args:
        tags: Tags to extract motif_ids from.

    Returns:
        Sorted list of motif_ids found in tags.
    """
    out: set[str] = set()
    for t in tags:
        if isinstance(t, str) and t.startswith("motif."):
            motif_id = t.removeprefix("motif.")
            if MOTIF_REGISTRY.has(motif_id):
                out.add(motif_id)
    return sorted(out)


# NOTE: Auto-registration is deferred to builtins/__init__.py
# to ensure TAG_REGISTRY is fully populated first
