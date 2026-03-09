#!/usr/bin/env python3
"""Aggressive cleanup of display template library.

Removes stub motifs (On+hit_small/hit_big), consolidates duplicates,
replaces generic effects with real xLights effects, and rebuilds index.

Run from project root: python scripts/cleanup_display_templates.py
"""

import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "data" / "templates"
BUILTINS_DIR = TEMPLATES_DIR / "builtins"
INDEX_FILE = TEMPLATES_DIR / "index.json"
DEPRECATED_DIR = TEMPLATES_DIR / "deprecated"

# ─── Motifs with real effects (keep) ─────────────────────────────────
REAL_MOTIFS = {
    "candy_stripes",
    "fire",
    "light_trails",
    "ornaments",
    "snowflakes",
    "radial_rays",
    "sparkles",
    "spiral",
}

# ─── Effect recipes for replacing On+hit_small stubs ────────────────


def _layer(
    index: int,
    name: str,
    depth: str,
    effect_type: str,
    blend: str = "NORMAL",
    mix: float = 1.0,
    params: dict | None = None,
    motion: list[str] | None = None,
    density: float = 0.6,
    color_source: str = "palette_primary",
    timing_offset: float | None = None,
) -> dict:
    layer = {
        "layer_index": index,
        "layer_name": name,
        "layer_depth": depth,
        "effect_type": effect_type,
        "blend_mode": blend,
        "mix": mix,
        "params": {k: {"value": v} for k, v in (params or {}).items()},
        "motion": motion or [],
        "density": density,
        "color_source": color_source,
    }
    if timing_offset is not None:
        layer["timing_offset_beats"] = timing_offset
    return layer


# ─── RHYTHM replacements ────────────────────────────────────────────

RHYTHM_REPLACEMENTS: dict[str, dict] = {
    "gtpl_rhythm_bounce_even": {
        "layers": [
            _layer(
                0,
                "Bounce Wash",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 50,
                    "cycles": 2.0,
                    "shimmer": True,
                    "horizontal_fade": False,
                    "vertical_fade": True,
                },
                motion=["BOUNCE"],
                density=0.7,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_rhythm_bounce_staggered": {
        "layers": [
            _layer(
                0,
                "Staggered Bounce",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 40,
                    "cycles": 3.0,
                    "shimmer": True,
                    "horizontal_fade": True,
                    "vertical_fade": True,
                },
                motion=["BOUNCE", "CHASE"],
                density=0.65,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_rhythm_double_time_push": {
        "layers": [
            _layer(
                0,
                "Double Time Pulse",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 80,
                    "cycles": 4.0,
                    "shimmer": True,
                    "horizontal_fade": False,
                    "vertical_fade": False,
                },
                motion=["PULSE"],
                density=0.8,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_rhythm_half_time_hold": {
        "layers": [
            _layer(
                0,
                "Half Time Hold",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 15,
                    "cycles": 0.5,
                    "shimmer": False,
                    "horizontal_fade": True,
                    "vertical_fade": False,
                },
                motion=["FADE"],
                density=0.5,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_rhythm_icicle_drip_fast": {
        "layers": [
            _layer(
                0,
                "Fast Icicle Drip",
                "FOREGROUND",
                "Meteors",
                params={
                    "count": 8,
                    "length": 30,
                    "speed": 15,
                    "direction": "Down",
                    "color_type": "Palette",
                    "swirl_intensity": 0,
                },
                motion=["CHASE"],
                density=0.7,
            ),
        ],
        "effect_family": "meteors",
    },
    "gtpl_rhythm_icicle_drip_slow": {
        "layers": [
            _layer(
                0,
                "Slow Icicle Drip",
                "FOREGROUND",
                "Meteors",
                params={
                    "count": 4,
                    "length": 50,
                    "speed": 5,
                    "direction": "Down",
                    "color_type": "Palette",
                    "swirl_intensity": 0,
                },
                motion=["FADE"],
                density=0.5,
            ),
        ],
        "effect_family": "meteors",
    },
    "gtpl_rhythm_strand_alt_blocks": {
        "layers": [
            _layer(
                0,
                "Alternating Blocks",
                "BACKGROUND",
                "SingleStrand",
                params={"chase_type": "Alternate", "group_count": 4, "chase_rotations": 100},
                motion=["CHASE"],
                density=0.6,
            ),
        ],
        "effect_family": "single_strand",
    },
    "gtpl_rhythm_strand_color_wipe": {
        "layers": [
            _layer(
                0,
                "Color Wipe",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 60,
                    "cycles": 1.0,
                    "shimmer": False,
                    "horizontal_fade": True,
                    "vertical_fade": False,
                },
                motion=["WIPE"],
                density=0.7,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_rhythm_strand_comet": {
        "layers": [
            _layer(
                0,
                "Comet Trail",
                "FOREGROUND",
                "Meteors",
                params={
                    "count": 1,
                    "length": 60,
                    "speed": 10,
                    "direction": "Right",
                    "color_type": "Palette",
                    "swirl_intensity": 20,
                },
                motion=["CHASE"],
                density=0.6,
            ),
        ],
        "effect_family": "meteors",
    },
    "gtpl_rhythm_strand_pingpong": {
        "layers": [
            _layer(
                0,
                "Ping-Pong Chase",
                "BACKGROUND",
                "SingleStrand",
                params={"chase_type": "Bounce from Left", "group_count": 3, "chase_rotations": 100},
                motion=["BOUNCE"],
                density=0.6,
            ),
        ],
        "effect_family": "single_strand",
    },
}

# ─── ACCENT replacements ────────────────────────────────────────────

ACCENT_REPLACEMENTS: dict[str, dict] = {
    "gtpl_accent_bell_single": {
        "layers": [
            _layer(
                0,
                "Bell Ring Decay",
                "FOREGROUND",
                "Twinkle",
                params={"count": 8, "steps": 60, "strobe": False, "re_random": False},
                motion=["FADE"],
                density=0.5,
            ),
        ],
        "effect_family": "twinkle",
    },
    "gtpl_accent_call_response_simple": {
        "layers": [
            _layer(
                0,
                "Call Side",
                "FOREGROUND",
                "Color Wash",
                params={
                    "speed": 60,
                    "cycles": 2.0,
                    "shimmer": True,
                    "horizontal_fade": True,
                    "vertical_fade": False,
                },
                motion=["SWEEP"],
                density=0.7,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_accent_call_response_stacked": {
        "layers": [
            _layer(
                0,
                "Call Layer",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 50,
                    "cycles": 2.0,
                    "shimmer": True,
                    "horizontal_fade": True,
                    "vertical_fade": False,
                },
                motion=["SWEEP"],
                density=0.6,
            ),
            _layer(
                1,
                "Response Overlay",
                "FOREGROUND",
                "Twinkle",
                blend="ADD",
                mix=0.6,
                params={"count": 6, "steps": 30, "strobe": False, "re_random": True},
                motion=["SPARKLE"],
                density=0.5,
                color_source="palette_accent",
                timing_offset=2.0,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_accent_cut_to_black": {
        "layers": [
            _layer(
                0,
                "Blackout",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 100,
                    "cycles": 1.0,
                    "shimmer": False,
                    "horizontal_fade": False,
                    "vertical_fade": False,
                },
                motion=["FADE"],
                density=0.0,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_accent_hit_color": {
        "layers": [
            _layer(
                0,
                "Color Flash",
                "FOREGROUND",
                "Strobe",
                params={"speed": 80, "type": "Strobe Color"},
                motion=["STROBE"],
                density=0.9,
            ),
        ],
        "effect_family": "strobe",
    },
    "gtpl_accent_hit_ring": {
        "layers": [
            _layer(
                0,
                "Ring Expansion",
                "FOREGROUND",
                "Shockwave",
                params={
                    "start_radius": 1,
                    "end_radius": 200,
                    "start_width": 50,
                    "end_width": 10,
                    "accel": 3,
                    "center_x": 50,
                    "center_y": 50,
                },
                motion=["RIPPLE"],
                density=0.8,
            ),
        ],
        "effect_family": "shockwave",
    },
    "gtpl_accent_hit_white": {
        "layers": [
            _layer(
                0,
                "White Flash",
                "FOREGROUND",
                "Strobe",
                params={"speed": 90, "type": "Strobe White"},
                motion=["STROBE"],
                density=0.9,
                color_source="white_only",
            ),
        ],
        "effect_family": "strobe",
    },
    "gtpl_accent_icon_pop_single": {
        "layers": [
            _layer(
                0,
                "Icon Pop",
                "FOREGROUND",
                "Pictures",
                params={"movement": "None", "frame_rate_adj": 10},
                motion=["PULSE"],
                density=0.7,
            ),
        ],
        "effect_family": "pictures",
    },
    "gtpl_accent_icon_pop_triplet": {
        "layers": [
            _layer(
                0,
                "Icon Sequence",
                "FOREGROUND",
                "Pictures",
                params={"movement": "Iterate", "frame_rate_adj": 20},
                motion=["CHASE", "PULSE"],
                density=0.7,
            ),
        ],
        "effect_family": "pictures",
    },
    "gtpl_accent_lyric_spotlight": {
        "layers": [
            _layer(
                0,
                "Spotlight Center",
                "FOREGROUND",
                "Color Wash",
                params={
                    "speed": 30,
                    "cycles": 1.0,
                    "shimmer": False,
                    "horizontal_fade": True,
                    "vertical_fade": True,
                },
                motion=["PULSE"],
                density=0.8,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_accent_lyric_underline": {
        "layers": [
            _layer(
                0,
                "Bottom Underline",
                "FOREGROUND",
                "Color Wash",
                params={
                    "speed": 40,
                    "cycles": 1.0,
                    "shimmer": False,
                    "horizontal_fade": False,
                    "vertical_fade": True,
                },
                motion=["WIPE"],
                density=0.7,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_accent_rollcall_lr": {
        "layers": [
            _layer(
                0,
                "Sequential L-R",
                "FOREGROUND",
                "SingleStrand",
                params={"chase_type": "Left-Right", "group_count": 1, "chase_rotations": 50},
                motion=["CHASE"],
                density=0.7,
            ),
        ],
        "effect_family": "single_strand",
    },
    "gtpl_accent_rollcall_random": {
        "layers": [
            _layer(
                0,
                "Random Activation",
                "FOREGROUND",
                "Twinkle",
                params={"count": 10, "steps": 20, "strobe": False, "re_random": True},
                motion=["SPARKLE"],
                density=0.7,
            ),
        ],
        "effect_family": "twinkle",
    },
    "gtpl_accent_wipe_fast": {
        "layers": [
            _layer(
                0,
                "Fast Wipe",
                "FOREGROUND",
                "Color Wash",
                params={
                    "speed": 90,
                    "cycles": 1.0,
                    "shimmer": False,
                    "horizontal_fade": True,
                    "vertical_fade": False,
                },
                motion=["WIPE"],
                density=0.8,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_accent_wipe_slam": {
        "layers": [
            _layer(
                0,
                "Slam Wipe Hold",
                "FOREGROUND",
                "Color Wash",
                params={
                    "speed": 100,
                    "cycles": 1.0,
                    "shimmer": False,
                    "horizontal_fade": False,
                    "vertical_fade": False,
                },
                motion=["WIPE"],
                density=1.0,
            ),
        ],
        "effect_family": "color_wash",
    },
}

# ─── TRANSITION replacements ────────────────────────────────────────

TRANSITION_REPLACEMENTS: dict[str, dict] = {
    "gtpl_transition_build_long": {
        "layers": [
            _layer(
                0,
                "Intensity Ramp",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 10,
                    "cycles": 1.0,
                    "shimmer": True,
                    "horizontal_fade": False,
                    "vertical_fade": False,
                },
                motion=["PULSE", "SHIMMER"],
                density=0.3,
            ),
            _layer(
                1,
                "Sparkle Build",
                "FOREGROUND",
                "Twinkle",
                blend="ADD",
                mix=0.4,
                params={"count": 3, "steps": 50, "strobe": False, "re_random": True},
                motion=["SHIMMER"],
                density=0.3,
                color_source="palette_accent",
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_transition_build_short": {
        "layers": [
            _layer(
                0,
                "Quick Intensity Ramp",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 30,
                    "cycles": 2.0,
                    "shimmer": True,
                    "horizontal_fade": False,
                    "vertical_fade": False,
                },
                motion=["PULSE"],
                density=0.5,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_transition_crossfade_hard": {
        "layers": [
            _layer(
                0,
                "Hard Crossfade",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 80,
                    "cycles": 1.0,
                    "shimmer": False,
                    "horizontal_fade": False,
                    "vertical_fade": False,
                },
                motion=["FADE"],
                density=0.8,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_transition_crossfade_soft": {
        "layers": [
            _layer(
                0,
                "Soft Crossfade",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 20,
                    "cycles": 1.0,
                    "shimmer": False,
                    "horizontal_fade": True,
                    "vertical_fade": True,
                },
                motion=["FADE"],
                density=0.5,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_transition_fade_in": {
        "layers": [
            _layer(
                0,
                "Fade From Black",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 15,
                    "cycles": 1.0,
                    "shimmer": False,
                    "horizontal_fade": False,
                    "vertical_fade": False,
                },
                motion=["FADE"],
                density=0.0,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_transition_fade_out": {
        "layers": [
            _layer(
                0,
                "Fade To Black",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 15,
                    "cycles": 1.0,
                    "shimmer": False,
                    "horizontal_fade": False,
                    "vertical_fade": False,
                },
                motion=["FADE"],
                density=1.0,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_transition_ramp_down": {
        "layers": [
            _layer(
                0,
                "Decaying Intensity",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 25,
                    "cycles": 1.0,
                    "shimmer": False,
                    "horizontal_fade": False,
                    "vertical_fade": False,
                },
                motion=["FADE"],
                density=0.8,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_transition_ramp_up": {
        "layers": [
            _layer(
                0,
                "Rising Intensity",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 25,
                    "cycles": 1.0,
                    "shimmer": True,
                    "horizontal_fade": False,
                    "vertical_fade": False,
                },
                motion=["PULSE"],
                density=0.3,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_transition_wipe_lr": {
        "layers": [
            _layer(
                0,
                "Left-Right Wipe",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 70,
                    "cycles": 1.0,
                    "shimmer": False,
                    "horizontal_fade": True,
                    "vertical_fade": False,
                },
                motion=["WIPE"],
                density=0.8,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_transition_wipe_radial": {
        "layers": [
            _layer(
                0,
                "Radial Expand Wipe",
                "BACKGROUND",
                "Shockwave",
                params={
                    "start_radius": 1,
                    "end_radius": 300,
                    "start_width": 200,
                    "end_width": 300,
                    "accel": 2,
                    "center_x": 50,
                    "center_y": 50,
                },
                motion=["RIPPLE"],
                density=0.8,
            ),
        ],
        "effect_family": "shockwave",
    },
}

# ─── SPECIAL replacements ───────────────────────────────────────────

SPECIAL_REPLACEMENTS: dict[str, dict] = {
    "gtpl_special_bridge_moody": {
        "layers": [
            _layer(
                0,
                "Moody Wash",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 10,
                    "cycles": 0.5,
                    "shimmer": False,
                    "horizontal_fade": True,
                    "vertical_fade": True,
                },
                motion=["FADE"],
                density=0.25,
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_special_bridge_sparse": {
        "layers": [
            _layer(
                0,
                "Sparse Twinkle",
                "BACKGROUND",
                "Twinkle",
                params={"count": 2, "steps": 60, "strobe": False, "re_random": True},
                motion=["TWINKLE"],
                density=0.15,
            ),
        ],
        "effect_family": "twinkle",
    },
    "gtpl_special_chorus_signature_a": {
        "layers": [
            _layer(
                0,
                "Full Bright Wash",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 40,
                    "cycles": 2.0,
                    "shimmer": True,
                    "horizontal_fade": False,
                    "vertical_fade": False,
                },
                motion=["PULSE"],
                density=0.9,
            ),
            _layer(
                1,
                "Sparkle Overlay",
                "FOREGROUND",
                "Twinkle",
                blend="ADD",
                mix=0.7,
                params={"count": 10, "steps": 20, "strobe": False, "re_random": True},
                motion=["SPARKLE"],
                density=0.7,
                color_source="palette_accent",
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_special_chorus_signature_b": {
        "layers": [
            _layer(
                0,
                "Rhythmic Wash",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 60,
                    "cycles": 4.0,
                    "shimmer": True,
                    "horizontal_fade": False,
                    "vertical_fade": False,
                },
                motion=["PULSE", "SWEEP"],
                density=0.85,
            ),
            _layer(
                1,
                "Strobe Accent",
                "FOREGROUND",
                "Strobe",
                blend="ADD",
                mix=0.5,
                params={"speed": 50, "type": "Strobe Color"},
                motion=["STROBE"],
                density=0.6,
                color_source="palette_accent",
            ),
        ],
        "effect_family": "color_wash",
    },
    "gtpl_special_drop_explode": {
        "layers": [
            _layer(
                0,
                "Explosion",
                "FOREGROUND",
                "Shockwave",
                params={
                    "start_radius": 1,
                    "end_radius": 300,
                    "start_width": 80,
                    "end_width": 10,
                    "accel": 8,
                    "center_x": 50,
                    "center_y": 50,
                },
                motion=["RIPPLE", "PULSE"],
                density=1.0,
            ),
        ],
        "effect_family": "shockwave",
    },
    "gtpl_special_drop_freeze": {
        "layers": [
            _layer(
                0,
                "Freeze Flash",
                "FOREGROUND",
                "Strobe",
                params={"speed": 100, "type": "Strobe White"},
                motion=["STROBE"],
                density=1.0,
                color_source="white_only",
            ),
            _layer(
                1,
                "Color Hold",
                "BACKGROUND",
                "Color Wash",
                blend="NORMAL",
                mix=0.8,
                params={
                    "speed": 1,
                    "cycles": 1.0,
                    "shimmer": False,
                    "horizontal_fade": False,
                    "vertical_fade": False,
                },
                motion=[],
                density=0.9,
            ),
        ],
        "effect_family": "strobe",
    },
    "gtpl_special_finale_ramp": {
        "layers": [
            _layer(
                0,
                "Maximum Build",
                "BACKGROUND",
                "Color Wash",
                params={
                    "speed": 60,
                    "cycles": 4.0,
                    "shimmer": True,
                    "horizontal_fade": False,
                    "vertical_fade": False,
                },
                motion=["PULSE", "SHIMMER"],
                density=0.7,
            ),
            _layer(
                1,
                "Sparkle Crescendo",
                "FOREGROUND",
                "Twinkle",
                blend="ADD",
                mix=0.6,
                params={"count": 8, "steps": 15, "strobe": False, "re_random": True},
                motion=["SPARKLE"],
                density=0.6,
                color_source="palette_accent",
            ),
            _layer(
                2,
                "Strobe Peak",
                "ACCENT",
                "Strobe",
                blend="ADD",
                mix=0.4,
                params={"speed": 70, "type": "Strobe Color"},
                motion=["STROBE"],
                density=0.5,
                color_source="palette_accent",
            ),
        ],
        "effect_family": "color_wash",
    },
}

# The level_meter rename
LEVEL_METER_REPLACEMENT = {
    "recipe_id": "gtpl_special_strand_level_meter",
    "effect_family": "single_strand",
    "layers": [
        _layer(
            0,
            "VU Level Meter",
            "BACKGROUND",
            "SingleStrand",
            params={"chase_type": "Left-Right", "group_count": 1, "chase_rotations": 100},
            motion=["CHASE"],
            density=0.7,
        ),
    ],
}


def is_stub_motif(recipe_id: str) -> bool:
    """Return True if this recipe belongs to a motif that has no real effects."""
    if "_motif_" not in recipe_id:
        return False
    parts = recipe_id.split("_motif_")[1]
    motif = parts.split("_")[0]
    if len(parts.split("_")) > 2:
        motif = "_".join(parts.split("_")[:2])
    for real in REAL_MOTIFS:
        if parts.startswith(real):
            return False
    return True


def derive_effect_family(template: dict) -> str:
    """Derive effect_family from primary layer's effect type."""
    layers = template.get("layers", [])
    if not layers:
        return "unknown"
    primary = layers[0]
    et = primary.get("effect_type", "unknown")
    return et.lower().replace(" ", "_")


def apply_replacement(template: dict, replacement: dict) -> dict:
    """Apply a replacement definition to a template."""
    template["layers"] = replacement["layers"]
    if "effect_family" in replacement:
        template["effect_family"] = replacement["effect_family"]
    if "recipe_id" in replacement:
        template["recipe_id"] = replacement["recipe_id"]
    return template


def main() -> None:
    DEPRECATED_DIR.mkdir(exist_ok=True)

    index = json.loads(INDEX_FILE.read_text())
    entries = index["entries"]

    deleted_ids: set[str] = set()
    modified_ids: set[str] = set()

    # ── 1. Remove stub motif templates ──────────────────────────────

    print("=== Phase 1: Remove stub motif templates ===")
    stub_files: list[Path] = []
    for f in sorted(BUILTINS_DIR.iterdir()):
        if not f.name.endswith(".json"):
            continue
        tpl = json.loads(f.read_text())
        rid = tpl["recipe_id"]
        if is_stub_motif(rid):
            stub_files.append(f)
            deleted_ids.add(rid)

    for f in stub_files:
        dest = DEPRECATED_DIR / f.name
        shutil.move(str(f), str(dest))
        print(f"  DEPRECATED: {f.name}")

    print(f"  Total deprecated: {len(stub_files)}")

    # ── 2. Remove near-duplicate wash_soft ──────────────────────────

    print("\n=== Phase 2: Remove near-duplicate wash_soft ===")
    wash_soft = BUILTINS_DIR / "gtpl_base_wash_soft.json"
    if wash_soft.exists():
        shutil.move(str(wash_soft), str(DEPRECATED_DIR / wash_soft.name))
        deleted_ids.add("gtpl_base_wash_soft")
        print("  DEPRECATED: gtpl_base_wash_soft.json")

    # ── 3. Replace On+hit_small stubs with real effects ─────────────

    print("\n=== Phase 3: Replace On+hit_small stubs ===")
    all_replacements = {
        **RHYTHM_REPLACEMENTS,
        **ACCENT_REPLACEMENTS,
        **TRANSITION_REPLACEMENTS,
        **SPECIAL_REPLACEMENTS,
    }

    for f in sorted(BUILTINS_DIR.iterdir()):
        if not f.name.endswith(".json"):
            continue
        tpl = json.loads(f.read_text())
        rid = tpl["recipe_id"]
        if rid in deleted_ids:
            continue

        if rid in all_replacements:
            tpl = apply_replacement(tpl, all_replacements[rid])
            f.write_text(json.dumps(tpl, indent=2) + "\n")
            modified_ids.add(rid)
            print(f"  FIXED: {rid}")

    # ── 4. Handle level_meter rename ────────────────────────────────

    print("\n=== Phase 4: Rename level_meter ===")
    old_lm = BUILTINS_DIR / "gtpl_rhythm_strand_level_meter.json"
    new_lm = BUILTINS_DIR / "gtpl_special_strand_level_meter.json"
    if old_lm.exists():
        tpl = json.loads(old_lm.read_text())
        tpl = apply_replacement(tpl, LEVEL_METER_REPLACEMENT)
        tpl["name"] = "Strand - Level Meter (1D VU)"
        tpl["template_type"] = "SPECIAL"
        new_lm.write_text(json.dumps(tpl, indent=2) + "\n")
        old_lm.unlink()
        deleted_ids.add("gtpl_rhythm_strand_level_meter")
        modified_ids.add("gtpl_special_strand_level_meter")
        print("  RENAMED: gtpl_rhythm_strand_level_meter → gtpl_special_strand_level_meter")

    # ── 5. Integrate orphaned pinwheel templates ────────────────────

    print("\n=== Phase 5: Integrate pinwheel templates ===")
    for old_name, new_id, ttype in [
        ("pinwheel_base_001.json", "gtpl_base_pinwheel_wash", "BASE"),
        ("pinwheel_rhythm_001.json", "gtpl_rhythm_pinwheel_twinkle", "RHYTHM"),
    ]:
        old = BUILTINS_DIR / old_name
        if old.exists():
            tpl = json.loads(old.read_text())
            tpl["recipe_id"] = new_id
            tpl["effect_family"] = derive_effect_family(tpl)
            new_path = BUILTINS_DIR / f"{new_id}.json"
            new_path.write_text(json.dumps(tpl, indent=2) + "\n")
            old.unlink()
            modified_ids.add(new_id)
            print(f"  INTEGRATED: {old_name} → {new_id}.json")

    # ── 6. Populate effect_family on all remaining templates ────────

    print("\n=== Phase 6: Populate effect_family ===")
    family_count = 0
    for f in sorted(BUILTINS_DIR.iterdir()):
        if not f.name.endswith(".json"):
            continue
        tpl = json.loads(f.read_text())
        rid = tpl["recipe_id"]
        if rid in deleted_ids:
            continue
        old_family = tpl.get("effect_family", "unknown")
        if old_family == "unknown" or old_family == "":
            new_family = derive_effect_family(tpl)
            tpl["effect_family"] = new_family
            f.write_text(json.dumps(tpl, indent=2) + "\n")
            family_count += 1
            modified_ids.add(rid)

    print(f"  Updated effect_family on {family_count} templates")

    # ── 7. Rebuild index.json ───────────────────────────────────────

    print("\n=== Phase 7: Rebuild index.json ===")

    new_entries: list[dict] = []
    for f in sorted(BUILTINS_DIR.iterdir()):
        if not f.name.endswith(".json"):
            continue
        tpl = json.loads(f.read_text())
        new_entries.append(
            {
                "recipe_id": tpl["recipe_id"],
                "name": tpl["name"],
                "template_type": tpl["template_type"],
                "visual_intent": tpl["visual_intent"],
                "tags": tpl.get("tags", []),
                "source": tpl.get("provenance", {}).get("source", "builtin"),
                "file": f"builtins/{f.name}",
            }
        )

    new_index = {
        "schema_version": "template-index.v1",
        "total": len(new_entries),
        "entries": new_entries,
    }
    INDEX_FILE.write_text(json.dumps(new_index, indent=2) + "\n")
    print(f"  Index rebuilt: {len(new_entries)} entries")

    # ── Summary ─────────────────────────────────────────────────────

    print("\n" + "=" * 60)
    print("CLEANUP SUMMARY")
    print("=" * 60)
    print(f"  Templates deprecated: {len(deleted_ids)}")
    print(f"  Templates fixed/modified: {len(modified_ids)}")
    print(f"  Final template count: {len(new_entries)}")
    print(f"  Deprecated files in: {DEPRECATED_DIR}")


if __name__ == "__main__":
    main()
