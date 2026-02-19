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


def _seed_profile(profile_dir: Path, *, effect_type: str = "On") -> None:
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
                "effect_type": effect_type,
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
    assert (output_root / "unknown_diagnostics.json").exists()
    assert (output_root / "template_retrieval_index.json").exists()
    assert (output_root / "template_diagnostics.json").exists()
    assert (output_root / "motif_catalog.json").exists()
    assert (output_root / "cluster_candidates.json").exists()
    assert (output_root / "cluster_review_queue.jsonl").exists()
    assert (output_root / "taxonomy_model_bundle.json").exists()
    assert (output_root / "taxonomy_eval_report.json").exists()
    assert (output_root / "retrieval_ann_index.json").exists()
    assert (output_root / "retrieval_eval_report.json").exists()
    assert (output_root / "planner_adapter_payloads" / "sequencer_adapter_payloads.jsonl").exists()
    assert (output_root / "planner_adapter_acceptance.json").exists()
    assert (output_root / "feature_store_manifest.json").exists()

    manifest = json.loads((output_root / "feature_store_manifest.json").read_text(encoding="utf-8"))
    assert "unknown_diagnostics" in manifest
    assert "template_retrieval_index" in manifest
    assert "template_diagnostics" in manifest
    assert "motif_catalog" in manifest
    assert "cluster_candidates" in manifest
    assert "cluster_review_queue" in manifest
    assert "taxonomy_model_bundle" in manifest
    assert "taxonomy_eval_report" in manifest
    assert "retrieval_ann_index" in manifest
    assert "retrieval_eval_report" in manifest
    assert "planner_adapter_payloads" in manifest
    assert "planner_adapter_acceptance" in manifest

    acceptance = json.loads((output_root / "planner_adapter_acceptance.json").read_text(encoding="utf-8"))
    assert acceptance["planner_change_mode_enforced"] is True
    assert acceptance["planner_runtime_changes_applied"] is False


def test_pipeline_run_corpus_writes_unknown_diagnostics_content(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profiles" / "show_profile"
    corpus_dir = tmp_path / "corpus"
    output_root = tmp_path / "features"
    extracted_root = tmp_path / "vendor"
    _seed_profile(profile_dir, effect_type="Totally Unknown Effect")
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
    pipeline.run_corpus(corpus_dir, output_root)

    diagnostics = json.loads((output_root / "unknown_diagnostics.json").read_text(encoding="utf-8"))
    assert diagnostics["unknown_effect_family_count"] == 1
    assert diagnostics["unknown_motion_count"] == 1
    top = diagnostics["top_unknown_effect_types"]
    assert isinstance(top, list) and top
    assert top[0]["effect_type"] == "Totally Unknown Effect"
