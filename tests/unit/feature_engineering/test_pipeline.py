from __future__ import annotations

import json
from pathlib import Path

import pytest

from twinklr.core.feature_engineering.pipeline import (
    FeatureEngineeringPipeline,
    FeatureEngineeringPipelineOptions,
)


class _FakeAnalyzer:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[tuple[str, bool]] = []

    def analyze_sync(self, audio_path: str, *, force_reprocess: bool = False):
        self.calls.append((audio_path, force_reprocess))
        if self.should_fail:
            raise RuntimeError("boom")
        return type(
            "_Bundle",
            (),
            {
                "features": {
                    "duration_s": 120.0,
                    "assumptions": {"beats_per_bar": 4},
                    "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0],
                    "bars_s": [0.0, 2.0],
                    "energy": {"times_s": [0.0, 2.0], "rms_norm": [0.2, 0.8]},
                    "tempo_analysis": {"tempo_curve": [{"time_s": 0.0, "tempo_bpm": 120.0}]},
                    "tension": {"tension_curve": [0.3, 0.5, 0.7, 0.6]},
                    "structure": {
                        "sections": [
                            {"start_s": 0.0, "end_s": 2.0, "label": "intro"},
                            {"start_s": 2.0, "end_s": 120.0, "label": "verse"},
                        ]
                    },
                    "harmonic": {"chords": {"chords": [{"time_s": 0.0, "chord": "C:maj"}]}},
                }
            },
        )()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_audio(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"audio")


def _seed_profile(profile_dir: Path) -> None:
    _write_json(
        profile_dir / "sequence_metadata.json",
        {
            "package_id": "pkg-1",
            "sequence_file_id": "seq-1",
            "sequence_sha256": "sha-seq",
            "media_file": "Need A Favor.mp3",
            "song": "Need A Favor",
            "artist": "Jelly Roll",
        },
    )
    _write_json(
        profile_dir / "lineage_index.json",
        {
            "sequence_file": {
                "filename": "Need A Favor.xsq",
            }
        },
    )
    _write_json(
        profile_dir / "enriched_effect_events.json",
        [
            {
                "effect_event_id": "evt-1",
                "target_name": "Tree",
                "layer_index": 0,
                "effect_type": "On",
                "start_ms": 0,
                "end_ms": 1000,
            }
        ],
    )


def test_pipeline_run_profile_writes_artifacts(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profiles" / "show_profile"
    output_dir = tmp_path / "features" / "pkg-1" / "seq-1"
    extracted_root = tmp_path / "vendor"
    _seed_profile(profile_dir)
    _write_audio(extracted_root / "show_extracted" / "Need A Favor.mp3")

    analyzer = _FakeAnalyzer()
    pipeline = FeatureEngineeringPipeline(
        options=FeatureEngineeringPipelineOptions(extracted_search_roots=(extracted_root,)),
        analyzer=analyzer,
    )
    bundle = pipeline.run_profile(profile_dir, output_dir)

    assert bundle.audio.audio_status.value == "found_in_pack"
    assert bundle.audio.audio_path is not None
    assert bundle.audio.analyzer_version == "AudioAnalyzer"
    assert len(analyzer.calls) == 2
    assert (output_dir / "audio_discovery.json").exists()
    assert (output_dir / "feature_bundle.json").exists()
    assert (
        (output_dir / "aligned_events.parquet").exists()
        or (output_dir / "aligned_events.jsonl").exists()
    )
    assert (
        (output_dir / "effect_phrases.parquet").exists()
        or (output_dir / "effect_phrases.jsonl").exists()
    )
    assert (
        (output_dir / "phrase_taxonomy.parquet").exists()
        or (output_dir / "phrase_taxonomy.jsonl").exists()
    )
    assert (
        (output_dir / "target_roles.parquet").exists()
        or (output_dir / "target_roles.jsonl").exists()
    )


def test_pipeline_run_profile_degraded_when_analyzer_fails(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profiles" / "show_profile"
    output_dir = tmp_path / "features"
    extracted_root = tmp_path / "vendor"
    _seed_profile(profile_dir)
    _write_audio(extracted_root / "show_extracted" / "Need A Favor.mp3")

    pipeline = FeatureEngineeringPipeline(
        options=FeatureEngineeringPipelineOptions(extracted_search_roots=(extracted_root,)),
        analyzer=_FakeAnalyzer(should_fail=True),
    )
    bundle = pipeline.run_profile(profile_dir, output_dir)

    assert bundle.audio.audio_status.value == "found_in_pack"
    assert bundle.audio.analyzer_error == "boom"


def test_pipeline_audio_required_raises_without_analyzer(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profiles" / "show_profile"
    output_dir = tmp_path / "features"
    extracted_root = tmp_path / "vendor"
    _seed_profile(profile_dir)
    _write_audio(extracted_root / "show_extracted" / "Need A Favor.mp3")

    pipeline = FeatureEngineeringPipeline(
        options=FeatureEngineeringPipelineOptions(
            extracted_search_roots=(extracted_root,),
            audio_required=True,
        ),
        analyzer=None,
    )
    with pytest.raises(ValueError, match="no analyzer configured"):
        pipeline.run_profile(profile_dir, output_dir)


def test_pipeline_run_corpus_iterates_sequence_index(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profiles" / "show_profile"
    corpus_dir = tmp_path / "corpus"
    output_root = tmp_path / "features"
    extracted_root = tmp_path / "vendor"
    _seed_profile(profile_dir)
    _write_audio(extracted_root / "show_extracted" / "Need A Favor.mp3")
    (corpus_dir / "sequence_index.jsonl").parent.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "sequence_index.jsonl").write_text(
        json.dumps(
            {
                "profile_path": str(profile_dir),
                "package_id": "pkg-1",
                "sequence_file_id": "seq-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    pipeline = FeatureEngineeringPipeline(
        options=FeatureEngineeringPipelineOptions(extracted_search_roots=(extracted_root,)),
        analyzer=_FakeAnalyzer(),
    )
    bundles = pipeline.run_corpus(corpus_dir, output_root)

    assert len(bundles) == 1
    assert bundles[0].package_id == "pkg-1"
    assert (output_root / "pkg-1" / "seq-1" / "feature_bundle.json").exists()
    assert (output_root / "content_templates.json").exists()
    assert (output_root / "orchestration_templates.json").exists()
    assert (output_root / "transition_graph.json").exists()
    assert (
        (output_root / "layering_features.parquet").exists()
        or (output_root / "layering_features.jsonl").exists()
    )
    assert (
        (output_root / "color_narrative.parquet").exists()
        or (output_root / "color_narrative.jsonl").exists()
    )
    assert (output_root / "quality_report.json").exists()
    assert (output_root / "feature_store_manifest.json").exists()
