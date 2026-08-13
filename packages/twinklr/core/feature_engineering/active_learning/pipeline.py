"""Round-trip orchestration for the active-learning taxonomy correction loop.

The loop closes as follows:

1. :class:`UncertaintySampler` selects uncertain ``(effect_type, param_signature)``
   pairs; :class:`ReviewBatchBuilder` turns them into a ``ReviewBatch`` written
   to ``review_batch.json``.
2. A reviewer — a human editing JSON, or :class:`TaxonomyReviewOracle` writing
   the same shape — produces ``taxonomy_corrections.json`` beside it: a JSON
   array of :class:`TaxonomyCorrectionResult` objects.  Human review is the
   default path; this loop exists to inject truth the model does not already
   hold.
3. :func:`apply_corrections_file` applies the approved corrections and merges
   them into the git-tracked corrections layer
   (``taxonomy/config/corrections.json``) as additive classifier rules.
4. The next :class:`TaxonomyClassifier` construction merges that layer over the
   base rules, so the corrected pair classifies with the corrected label.

Label resolution: a correction names an effect *family* and *motion*, while the
classifier scores *function* labels.  :func:`resolve_correction_label` maps one
onto the other with an explicit table; a correction whose corrected family is
already a :class:`TaxonomyLabel` value is used verbatim.  Unmappable
corrections are skipped with a warning rather than guessed at.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import json
import logging
from pathlib import Path
from typing import Any

from twinklr.core.feature_engineering.active_learning.applier import CorrectionApplier
from twinklr.core.feature_engineering.active_learning.models import (
    CorrectionReport,
    ReviewBatch,
    TaxonomyCorrectionResult,
)
from twinklr.core.feature_engineering.active_learning.sampler import candidate_id_for
from twinklr.core.feature_engineering.models.phrases import EffectPhrase
from twinklr.core.feature_engineering.models.taxonomy import TaxonomyLabel
from twinklr.core.feature_engineering.taxonomy.classifier import DEFAULT_CORRECTIONS_PATH

logger = logging.getLogger(__name__)

CORRECTIONS_FILE_NAME = "taxonomy_corrections.json"
"""Name of the reviewer-authored file expected beside ``review_batch.json``."""

_CORRECTIONS_SCHEMA_VERSION = "1.0.0"
_CORRECTION_RULE_WEIGHT = 1.0

_FAMILY_TO_LABEL: dict[str, str] = {
    "bars": TaxonomyLabel.CHASE_PATTERN.value,
    "chase": TaxonomyLabel.CHASE_PATTERN.value,
    "marquee": TaxonomyLabel.CHASE_PATTERN.value,
    "pattern_bars": TaxonomyLabel.CHASE_PATTERN.value,
    "single_strand": TaxonomyLabel.CHASE_PATTERN.value,
    "candle": TaxonomyLabel.SPARKLE_OVERLAY.value,
    "shimmer": TaxonomyLabel.SPARKLE_OVERLAY.value,
    "snowflakes": TaxonomyLabel.SPARKLE_OVERLAY.value,
    "sparkle": TaxonomyLabel.SPARKLE_OVERLAY.value,
    "twinkle": TaxonomyLabel.SPARKLE_OVERLAY.value,
    "fireworks": TaxonomyLabel.BURST_IMPACT.value,
    "lightning": TaxonomyLabel.BURST_IMPACT.value,
    "strobe": TaxonomyLabel.BURST_IMPACT.value,
    "color": TaxonomyLabel.FILL_WASH.value,
    "color_wash": TaxonomyLabel.FILL_WASH.value,
    "fill": TaxonomyLabel.FILL_WASH.value,
    "on": TaxonomyLabel.FILL_WASH.value,
    "static": TaxonomyLabel.FILL_WASH.value,
    "butterfly": TaxonomyLabel.MOTION_DRIVER.value,
    "circles": TaxonomyLabel.MOTION_DRIVER.value,
    "morph": TaxonomyLabel.MOTION_DRIVER.value,
    "warp": TaxonomyLabel.MOTION_DRIVER.value,
    "wave": TaxonomyLabel.MOTION_DRIVER.value,
}

_MOTION_TO_LABEL: dict[str, str] = {
    "pulse": TaxonomyLabel.RHYTHM_DRIVER.value,
    "sparkle": TaxonomyLabel.SPARKLE_OVERLAY.value,
    "static": TaxonomyLabel.FILL_WASH.value,
    "sweep": TaxonomyLabel.MOTION_DRIVER.value,
}

_LABEL_VALUES: frozenset[str] = frozenset(label.value for label in TaxonomyLabel)


def resolve_correction_label(correction: TaxonomyCorrectionResult) -> str | None:
    """Resolve the taxonomy function label a correction should reinforce.

    Args:
        correction: An approved correction naming a corrected family and/or motion.

    Returns:
        A :class:`TaxonomyLabel` value, or ``None`` when the correction names
        nothing the classifier can score.
    """
    family = (correction.corrected_family or "").strip().lower()
    if family in _LABEL_VALUES:
        return family
    if family in _FAMILY_TO_LABEL:
        return _FAMILY_TO_LABEL[family]

    motion = (correction.corrected_motion or "").strip().lower()
    if motion in _LABEL_VALUES:
        return motion
    return _MOTION_TO_LABEL.get(motion)


def load_corrections_file(path: Path) -> tuple[TaxonomyCorrectionResult, ...]:
    """Parse a reviewer-authored corrections file.

    Args:
        path: Path to ``taxonomy_corrections.json``.

    Returns:
        The parsed corrections, in file order.

    Raises:
        ValueError: If the payload is neither a JSON array nor an object with a
            ``corrections`` array.
    """
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("corrections", [])
    if not isinstance(payload, list):
        raise ValueError(f"Invalid taxonomy corrections file at {path}")
    return tuple(TaxonomyCorrectionResult.model_validate(row) for row in payload)


def signatures_from_phrases(phrases: Iterable[EffectPhrase]) -> dict[str, str]:
    """Index param signatures by candidate id across a phrase corpus.

    Args:
        phrases: Phrases to index.

    Returns:
        Mapping of candidate_id -> param_signature.
    """
    return {
        candidate_id_for(phrase.effect_type, phrase.param_signature): phrase.param_signature
        for phrase in phrases
    }


def signatures_from_batch(batch: ReviewBatch) -> dict[str, str]:
    """Index param signatures by candidate id from a review batch.

    Args:
        batch: The batch handed to the reviewer.

    Returns:
        Mapping of candidate_id -> param_signature for every item in the batch.
    """
    signatures: dict[str, str] = {}
    for item in batch.items:
        _, _, param_signature = item.candidate.normalized_key.partition("::")
        signatures[item.candidate.candidate_id] = param_signature
    return signatures


def merge_corrections_into_config(
    corrections: Sequence[TaxonomyCorrectionResult],
    *,
    signatures: Mapping[str, str],
    config_path: Path,
) -> tuple[str, ...]:
    """Merge approved corrections into the git-tracked corrections config.

    Each approved correction becomes one additive rule
    ``{"id": "correction:<candidate_id>", "when": {"effect_type": ...,
    "param_signature": ...}, "weight": 1.0}`` under the label
    :func:`resolve_correction_label` resolves.  Existing rules are never
    rewritten or removed, and a rule id already present is left alone — so
    re-applying the same corrections file is a no-op.  The base rules config is
    never touched.

    Args:
        corrections: Corrections from the reviewer (unapproved ones are ignored).
        signatures: Mapping of candidate_id -> param_signature; corrections
            whose candidate is absent cannot be turned into a rule and are skipped.
        config_path: Path to the corrections config to update in place.

    Returns:
        The rule ids newly added, in insertion order.
    """
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError(f"Invalid corrections config at {config_path}")
    else:
        config = {"schema_version": _CORRECTIONS_SCHEMA_VERSION, "labels": {}}

    labels = config.setdefault("labels", {})
    if not isinstance(labels, dict):
        raise ValueError(f"Invalid corrections config at {config_path}")

    added: list[str] = []
    for correction in corrections:
        if not correction.approved:
            continue
        label = resolve_correction_label(correction)
        if label is None:
            logger.warning(
                "Skipping correction %s: no taxonomy label for family=%r motion=%r",
                correction.candidate_id,
                correction.corrected_family,
                correction.corrected_motion,
            )
            continue
        param_signature = signatures.get(correction.candidate_id)
        if param_signature is None:
            logger.warning(
                "Skipping correction %s: no known param signature for that candidate",
                correction.candidate_id,
            )
            continue

        rule_id = f"correction:{correction.candidate_id}"
        entry = labels.setdefault(label, {"base": 0.0, "min_confidence": 0.0, "rules": []})
        rules = entry.setdefault("rules", [])
        if any(isinstance(rule, dict) and rule.get("id") == rule_id for rule in rules):
            continue
        rules.append(
            {
                "id": rule_id,
                "when": {
                    "effect_type": correction.effect_type,
                    "param_signature": param_signature,
                },
                "weight": _CORRECTION_RULE_WEIGHT,
            }
        )
        added.append(rule_id)

    if added:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return tuple(added)


def apply_corrections_file(
    corrections_path: Path,
    *,
    taxonomy_overrides: dict[str, dict[str, str]] | None = None,
    signatures: Mapping[str, str] | None = None,
    config_path: Path | None = None,
) -> CorrectionReport | None:
    """Apply a reviewer-authored corrections file and persist it as rules.

    Args:
        corrections_path: Path to ``taxonomy_corrections.json``.  When it does
            not exist the loop has nothing to do.
        taxonomy_overrides: Mutable mapping of candidate_id ->
            ``{"family": str, "motion": str}``, updated in place with the
            corrected labels.  Metrics in the report are computed against it.
        signatures: Mapping of candidate_id -> param_signature, used to build
            the persisted rules' ``when`` clauses.
        config_path: Corrections config to merge into.  ``None`` applies the
            corrections without persisting them.

    Returns:
        The :class:`CorrectionReport`, or ``None`` if no corrections file exists.
    """
    if not corrections_path.exists():
        return None

    corrections = load_corrections_file(corrections_path)
    report = CorrectionApplier().apply(
        corrections, taxonomy_overrides if taxonomy_overrides is not None else {}
    )

    if config_path is not None:
        added = merge_corrections_into_config(
            corrections,
            signatures=signatures or {},
            config_path=config_path,
        )
        if added:
            logger.info("Merged %d taxonomy correction rule(s) into %s", len(added), config_path)
    return report


__all__ = [
    "CORRECTIONS_FILE_NAME",
    "DEFAULT_CORRECTIONS_PATH",
    "apply_corrections_file",
    "load_corrections_file",
    "merge_corrections_into_config",
    "resolve_correction_label",
    "signatures_from_batch",
    "signatures_from_phrases",
]
