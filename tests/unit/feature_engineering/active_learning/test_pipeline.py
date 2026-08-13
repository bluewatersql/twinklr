"""Tests for the active-learning correction round trip.

The centrepiece is :func:`test_review_correction_round_trip_changes_classification`:
sample → batch → simulated human corrections → applier → corrections config →
fresh classifier → the corrected label wins. That round trip is what breaks the
weak-supervision circularity of a taxonomy trained on its own rule engine.
"""

from __future__ import annotations

import json
from pathlib import Path

from twinklr.core.feature_engineering.active_learning.batch_builder import ReviewBatchBuilder
from twinklr.core.feature_engineering.active_learning.models import (
    UncertaintySamplerOptions,
)
from twinklr.core.feature_engineering.active_learning.pipeline import (
    DEFAULT_CORRECTIONS_PATH,
    apply_corrections_file,
    load_corrections_file,
    merge_corrections_into_config,
    signatures_from_batch,
    signatures_from_phrases,
)
from twinklr.core.feature_engineering.active_learning.sampler import (
    UncertaintySampler,
    candidate_id_for,
)
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
from twinklr.core.feature_engineering.taxonomy.classifier import (
    TaxonomyClassifier,
    TaxonomyClassifierOptions,
)

_EFFECT_TYPE = "Twinkle"
_PARAM_SIGNATURE = "sig-twinkle-01"


def _phrase(index: int) -> EffectPhrase:
    """Build an uncertain phrase the sampler will pick up."""
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


def _corrections_payload(candidate_id: str, *, approved: bool = True) -> list[dict[str, object]]:
    """Simulate the JSON a human reviewer writes back for one candidate."""
    return [
        {
            "candidate_id": candidate_id,
            "effect_type": _EFFECT_TYPE,
            "original_family": "unknown",
            "original_motion": "unknown",
            "corrected_family": "SPARKLE",
            "corrected_motion": "sparkle",
            "correction_confidence": 0.95,
            "rationale": "Reviewer identified a twinkle overlay.",
            "approved": approved,
        }
    ]


def _write_corrections(tmp_path: Path, candidate_id: str, *, approved: bool = True) -> Path:
    path = tmp_path / "taxonomy_corrections.json"
    path.write_text(json.dumps(_corrections_payload(candidate_id, approved=approved)))
    return path


def _empty_config(tmp_path: Path) -> Path:
    path = tmp_path / "corrections.json"
    path.write_text(json.dumps({"schema_version": "1.0.0", "labels": {}}))
    return path


def test_load_corrections_file_parses_reviewer_json(tmp_path: Path) -> None:
    """The reviewer's JSON array parses into TaxonomyCorrectionResult objects."""
    path = _write_corrections(tmp_path, "cand_001")

    corrections = load_corrections_file(path)

    assert len(corrections) == 1
    assert corrections[0].candidate_id == "cand_001"
    assert corrections[0].effect_type == _EFFECT_TYPE
    assert corrections[0].approved is True


def test_apply_corrections_file_merges_into_corrections_json(tmp_path: Path) -> None:
    """One approved correction adds exactly one rule, and re-applying is a no-op."""
    candidate_id = candidate_id_for(_EFFECT_TYPE, _PARAM_SIGNATURE)
    corrections_path = _write_corrections(tmp_path, candidate_id)
    config_path = _empty_config(tmp_path)
    signatures = {candidate_id: _PARAM_SIGNATURE}

    report = apply_corrections_file(
        corrections_path,
        taxonomy_overrides={candidate_id: {"family": "unknown", "motion": "unknown"}},
        signatures=signatures,
        config_path=config_path,
    )

    assert report is not None
    assert report.total_applied == 1
    label = TaxonomyLabel.SPARKLE_OVERLAY.value
    config = json.loads(config_path.read_text())
    rules = config["labels"][label]["rules"]
    assert len(rules) == 1
    assert rules[0]["id"] == f"correction:{candidate_id}"
    assert rules[0]["when"] == {
        "effect_type": _EFFECT_TYPE,
        "param_signature": _PARAM_SIGNATURE,
    }
    assert rules[0]["weight"] == 1.0

    apply_corrections_file(
        corrections_path,
        taxonomy_overrides={},
        signatures=signatures,
        config_path=config_path,
    )

    reloaded = json.loads(config_path.read_text())
    assert len(reloaded["labels"][label]["rules"]) == 1


def test_unapproved_corrections_are_not_persisted(tmp_path: Path) -> None:
    """A correction the reviewer rejected never becomes a rule."""
    candidate_id = candidate_id_for(_EFFECT_TYPE, _PARAM_SIGNATURE)
    corrections_path = _write_corrections(tmp_path, candidate_id, approved=False)
    config_path = _empty_config(tmp_path)

    apply_corrections_file(
        corrections_path,
        signatures={candidate_id: _PARAM_SIGNATURE},
        config_path=config_path,
    )

    assert json.loads(config_path.read_text())["labels"] == {}


def test_apply_corrections_file_returns_none_without_a_file(tmp_path: Path) -> None:
    """The first run has no reviewer answer yet, so nothing happens."""
    assert apply_corrections_file(tmp_path / "taxonomy_corrections.json") is None


def test_merge_skips_candidates_with_no_known_signature(tmp_path: Path) -> None:
    """A correction for an unseen candidate cannot be turned into a rule."""
    corrections = load_corrections_file(_write_corrections(tmp_path, "unknown_candidate"))
    config_path = _empty_config(tmp_path)

    added = merge_corrections_into_config(corrections, signatures={}, config_path=config_path)

    assert added == ()
    assert json.loads(config_path.read_text())["labels"] == {}


def test_merge_preserves_existing_rules(tmp_path: Path) -> None:
    """Merging is additive: rules already in the file survive untouched."""
    candidate_id = candidate_id_for(_EFFECT_TYPE, _PARAM_SIGNATURE)
    config_path = tmp_path / "corrections.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "labels": {
                    TaxonomyLabel.SPARKLE_OVERLAY.value: {
                        "base": 0.0,
                        "min_confidence": 0.0,
                        "rules": [
                            {
                                "id": "correction:earlier",
                                "when": {"effect_type": "X"},
                                "weight": 1.0,
                            }
                        ],
                    }
                },
            }
        )
    )
    corrections = load_corrections_file(_write_corrections(tmp_path, candidate_id))

    merge_corrections_into_config(
        corrections,
        signatures={candidate_id: _PARAM_SIGNATURE},
        config_path=config_path,
    )

    rules = json.loads(config_path.read_text())["labels"][TaxonomyLabel.SPARKLE_OVERLAY.value][
        "rules"
    ]
    assert [rule["id"] for rule in rules] == ["correction:earlier", f"correction:{candidate_id}"]


def test_signature_indexes_agree(tmp_path: Path) -> None:
    """Signatures derived from phrases and from a batch key the same candidates."""
    phrases = tuple(_phrase(i) for i in range(3))
    candidates = UncertaintySampler(UncertaintySamplerOptions()).sample(phrases, ())
    batch = ReviewBatchBuilder().build(candidates, phrases)

    assert signatures_from_batch(batch) == signatures_from_phrases(phrases)


def test_review_correction_round_trip_changes_classification(tmp_path: Path) -> None:
    """Sample → batch → human correction → applier → next classification changes."""
    phrases = tuple(_phrase(i) for i in range(3))
    base_labels = (
        TaxonomyClassifier()
        .classify(phrases=phrases, package_id="pkg-1", sequence_file_id="seq-1")[0]
        .labels
    )
    assert TaxonomyLabel.SPARKLE_OVERLAY not in base_labels

    candidates = UncertaintySampler(UncertaintySamplerOptions()).sample(phrases, ())
    assert candidates, "the uncertain phrase group should be sampled for review"
    batch = ReviewBatchBuilder().build(candidates, phrases)
    candidate_id = batch.items[0].candidate.candidate_id

    # The human answers the batch by hand-writing the corrections file.
    corrections_path = _write_corrections(tmp_path, candidate_id)
    config_path = _empty_config(tmp_path)

    report = apply_corrections_file(
        corrections_path,
        taxonomy_overrides={
            c.candidate_id: {"family": c.current_family, "motion": c.current_motion}
            for c in candidates
        },
        signatures=signatures_from_batch(batch),
        config_path=config_path,
    )

    assert report is not None
    assert report.total_applied == 1
    assert report.unknown_ratio_after < report.unknown_ratio_before

    # A fresh classifier — the next mining run — reads the corrections layer.
    corrected = TaxonomyClassifier(
        TaxonomyClassifierOptions(corrections_path=config_path)
    ).classify(phrases=phrases, package_id="pkg-1", sequence_file_id="seq-1")[0]

    assert TaxonomyLabel.SPARKLE_OVERLAY in corrected.labels
    assert corrected.labels != base_labels
    assert f"correction:{candidate_id}" in corrected.rule_hit_keys
    top = max(corrected.label_scores, key=lambda score: score.confidence)
    assert top.label is TaxonomyLabel.SPARKLE_OVERLAY


def test_effect_function_v2_is_never_written_by_the_loop(tmp_path: Path) -> None:
    """Only the corrections layer is written; the base rule file stays pristine."""
    base_path = DEFAULT_CORRECTIONS_PATH.parent / "effect_function_v2.json"
    before = base_path.read_bytes()
    candidate_id = candidate_id_for(_EFFECT_TYPE, _PARAM_SIGNATURE)

    apply_corrections_file(
        _write_corrections(tmp_path, candidate_id),
        signatures={candidate_id: _PARAM_SIGNATURE},
        config_path=_empty_config(tmp_path),
    )

    assert base_path.read_bytes() == before
