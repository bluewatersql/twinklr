"""Tests for Phase 05 COL-01: ColorArcExtractor palette library loop closure.

Verifies that discovered palettes from palette_library_path are preferred
over hardcoded _PALETTE_TEMPLATES when available, with correct fallback behavior.
"""

from __future__ import annotations

import json
from pathlib import Path

from twinklr.core.feature_engineering.color_arc import ColorArcExtractor
from twinklr.core.feature_engineering.models.color_arc import NamedPalette
from twinklr.core.feature_engineering.models.color_narrative import ColorNarrativeRow
from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)

# ---------------------------------------------------------------------------
# Hardcoded palette IDs from _PALETTE_TEMPLATES (used to verify fallback)
# ---------------------------------------------------------------------------

_TEMPLATE_PALETTE_IDS = {
    "pal_cool_white",
    "pal_warm_white",
    "pal_classic_holiday",
    "pal_icy_blue",
    "pal_rainbow_burst",
    "pal_carnival",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_phrase(*, section_label: str, section_index: int = 0) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.0.0",
        phrase_id=f"ph_{section_label}_{section_index}",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=f"evt_{section_label}_{section_index}",
        effect_type="Bars",
        effect_family="single_strand",
        motion_class=MotionClass.SWEEP,
        color_class=ColorClass.PALETTE,
        energy_class=EnergyClass.MID,
        continuity_class=ContinuityClass.SUSTAINED,
        spatial_class=SpatialClass.SINGLE_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=0.9,
        target_name="MegaTree",
        layer_index=0,
        start_ms=section_index * 4000,
        end_ms=section_index * 4000 + 4000,
        duration_ms=4000,
        section_label=section_label,
        param_signature="bars|sweep|palette",
    )


def _make_color_row(
    *,
    section_label: str,
    section_index: int,
    dominant_color_class: str = "palette",
    contrast_shift_from_prev: float = 0.0,
) -> ColorNarrativeRow:
    return ColorNarrativeRow(
        schema_version="v1.8.0",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        section_label=section_label,
        section_index=section_index,
        phrase_count=5,
        dominant_color_class=dominant_color_class,
        contrast_shift_from_prev=contrast_shift_from_prev,
        hue_family_movement="section_start" if section_index == 0 else "hold",
    )


def _make_palette_json(palettes: list[dict]) -> dict:
    """Build the JSON structure for a palette library file."""
    return {"palettes": palettes}


_DISCOVERED_PALETTES = [
    {
        "palette_id": "disc_aurora",
        "name": "Aurora",
        "colors": ["#AA00FF", "#00FFAA"],
        "mood_tags": ["ethereal", "dynamic"],
        "temperature": "cool",
    },
    {
        "palette_id": "disc_ember",
        "name": "Ember",
        "colors": ["#FF4400", "#FF8800"],
        "mood_tags": ["intense", "warm"],
        "temperature": "warm",
    },
    {
        "palette_id": "disc_frost",
        "name": "Frost",
        "colors": ["#C8EEFF", "#E8F8FF"],
        "mood_tags": ["calm", "crisp"],
        "temperature": "cool",
    },
]

_DISCOVERED_IDS = {"disc_aurora", "disc_ember", "disc_frost"}


# ---------------------------------------------------------------------------
# Test 1: extract() uses discovered palettes when library is populated
# ---------------------------------------------------------------------------


def test_color_arc_uses_discovered_palettes(tmp_path: Path) -> None:
    """ColorArcExtractor uses palette IDs from the loaded library, not _PALETTE_TEMPLATES.

    When palette_library_path points to a JSON with discovered palettes, all
    section_assignments must reference palette IDs from the library, not from
    the hardcoded template IDs.
    """
    lib_path = tmp_path / "palette_library.json"
    lib_path.write_text(json.dumps(_make_palette_json(_DISCOVERED_PALETTES)), encoding="utf-8")

    sections = ["intro", "verse", "chorus"]
    phrases = tuple(_make_phrase(section_label=s, section_index=i) for i, s in enumerate(sections))
    color_rows = tuple(
        _make_color_row(section_label=s, section_index=i) for i, s in enumerate(sections)
    )

    extractor = ColorArcExtractor(palette_library_path=lib_path)
    result = extractor.extract(phrases=phrases, color_narrative=color_rows)

    assert len(result.section_assignments) == 3, "Expected 3 section assignments"

    assigned_ids = {a.palette_id for a in result.section_assignments}
    # All assigned IDs must come from the discovered library
    assert assigned_ids.issubset(_DISCOVERED_IDS), (
        f"Expected palette IDs from library {_DISCOVERED_IDS}, got {assigned_ids}"
    )
    # Must NOT be from hardcoded templates
    assert not assigned_ids.intersection(_TEMPLATE_PALETTE_IDS), (
        f"palette IDs must not come from _PALETTE_TEMPLATES when library present: {assigned_ids}"
    )


# ---------------------------------------------------------------------------
# Test 2: extract() falls back to _PALETTE_TEMPLATES when library is empty
# ---------------------------------------------------------------------------


def test_color_arc_fallback_empty_library(tmp_path: Path) -> None:
    """ColorArcExtractor falls back to _PALETTE_TEMPLATES when palette library is empty.

    When palette_library_path points to a JSON with an empty palettes list,
    section_assignments must use IDs from _PALETTE_TEMPLATES.
    """
    lib_path = tmp_path / "empty_library.json"
    lib_path.write_text(json.dumps({"palettes": []}), encoding="utf-8")

    sections = ["verse", "chorus"]
    phrases = tuple(_make_phrase(section_label=s, section_index=i) for i, s in enumerate(sections))
    color_rows = tuple(
        _make_color_row(section_label=s, section_index=i) for i, s in enumerate(sections)
    )

    extractor = ColorArcExtractor(palette_library_path=lib_path)
    result = extractor.extract(phrases=phrases, color_narrative=color_rows)

    assert len(result.section_assignments) == 2, "Expected 2 section assignments"

    assigned_ids = {a.palette_id for a in result.section_assignments}
    assert assigned_ids.issubset(_TEMPLATE_PALETTE_IDS), (
        f"Expected fallback to template palette IDs {_TEMPLATE_PALETTE_IDS}, got {assigned_ids}"
    )


# ---------------------------------------------------------------------------
# Test 3: extract() falls back to _PALETTE_TEMPLATES when no library path given
# ---------------------------------------------------------------------------


def test_color_arc_fallback_none_library() -> None:
    """ColorArcExtractor falls back to _PALETTE_TEMPLATES when no palette_library_path.

    With no palette_library_path argument, section_assignments must use IDs
    from _PALETTE_TEMPLATES (existing behavior, no regression).
    """
    sections = ["verse", "chorus"]
    phrases = tuple(_make_phrase(section_label=s, section_index=i) for i, s in enumerate(sections))
    color_rows = tuple(
        _make_color_row(section_label=s, section_index=i) for i, s in enumerate(sections)
    )

    extractor = ColorArcExtractor()  # No palette_library_path
    result = extractor.extract(phrases=phrases, color_narrative=color_rows)

    assert len(result.section_assignments) == 2, "Expected 2 section assignments"

    assigned_ids = {a.palette_id for a in result.section_assignments}
    assert assigned_ids.issubset(_TEMPLATE_PALETTE_IDS), (
        f"Expected template palette IDs {_TEMPLATE_PALETTE_IDS}, got {assigned_ids}"
    )
    # Must not be from discovered (they aren't loaded)
    assert not assigned_ids.intersection(_DISCOVERED_IDS), (
        f"Must not use discovered palette IDs when no library: {assigned_ids}"
    )


# ---------------------------------------------------------------------------
# Test 4: palette_library in SongColorArc populated from discovered palettes
# ---------------------------------------------------------------------------


def test_color_arc_palette_library_populated_from_discovery(
    tmp_path: Path,
) -> None:
    """SongColorArc.palette_library contains NamedPalette objects from the discovered library.

    The palette_library on the output arc must contain the actually-used discovered
    palettes (not template palettes).
    """
    lib_path = tmp_path / "palette_library.json"
    lib_path.write_text(json.dumps(_make_palette_json(_DISCOVERED_PALETTES)), encoding="utf-8")

    sections = ["verse"]
    phrases = tuple(_make_phrase(section_label=s, section_index=i) for i, s in enumerate(sections))
    color_rows = tuple(
        _make_color_row(section_label=s, section_index=i) for i, s in enumerate(sections)
    )

    extractor = ColorArcExtractor(palette_library_path=lib_path)
    result = extractor.extract(phrases=phrases, color_narrative=color_rows)

    assert len(result.palette_library) >= 1, "palette_library must be non-empty"
    for palette in result.palette_library:
        assert isinstance(palette, NamedPalette), f"Expected NamedPalette, got {type(palette)}"
        assert palette.palette_id in _DISCOVERED_IDS, (
            f"palette_library entry {palette.palette_id!r} not in discovered library"
        )
