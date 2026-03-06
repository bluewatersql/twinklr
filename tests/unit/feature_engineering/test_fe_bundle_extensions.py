"""Tests for FEArtifactBundle extensions: vocabulary_extensions, color_palette_library, color_narrative."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError
import pytest

from twinklr.core.feature_engineering.loader import FEArtifactBundle, load_fe_artifacts

# ---------------------------------------------------------------------------
# Minimal JSON fixtures
# ---------------------------------------------------------------------------

VOCABULARY_EXTENSIONS_JSON = {
    "schema_version": "v1.0.0",
    "compound_motion_terms": [],
    "compound_energy_terms": [],
    "total_stack_signatures_analyzed": 10,
    "total_multi_layer_stacks": 5,
}

COLOR_PALETTE_LIBRARY_JSON = {
    "schema_version": "v1.0.0",
    "palette_count": 1,
    "palettes": [
        {
            "palette_id": "p1",
            "name": "warm",
            "colors": ["#FF0000", "#FF8800"],
            "scope_key": ["pkg1", "seq1", "section1"],
            "hue_bins": [{"bin_name": "red", "colors": ["#FF0000"]}],
        }
    ],
}

COLOR_NARRATIVE_JSON = [
    {
        "schema_version": "v1.0.0",
        "package_id": "pkg1",
        "sequence_file_id": "seq1",
        "section_label": "intro",
        "section_index": 0,
        "phrase_count": 4,
        "dominant_color_class": "warm",
        "contrast_shift_from_prev": 0.25,
        "hue_family_movement": "stable",
    }
]


# ---------------------------------------------------------------------------
# Helper: write manifest + artifact file to tmp_path
# ---------------------------------------------------------------------------


def _write_manifest(out: Path, entries: dict[str, str]) -> None:
    (out / "feature_store_manifest.json").write_text(json.dumps(entries), encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Defaults: all new fields absent / default values
# ---------------------------------------------------------------------------


def test_bundle_all_new_fields_absent() -> None:
    """FEArtifactBundle() defaults: vocabulary_extensions=None, collections empty."""
    bundle = FEArtifactBundle()
    assert bundle.vocabulary_extensions is None
    assert bundle.color_palette_library == ()
    assert bundle.color_narrative == ()


# ---------------------------------------------------------------------------
# 2. vocabulary_extensions loaded from manifest
# ---------------------------------------------------------------------------


def test_bundle_vocabulary_extensions_loaded(tmp_path: Path) -> None:
    """load_fe_artifacts populates vocabulary_extensions when manifest key present."""
    out = tmp_path / "fe_out"
    out.mkdir()

    vocab_file = out / "vocabulary_extensions.json"
    vocab_file.write_text(json.dumps(VOCABULARY_EXTENSIONS_JSON), encoding="utf-8")

    _write_manifest(out, {"vocabulary_extensions": str(vocab_file)})

    bundle = load_fe_artifacts(out)

    assert bundle.vocabulary_extensions is not None
    assert bundle.vocabulary_extensions.schema_version == "v1.0.0"
    assert bundle.vocabulary_extensions.total_stack_signatures_analyzed == 10
    assert bundle.vocabulary_extensions.total_multi_layer_stacks == 5
    assert bundle.vocabulary_extensions.compound_motion_terms == ()
    assert bundle.vocabulary_extensions.compound_energy_terms == ()


# ---------------------------------------------------------------------------
# 3. color_palette_library loaded from manifest
# ---------------------------------------------------------------------------


def test_bundle_color_palette_library_loaded(tmp_path: Path) -> None:
    """load_fe_artifacts populates color_palette_library from palette JSON."""
    from twinklr.core.feature_engineering.color_discovery import DiscoveredPalette, HueBin

    out = tmp_path / "fe_out"
    out.mkdir()

    palette_file = out / "color_palette_library.json"
    palette_file.write_text(json.dumps(COLOR_PALETTE_LIBRARY_JSON), encoding="utf-8")

    _write_manifest(out, {"color_palette_library": str(palette_file)})

    bundle = load_fe_artifacts(out)

    assert len(bundle.color_palette_library) == 1
    palette = bundle.color_palette_library[0]
    assert isinstance(palette, DiscoveredPalette)
    assert palette.name == "warm"
    assert palette.scope_key == ("pkg1", "seq1", "section1")
    assert palette.colors == ("#FF0000", "#FF8800")
    assert len(palette.hue_bins) == 1
    hb = palette.hue_bins[0]
    assert isinstance(hb, HueBin)
    assert hb.bin_name == "red"
    assert hb.colors == ("#FF0000",)


# ---------------------------------------------------------------------------
# 4. color_narrative loaded from manifest
# ---------------------------------------------------------------------------


def test_bundle_color_narrative_loaded(tmp_path: Path) -> None:
    """load_fe_artifacts populates color_narrative from list JSON."""
    from twinklr.core.feature_engineering.models.color_narrative import ColorNarrativeRow

    out = tmp_path / "fe_out"
    out.mkdir()

    narrative_file = out / "color_narrative.json"
    narrative_file.write_text(json.dumps(COLOR_NARRATIVE_JSON), encoding="utf-8")

    _write_manifest(out, {"color_narrative": str(narrative_file)})

    bundle = load_fe_artifacts(out)

    assert len(bundle.color_narrative) == 1
    row = bundle.color_narrative[0]
    assert isinstance(row, ColorNarrativeRow)
    assert row.package_id == "pkg1"
    assert row.sequence_file_id == "seq1"
    assert row.section_label == "intro"
    assert row.section_index == 0
    assert row.phrase_count == 4
    assert row.dominant_color_class == "warm"
    assert row.contrast_shift_from_prev == pytest.approx(0.25)
    assert row.hue_family_movement == "stable"


# ---------------------------------------------------------------------------
# 5-7. Key present in manifest but file missing → graceful default
# ---------------------------------------------------------------------------


def test_manifest_key_present_file_missing_vocabulary(tmp_path: Path) -> None:
    """vocabulary_extensions is None when manifest key points to missing file."""
    out = tmp_path / "fe_out"
    out.mkdir()

    _write_manifest(out, {"vocabulary_extensions": str(out / "nonexistent.json")})

    bundle = load_fe_artifacts(out)

    assert bundle.vocabulary_extensions is None


def test_manifest_key_present_file_missing_palettes(tmp_path: Path) -> None:
    """color_palette_library is () when manifest key points to missing file."""
    out = tmp_path / "fe_out"
    out.mkdir()

    _write_manifest(out, {"color_palette_library": str(out / "nonexistent.json")})

    bundle = load_fe_artifacts(out)

    assert bundle.color_palette_library == ()


def test_manifest_key_present_file_missing_narrative(tmp_path: Path) -> None:
    """color_narrative is () when manifest key points to missing file."""
    out = tmp_path / "fe_out"
    out.mkdir()

    _write_manifest(out, {"color_narrative": str(out / "nonexistent.json")})

    bundle = load_fe_artifacts(out)

    assert bundle.color_narrative == ()


# ---------------------------------------------------------------------------
# 8. Frozen model
# ---------------------------------------------------------------------------


def test_fe_artifact_bundle_frozen() -> None:
    """FEArtifactBundle is immutable (frozen=True)."""
    bundle = FEArtifactBundle()
    with pytest.raises(ValidationError):
        bundle.vocabulary_extensions = None  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 9. Extra fields forbidden
# ---------------------------------------------------------------------------


def test_fe_artifact_bundle_extra_forbid() -> None:
    """FEArtifactBundle rejects unknown extra fields."""
    with pytest.raises(ValidationError):
        FEArtifactBundle(unknown_field="oops")  # type: ignore[call-arg]
