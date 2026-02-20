"""Phase 1 Integration Test: FE pipeline produces all Phase 1 artifacts.

Runs the full FE pipeline with Color Arc, Propensity, and Style Fingerprint
stages enabled, then verifies all new artifacts exist and contain valid content.
"""

from __future__ import annotations

import json
from pathlib import Path

from twinklr.core.feature_engineering.pipeline import (
    FeatureEngineeringPipeline,
    FeatureEngineeringPipelineOptions,
)


class _FakeAnalyzer:
    """Minimal analyzer stub returning enough features for Phase 1 stages."""

    def analyze_sync(self, audio_path: str, *, force_reprocess: bool = False):
        return type(
            "_Bundle",
            (),
            {
                "features": {
                    "duration_s": 120.0,
                    "assumptions": {"beats_per_bar": 4},
                    "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
                    "bars_s": [0.0, 2.0, 4.0],
                    "energy": {
                        "times_s": [0.0, 1.0, 2.0, 3.0, 4.0],
                        "rms_norm": [0.2, 0.4, 0.8, 0.6, 0.3],
                    },
                    "tempo_analysis": {"tempo_curve": [{"time_s": 0.0, "tempo_bpm": 120.0}]},
                    "tension": {"tension_curve": [0.3, 0.5, 0.7, 0.6]},
                    "structure": {
                        "sections": [
                            {"start_s": 0.0, "end_s": 2.0, "label": "intro"},
                            {"start_s": 2.0, "end_s": 4.0, "label": "verse"},
                        ]
                    },
                    "harmonic": {
                        "chords": {
                            "chords": [
                                {"time_s": 0.0, "chord": "C:maj"},
                                {"time_s": 2.0, "chord": "A:min"},
                            ]
                        }
                    },
                }
            },
        )()


def _write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_audio(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"audio")


def _seed_profile(profile_dir: Path) -> None:
    """Seed a minimal profile with enriched effect events for Phase 1 stages."""
    _write_json(
        profile_dir / "sequence_metadata.json",
        {
            "package_id": "pkg-phase1",
            "sequence_file_id": "seq-phase1",
            "sequence_sha256": "sha-phase1",
            "media_file": "TestSong.mp3",
            "song": "Test Song",
            "artist": "Test Artist",
        },
    )
    _write_json(
        profile_dir / "lineage_index.json",
        {"sequence_file": {"filename": "TestSong.xsq"}},
    )
    # Multiple events across sections to exercise phrase grouping and color narrative
    _write_json(
        profile_dir / "enriched_effect_events.json",
        [
            {
                "effect_event_id": "evt-1",
                "target_name": "Megatree",
                "layer_index": 0,
                "effect_type": "On",
                "start_ms": 0,
                "end_ms": 1000,
            },
            {
                "effect_event_id": "evt-2",
                "target_name": "Megatree",
                "layer_index": 0,
                "effect_type": "On",
                "start_ms": 1000,
                "end_ms": 2000,
            },
            {
                "effect_event_id": "evt-3",
                "target_name": "Arch",
                "layer_index": 0,
                "effect_type": "Shimmer",
                "start_ms": 2000,
                "end_ms": 3000,
            },
            {
                "effect_event_id": "evt-4",
                "target_name": "Arch",
                "layer_index": 1,
                "effect_type": "Twinkle",
                "start_ms": 2500,
                "end_ms": 3500,
            },
        ],
    )


def _setup_corpus(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create corpus structure with one profile entry."""
    profile_dir = tmp_path / "profiles" / "test_profile"
    corpus_dir = tmp_path / "corpus"
    output_root = tmp_path / "features"
    extracted_root = tmp_path / "vendor"

    _seed_profile(profile_dir)
    _write_audio(extracted_root / "test_extracted" / "TestSong.mp3")

    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "sequence_index.jsonl").write_text(
        json.dumps(
            {
                "profile_path": str(profile_dir),
                "package_id": "pkg-phase1",
                "sequence_file_id": "seq-phase1",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    return corpus_dir, output_root, extracted_root


def test_phase1_artifacts_produced(tmp_path: Path) -> None:
    """All Phase 1 artifacts are written when pipeline runs with stages enabled."""
    corpus_dir, output_root, extracted_root = _setup_corpus(tmp_path)

    pipeline = FeatureEngineeringPipeline(
        options=FeatureEngineeringPipelineOptions(
            extracted_search_roots=(extracted_root,),
            enable_color_arc=True,
            enable_propensity=True,
            enable_style_fingerprint=True,
        ),
        analyzer=_FakeAnalyzer(),
    )
    bundles = pipeline.run_corpus(corpus_dir, output_root)

    assert len(bundles) == 1

    # Phase 1 artifact files must exist
    assert (output_root / "color_arc.json").exists(), "color_arc.json missing"
    assert (output_root / "propensity_index.json").exists(), "propensity_index.json missing"
    assert (output_root / "style_fingerprint.json").exists(), "style_fingerprint.json missing"


def test_phase1_manifest_entries(tmp_path: Path) -> None:
    """Feature store manifest contains entries for all Phase 1 artifacts."""
    corpus_dir, output_root, extracted_root = _setup_corpus(tmp_path)

    pipeline = FeatureEngineeringPipeline(
        options=FeatureEngineeringPipelineOptions(
            extracted_search_roots=(extracted_root,),
        ),
        analyzer=_FakeAnalyzer(),
    )
    pipeline.run_corpus(corpus_dir, output_root)

    manifest = json.loads((output_root / "feature_store_manifest.json").read_text(encoding="utf-8"))
    assert "color_arc" in manifest, "manifest missing color_arc entry"
    assert "propensity_index" in manifest, "manifest missing propensity_index entry"
    assert "style_fingerprint" in manifest, "manifest missing style_fingerprint entry"


def test_phase1_color_arc_content(tmp_path: Path) -> None:
    """Color arc artifact contains valid structure with palettes and assignments."""
    corpus_dir, output_root, extracted_root = _setup_corpus(tmp_path)

    pipeline = FeatureEngineeringPipeline(
        options=FeatureEngineeringPipelineOptions(
            extracted_search_roots=(extracted_root,),
        ),
        analyzer=_FakeAnalyzer(),
    )
    pipeline.run_corpus(corpus_dir, output_root)

    arc = json.loads((output_root / "color_arc.json").read_text(encoding="utf-8"))
    assert "palette_library" in arc
    assert "section_assignments" in arc
    assert isinstance(arc["palette_library"], list)
    assert isinstance(arc["section_assignments"], list)


def test_phase1_propensity_content(tmp_path: Path) -> None:
    """Propensity index contains valid affinities list."""
    corpus_dir, output_root, extracted_root = _setup_corpus(tmp_path)

    pipeline = FeatureEngineeringPipeline(
        options=FeatureEngineeringPipelineOptions(
            extracted_search_roots=(extracted_root,),
        ),
        analyzer=_FakeAnalyzer(),
    )
    pipeline.run_corpus(corpus_dir, output_root)

    index = json.loads((output_root / "propensity_index.json").read_text(encoding="utf-8"))
    assert "affinities" in index
    assert isinstance(index["affinities"], list)
    # Each affinity should have required fields
    for aff in index["affinities"]:
        assert "effect_family" in aff
        assert "model_type" in aff
        assert "frequency" in aff


def test_phase1_style_fingerprint_content(tmp_path: Path) -> None:
    """Style fingerprint contains valid creator profile structure."""
    corpus_dir, output_root, extracted_root = _setup_corpus(tmp_path)

    pipeline = FeatureEngineeringPipeline(
        options=FeatureEngineeringPipelineOptions(
            extracted_search_roots=(extracted_root,),
        ),
        analyzer=_FakeAnalyzer(),
    )
    pipeline.run_corpus(corpus_dir, output_root)

    fp = json.loads((output_root / "style_fingerprint.json").read_text(encoding="utf-8"))
    assert "creator_id" in fp
    assert "recipe_preferences" in fp
    assert "transition_style" in fp
    assert "timing_style" in fp
    assert "layering_style" in fp
    assert fp["creator_id"] == "pkg-phase1"


def test_phase1_disabled_stages_omit_artifacts(tmp_path: Path) -> None:
    """When Phase 1 stages are disabled, their artifacts are not produced."""
    corpus_dir, output_root, extracted_root = _setup_corpus(tmp_path)

    pipeline = FeatureEngineeringPipeline(
        options=FeatureEngineeringPipelineOptions(
            extracted_search_roots=(extracted_root,),
            enable_color_arc=False,
            enable_propensity=False,
            enable_style_fingerprint=False,
        ),
        analyzer=_FakeAnalyzer(),
    )
    pipeline.run_corpus(corpus_dir, output_root)

    assert not (output_root / "color_arc.json").exists()
    assert not (output_root / "propensity_index.json").exists()
    assert not (output_root / "style_fingerprint.json").exists()

    manifest = json.loads((output_root / "feature_store_manifest.json").read_text(encoding="utf-8"))
    assert "color_arc" not in manifest
    assert "propensity_index" not in manifest
    assert "style_fingerprint" not in manifest
