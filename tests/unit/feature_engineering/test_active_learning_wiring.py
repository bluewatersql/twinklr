"""Tests for active-learning wiring in corpus_artifacts.

Covers both halves of the human-in-the-loop cycle: the first run emits a full
review batch and stops, and the second run — once a reviewer has written
``taxonomy_corrections.json`` beside it — applies the corrections and persists
them into the taxonomy corrections layer.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from twinklr.core.feature_engineering.active_learning.sampler import candidate_id_for
from twinklr.core.feature_engineering.config import FeatureEngineeringPipelineOptions
from twinklr.core.feature_engineering.corpus_artifacts import write_v1_tail_artifacts
from twinklr.core.feature_engineering.models import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.models.taxonomy import TaxonomyLabel

_EFFECT_TYPE = "Twinkle"
_PARAM_SIGNATURE = "sig-twinkle-01"


def _options(tmp_path: Path, **overrides: object) -> FeatureEngineeringPipelineOptions:
    """Options with every stage disabled except the ones under test."""
    defaults: dict[str, object] = {
        "enable_transition_modeling": False,
        "enable_layering_features": False,
        "enable_color_narrative": False,
        "enable_color_arc": False,
        "enable_propensity": False,
        "enable_style_fingerprint": False,
        "enable_quality_gates": False,
        "enable_recipe_promotion": False,
        "enable_color_discovery": False,
        "enable_effect_metadata": False,
        "enable_vocabulary_expansion": False,
        "enable_v2_motif_mining": False,
        "enable_v2_temporal_motif_mining": False,
        "enable_v2_clustering": False,
        "enable_v2_learned_taxonomy": False,
        "enable_v2_ann_retrieval": False,
        "enable_v2_adapter_contracts": False,
        "enable_template_retrieval_ranking": False,
        "enable_template_diagnostics": False,
        "taxonomy_corrections_path": tmp_path / "corrections.json",
    }
    defaults.update(overrides)
    return FeatureEngineeringPipelineOptions(**defaults)  # type: ignore[arg-type]


def _phrase(index: int) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.2.0",
        phrase_id=f"phrase-{index}",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=f"evt-{index}",
        effect_type=_EFFECT_TYPE,
        effect_family="unknown",
        motion_class=MotionClass.UNKNOWN,
        color_class=ColorClass.PALETTE,
        energy_class=EnergyClass.MID,
        continuity_class=ContinuityClass.SUSTAINED,
        spatial_class=SpatialClass.MULTI_TARGET,
        source=PhraseSource.FALLBACK,
        map_confidence=0.2,
        target_name="Tree",
        layer_index=0,
        start_ms=0,
        end_ms=2000,
        duration_ms=2000,
        onset_sync_score=0.3,
        param_signature=_PARAM_SIGNATURE,
    )


def _run(output_root: Path, options: FeatureEngineeringPipelineOptions) -> MagicMock:
    """Run the corpus tail with mocked writers; return the writer mock."""
    writer = MagicMock()
    write_v1_tail_artifacts(
        output_root=output_root,
        bundles=(),
        phrases=tuple(_phrase(i) for i in range(3)),
        taxonomy_rows=(MagicMock(),),
        target_roles=(),
        template_catalogs=None,
        stacks=None,
        options=options,
        writer=writer,
        artifact_writer=MagicMock(),
        components=MagicMock(),
        store=MagicMock(),
    )
    return writer


def _manifest(writer: MagicMock) -> dict[str, str]:
    manifest: dict[str, str] = writer.write_feature_store_manifest.call_args.args[1]
    return manifest


def test_first_run_writes_a_full_review_batch(tmp_path: Path) -> None:
    """With no reviewer answer yet, the run emits a ReviewBatch and stops."""
    writer = _run(tmp_path, _options(tmp_path, enable_active_learning=True))

    payload = writer.write_review_batch.call_args.args[1]
    assert set(payload) == {"batch_id", "items", "total_candidates"}
    assert payload["items"][0]["candidate"]["effect_type"] == _EFFECT_TYPE
    assert payload["items"][0]["context_phrases"] == [_PARAM_SIGNATURE]
    assert "taxonomy_correction_report" not in _manifest(writer)
    assert not (tmp_path / "corrections.json").exists()


def test_second_run_applies_reviewer_corrections(tmp_path: Path) -> None:
    """A reviewer-written corrections file is applied and persisted as a rule."""
    candidate_id = candidate_id_for(_EFFECT_TYPE, _PARAM_SIGNATURE)
    (tmp_path / "taxonomy_corrections.json").write_text(
        json.dumps(
            [
                {
                    "candidate_id": candidate_id,
                    "effect_type": _EFFECT_TYPE,
                    "original_family": "unknown",
                    "original_motion": "unknown",
                    "corrected_family": "SPARKLE",
                    "corrected_motion": "sparkle",
                    "correction_confidence": 0.95,
                    "rationale": "Reviewer identified a twinkle overlay.",
                    "approved": True,
                }
            ]
        ),
        encoding="utf-8",
    )

    writer = _run(tmp_path, _options(tmp_path, enable_active_learning=True))

    config = json.loads((tmp_path / "corrections.json").read_text())
    rules = config["labels"][TaxonomyLabel.SPARKLE_OVERLAY.value]["rules"]
    assert [rule["id"] for rule in rules] == [f"correction:{candidate_id}"]

    manifest = _manifest(writer)
    report = json.loads(Path(manifest["taxonomy_correction_report"]).read_text())
    assert report["total_applied"] == 1


def test_active_learning_skipped_when_disabled(tmp_path: Path) -> None:
    """Nothing is sampled, written, or applied when the flag is off."""
    writer = _run(tmp_path, _options(tmp_path))

    writer.write_review_batch.assert_not_called()
    assert not (tmp_path / "corrections.json").exists()
