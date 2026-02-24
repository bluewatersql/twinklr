"""Tests for FE artifact loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from twinklr.core.feature_engineering.loader import FEArtifactBundle, load_fe_artifacts


@pytest.fixture()
def fe_output_dir(tmp_path: Path) -> Path:
    """Create a minimal FE output directory with manifest and artifacts."""
    out = tmp_path / "fe_output"
    out.mkdir()

    color_arc = {
        "schema_version": "v1.0.0",
        "palette_library": [],
        "section_assignments": [],
        "arc_curve": [],
        "transition_rules": [],
    }
    (out / "color_arc.json").write_text(json.dumps(color_arc), encoding="utf-8")

    propensity = {
        "schema_version": "v1.0.0",
        "affinities": [],
        "anti_affinities": [],
    }
    (out / "propensity_index.json").write_text(json.dumps(propensity), encoding="utf-8")

    style = {
        "creator_id": "test_creator",
        "corpus_sequence_count": 5,
        "recipe_preferences": {},
        "transition_style": {
            "preferred_gap_ms": 50.0,
            "overlap_tendency": 0.3,
            "variety_score": 0.5,
        },
        "color_tendencies": {
            "palette_complexity": 0.5,
            "contrast_preference": 0.5,
            "temperature_preference": 0.5,
        },
        "timing_style": {
            "beat_alignment_strictness": 0.7,
            "density_preference": 0.5,
            "section_change_aggression": 0.4,
        },
        "layering_style": {
            "mean_layers": 2.0,
            "max_layers": 4,
            "blend_mode_preference": "normal",
        },
    }
    (out / "style_fingerprint.json").write_text(json.dumps(style), encoding="utf-8")

    recipe_catalog = {
        "schema_version": "1",
        "recipes": [
            {
                "recipe_id": "test_recipe_1",
                "name": "Test Recipe",
                "description": "A test recipe",
                "recipe_version": "1.0.0",
                "template_type": "BASE",
                "visual_intent": "ABSTRACT",
                "timing": {"bars_min": 2, "bars_max": 8},
                "palette_spec": {"mode": "MONOCHROME", "palette_roles": ["primary"]},
                "provenance": {"source": "mined"},
                "style_markers": {"complexity": 0.33, "energy_affinity": "LOW"},
                "layers": [
                    {
                        "layer_index": 0,
                        "layer_name": "Base",
                        "layer_depth": "BACKGROUND",
                        "effect_type": "ColorWash",
                        "blend_mode": "NORMAL",
                        "mix": 1.0,
                        "density": 0.5,
                        "params": {},
                        "color_source": "PALETTE_PRIMARY",
                    }
                ],
            }
        ],
    }
    (out / "recipe_catalog.json").write_text(json.dumps(recipe_catalog), encoding="utf-8")

    manifest = {
        "color_arc": str(out / "color_arc.json"),
        "propensity_index": str(out / "propensity_index.json"),
        "style_fingerprint": str(out / "style_fingerprint.json"),
        "recipe_catalog": str(out / "recipe_catalog.json"),
    }
    (out / "feature_store_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    return out


def test_load_all_artifacts(fe_output_dir: Path) -> None:
    """Loader populates all fields from manifest."""
    bundle = load_fe_artifacts(fe_output_dir)

    assert isinstance(bundle, FEArtifactBundle)
    assert bundle.color_arc is not None
    assert bundle.propensity_index is not None
    assert bundle.style_fingerprint is not None
    assert bundle.style_fingerprint.creator_id == "test_creator"
    assert len(bundle.recipe_catalog_entries) == 1
    assert bundle.recipe_catalog_entries[0].recipe_id == "test_recipe_1"


def test_load_missing_manifest(tmp_path: Path) -> None:
    """Loader returns empty bundle when manifest is missing."""
    bundle = load_fe_artifacts(tmp_path)

    assert isinstance(bundle, FEArtifactBundle)
    assert bundle.color_arc is None
    assert bundle.propensity_index is None
    assert bundle.style_fingerprint is None
    assert len(bundle.recipe_catalog_entries) == 0


def test_load_partial_manifest(tmp_path: Path) -> None:
    """Loader handles manifest with only some artifacts."""
    out = tmp_path / "partial"
    out.mkdir()

    color_arc = {
        "schema_version": "v1.0.0",
        "palette_library": [],
        "section_assignments": [],
        "arc_curve": [],
        "transition_rules": [],
    }
    (out / "color_arc.json").write_text(json.dumps(color_arc), encoding="utf-8")

    manifest = {"color_arc": str(out / "color_arc.json")}
    (out / "feature_store_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    bundle = load_fe_artifacts(out)

    assert bundle.color_arc is not None
    assert bundle.propensity_index is None
    assert bundle.style_fingerprint is None
    assert len(bundle.recipe_catalog_entries) == 0


def test_load_missing_artifact_file(tmp_path: Path) -> None:
    """Loader warns and returns None when artifact file is missing."""
    out = tmp_path / "broken"
    out.mkdir()

    manifest = {
        "color_arc": str(out / "nonexistent.json"),
        "recipe_catalog": str(out / "also_missing.json"),
    }
    (out / "feature_store_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    bundle = load_fe_artifacts(out)

    assert bundle.color_arc is None
    assert len(bundle.recipe_catalog_entries) == 0
