"""Tests for PERF-21: parallel corpus processing via max_workers."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from unittest.mock import patch

from twinklr.core.feature_engineering.pipeline import (
    FeatureEngineeringPipeline,
    FeatureEngineeringPipelineOptions,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_audio(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"audio")


def _seed_profile(profile_dir: Path, *, pkg_id: str = "pkg-1", seq_id: str = "seq-1") -> None:
    _write_json(
        profile_dir / "sequence_metadata.json",
        {
            "package_id": pkg_id,
            "sequence_file_id": seq_id,
            "sequence_sha256": "sha-seq",
            "media_file": "Need A Favor.mp3",
            "song": "Need A Favor",
            "artist": "Jelly Roll",
        },
    )
    _write_json(
        profile_dir / "lineage_index.json",
        {"sequence_file": {"filename": "Need A Favor.xsq"}},
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


class _FakeAnalyzer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def analyze_sync(self, audio_path: str, *, force_reprocess: bool = False):
        self.calls.append((audio_path, force_reprocess))
        return type(
            "_Bundle",
            (),
            {
                "features": {
                    "duration_s": 120.0,
                    "assumptions": {"beats_per_bar": 4},
                    "beats_s": [0.0, 0.5, 1.0],
                    "bars_s": [0.0, 2.0],
                    "energy": {"times_s": [0.0], "rms_norm": [0.5]},
                    "tempo_analysis": {"tempo_curve": [{"time_s": 0.0, "tempo_bpm": 120.0}]},
                    "tension": {"tension_curve": [0.3, 0.5]},
                    "structure": {"sections": [{"start_s": 0.0, "end_s": 120.0, "label": "verse"}]},
                    "harmonic": {"chords": {"chords": [{"time_s": 0.0, "chord": "C:maj"}]}},
                }
            },
        )()


def _write_corpus_index(corpus_dir: Path, rows: list[dict]) -> None:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row) for row in rows]
    (corpus_dir / "sequence_index.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# PERF-21: max_workers parameter exists on run_corpus
# ---------------------------------------------------------------------------


class TestMaxWorkersSignature:
    """run_corpus must accept max_workers keyword argument."""

    def test_max_workers_in_signature(self) -> None:
        sig = inspect.signature(FeatureEngineeringPipeline.run_corpus)
        assert "max_workers" in sig.parameters, "run_corpus missing max_workers parameter"

    def test_max_workers_default_is_none(self) -> None:
        sig = inspect.signature(FeatureEngineeringPipeline.run_corpus)
        default = sig.parameters["max_workers"].default
        assert default is None, f"max_workers default should be None, got {default!r}"


# ---------------------------------------------------------------------------
# Sequential mode (backward compat)
# ---------------------------------------------------------------------------


class TestSequentialMode:
    """max_workers=None produces the same results as the legacy sequential path."""

    def test_sequential_single_profile(self, tmp_path: Path) -> None:
        profile_dir = tmp_path / "profiles" / "show"
        corpus_dir = tmp_path / "corpus"
        output_root = tmp_path / "features"
        extracted_root = tmp_path / "vendor"

        _seed_profile(profile_dir, pkg_id="pkg-1", seq_id="seq-1")
        _write_audio(extracted_root / "show_extracted" / "Need A Favor.mp3")
        _write_corpus_index(
            corpus_dir,
            [
                {
                    "profile_path": str(profile_dir),
                    "package_id": "pkg-1",
                    "sequence_file_id": "seq-1",
                }
            ],
        )

        pipeline = FeatureEngineeringPipeline(
            options=FeatureEngineeringPipelineOptions(extracted_search_roots=(extracted_root,)),
            analyzer=_FakeAnalyzer(),
        )
        bundles = pipeline.run_corpus(corpus_dir, output_root, max_workers=None)
        assert len(bundles) == 1
        assert bundles[0].package_id == "pkg-1"

    def test_sequential_explicit_one_worker(self, tmp_path: Path) -> None:
        profile_dir = tmp_path / "profiles" / "show"
        corpus_dir = tmp_path / "corpus"
        output_root = tmp_path / "features"
        extracted_root = tmp_path / "vendor"

        _seed_profile(profile_dir, pkg_id="pkg-1", seq_id="seq-1")
        _write_audio(extracted_root / "show_extracted" / "Need A Favor.mp3")
        _write_corpus_index(
            corpus_dir,
            [
                {
                    "profile_path": str(profile_dir),
                    "package_id": "pkg-1",
                    "sequence_file_id": "seq-1",
                }
            ],
        )

        pipeline = FeatureEngineeringPipeline(
            options=FeatureEngineeringPipelineOptions(extracted_search_roots=(extracted_root,)),
            analyzer=_FakeAnalyzer(),
        )
        bundles = pipeline.run_corpus(corpus_dir, output_root, max_workers=1)
        assert len(bundles) == 1


# ---------------------------------------------------------------------------
# Parallel mode
# ---------------------------------------------------------------------------


class TestParallelMode:
    """max_workers > 1 uses ThreadPoolExecutor and produces correct results."""

    def test_parallel_two_profiles(self, tmp_path: Path) -> None:
        profiles = []
        rows = []
        extracted_root = tmp_path / "vendor"
        _write_audio(extracted_root / "show_extracted" / "Need A Favor.mp3")

        for i in range(2):
            pkg_id = f"pkg-{i}"
            seq_id = f"seq-{i}"
            profile_dir = tmp_path / "profiles" / f"show-{i}"
            _seed_profile(profile_dir, pkg_id=pkg_id, seq_id=seq_id)
            profiles.append(profile_dir)
            rows.append(
                {
                    "profile_path": str(profile_dir),
                    "package_id": pkg_id,
                    "sequence_file_id": seq_id,
                }
            )

        corpus_dir = tmp_path / "corpus"
        output_root = tmp_path / "features"
        _write_corpus_index(corpus_dir, rows)

        pipeline = FeatureEngineeringPipeline(
            options=FeatureEngineeringPipelineOptions(extracted_search_roots=(extracted_root,)),
            analyzer=_FakeAnalyzer(),
        )
        bundles = pipeline.run_corpus(corpus_dir, output_root, max_workers=2)
        assert len(bundles) == 2
        pkg_ids = {b.package_id for b in bundles}
        assert "pkg-0" in pkg_ids
        assert "pkg-1" in pkg_ids

    def test_parallel_artifacts_written(self, tmp_path: Path) -> None:
        """All expected corpus-level artifacts are written in parallel mode."""
        profile_dir = tmp_path / "profiles" / "show"
        corpus_dir = tmp_path / "corpus"
        output_root = tmp_path / "features"
        extracted_root = tmp_path / "vendor"

        _seed_profile(profile_dir, pkg_id="pkg-1", seq_id="seq-1")
        _write_audio(extracted_root / "show_extracted" / "Need A Favor.mp3")
        _write_corpus_index(
            corpus_dir,
            [
                {
                    "profile_path": str(profile_dir),
                    "package_id": "pkg-1",
                    "sequence_file_id": "seq-1",
                }
            ],
        )

        pipeline = FeatureEngineeringPipeline(
            options=FeatureEngineeringPipelineOptions(extracted_search_roots=(extracted_root,)),
            analyzer=_FakeAnalyzer(),
        )
        pipeline.run_corpus(corpus_dir, output_root, max_workers=2)

        assert (output_root / "content_templates.json").exists()
        assert (output_root / "orchestration_templates.json").exists()
        assert (output_root / "feature_store_manifest.json").exists()

    def test_parallel_uses_thread_pool(self, tmp_path: Path) -> None:
        """ThreadPoolExecutor is used when max_workers > 1."""
        profile_dir = tmp_path / "profiles" / "show"
        corpus_dir = tmp_path / "corpus"
        output_root = tmp_path / "features"
        extracted_root = tmp_path / "vendor"

        _seed_profile(profile_dir, pkg_id="pkg-1", seq_id="seq-1")
        _write_audio(extracted_root / "show_extracted" / "Need A Favor.mp3")
        _write_corpus_index(
            corpus_dir,
            [
                {
                    "profile_path": str(profile_dir),
                    "package_id": "pkg-1",
                    "sequence_file_id": "seq-1",
                }
            ],
        )

        pipeline = FeatureEngineeringPipeline(
            options=FeatureEngineeringPipelineOptions(extracted_search_roots=(extracted_root,)),
            analyzer=_FakeAnalyzer(),
        )

        with patch(
            "twinklr.core.feature_engineering.pipeline.ThreadPoolExecutor"
        ) as mock_executor_cls:
            # Use a real executor behind the mock so the pipeline still works
            from concurrent.futures import ThreadPoolExecutor as _RealTPE

            mock_executor_cls.side_effect = lambda max_workers=None: _RealTPE(
                max_workers=max_workers
            )
            pipeline.run_corpus(corpus_dir, output_root, max_workers=2)
            mock_executor_cls.assert_called_once_with(max_workers=2)


# ---------------------------------------------------------------------------
# Error isolation in parallel mode
# ---------------------------------------------------------------------------


class TestParallelErrorHandling:
    """A failure in one profile does not prevent others from completing."""

    def test_error_profile_does_not_block_others(self, tmp_path: Path) -> None:
        """With fail_fast=False, a bad profile is skipped; good ones complete."""
        rows = []
        extracted_root = tmp_path / "vendor"
        _write_audio(extracted_root / "show_extracted" / "Need A Favor.mp3")

        # Profile 0: good
        pkg_id, seq_id = "pkg-good", "seq-good"
        good_dir = tmp_path / "profiles" / "good"
        _seed_profile(good_dir, pkg_id=pkg_id, seq_id=seq_id)
        rows.append(
            {
                "profile_path": str(good_dir),
                "package_id": pkg_id,
                "sequence_file_id": seq_id,
            }
        )

        # Profile 1: missing sequence_metadata.json → will raise FileNotFoundError
        bad_dir = tmp_path / "profiles" / "bad"
        bad_dir.mkdir(parents=True, exist_ok=True)
        rows.append(
            {
                "profile_path": str(bad_dir),
                "package_id": "pkg-bad",
                "sequence_file_id": "seq-bad",
            }
        )

        corpus_dir = tmp_path / "corpus"
        output_root = tmp_path / "features"
        _write_corpus_index(corpus_dir, rows)

        pipeline = FeatureEngineeringPipeline(
            options=FeatureEngineeringPipelineOptions(
                extracted_search_roots=(extracted_root,),
                fail_fast=False,
            ),
            analyzer=_FakeAnalyzer(),
        )
        bundles = pipeline.run_corpus(corpus_dir, output_root, max_workers=2)
        # Only the good profile should be in results
        assert len(bundles) == 1
        assert bundles[0].package_id == "pkg-good"


# ---------------------------------------------------------------------------
# Store write serialization
# ---------------------------------------------------------------------------


class TestStoreWriteSerialization:
    """Store writes are serialized even in parallel mode (no corruption)."""

    def test_store_calls_are_threadsafe(self, tmp_path: Path) -> None:
        """upsert_phrases is called once per profile without interleaving errors."""
        rows = []
        extracted_root = tmp_path / "vendor"
        _write_audio(extracted_root / "show_extracted" / "Need A Favor.mp3")

        for i in range(3):
            pkg_id = f"pkg-{i}"
            seq_id = f"seq-{i}"
            profile_dir = tmp_path / "profiles" / f"show-{i}"
            _seed_profile(profile_dir, pkg_id=pkg_id, seq_id=seq_id)
            rows.append(
                {
                    "profile_path": str(profile_dir),
                    "package_id": pkg_id,
                    "sequence_file_id": seq_id,
                }
            )

        corpus_dir = tmp_path / "corpus"
        output_root = tmp_path / "features"
        _write_corpus_index(corpus_dir, rows)

        pipeline = FeatureEngineeringPipeline(
            options=FeatureEngineeringPipelineOptions(extracted_search_roots=(extracted_root,)),
            analyzer=_FakeAnalyzer(),
        )
        # Should complete without exception (thread-safety smoke test)
        bundles = pipeline.run_corpus(corpus_dir, output_root, max_workers=3)
        assert len(bundles) == 3
