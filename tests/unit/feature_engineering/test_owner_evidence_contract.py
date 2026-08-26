"""Strict public contracts for owner-run and decision evidence."""

from __future__ import annotations

from datetime import UTC, date, datetime

from pydantic import ValidationError
import pytest

from twinklr.core.feature_engineering.evidence import (
    ArtifactDigest,
    OwnerDecision,
    OwnerDecisionRecord,
    P2KEvidenceManifest,
    TreeSnapshot,
    sha256_file,
    verify_staged_artifacts,
)

VALUE_NAMES = (
    "recipe_promotion_min_support",
    "recipe_promotion_min_stability",
    "promotion_run_default_min_support",
    "promotion_run_default_min_stability",
    "propensity_min_support",
    "target_role_score_cutoff",
    "recipe_promotion_max_per_family",
    "recipe_promotion_max_per_cluster",
)


def _decision(name: str, *, decision: str = "keep", changed_value: object = None) -> dict:
    return {
        "name": name,
        "current_value": 1,
        "decision": decision,
        "changed_value": changed_value,
        "decided_on": date(2026, 8, 26),
        "rationale": "Owner reviewed the bound sensitivity evidence.",
    }


def _record() -> dict:
    return {
        "schema_version": "twinklr.owner-threshold-decisions.v1",
        "report_schema_version": "quality_gate_distribution_report_v2",
        "report_sha256": "1" * 64,
        "review_bundle_schema_version": "twinklr.quality-gate-review-bundle.v1",
        "review_bundle_sha256": "2" * 64,
        "decisions": [_decision(name) for name in VALUE_NAMES],
    }


def test_owner_decision_record_requires_exactly_one_typed_decision_per_value() -> None:
    parsed = OwnerDecisionRecord.model_validate(_record())
    assert tuple(decision.name for decision in parsed.decisions) == VALUE_NAMES

    duplicate = _record()
    duplicate["decisions"][-1] = duplicate["decisions"][0]
    with pytest.raises(ValidationError, match="exactly one decision"):
        OwnerDecisionRecord.model_validate(duplicate)

    extra = _record()
    extra["unexpected"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        OwnerDecisionRecord.model_validate(extra)


@pytest.mark.parametrize("changed_value", [None, True, "3", float("nan")])
def test_change_decision_requires_a_finite_numeric_changed_value(changed_value: object) -> None:
    with pytest.raises(ValidationError, match="changed_value"):
        OwnerDecision.model_validate(
            _decision(
                "recipe_promotion_min_support",
                decision="change",
                changed_value=changed_value,
            )
        )


def test_keep_or_defer_decision_rejects_a_changed_value_and_fake_date() -> None:
    with pytest.raises(ValidationError, match="changed_value"):
        OwnerDecision.model_validate(_decision("recipe_promotion_min_support", changed_value=2))
    payload = _decision("recipe_promotion_min_support")
    payload["decided_on"] = "not-a-date"
    with pytest.raises(ValidationError):
        OwnerDecision.model_validate(payload)

    payload = _decision("recipe_promotion_min_support")
    payload["rationale"] = "   "
    with pytest.raises(ValidationError, match="rationale"):
        OwnerDecision.model_validate(payload)


@pytest.mark.parametrize(
    ("name", "changed_value"),
    [
        ("recipe_promotion_min_support", 1.5),
        ("recipe_promotion_max_per_family", 0),
        ("recipe_promotion_min_stability", 2.0),
        ("target_role_score_cutoff", 1),
    ],
)
def test_changed_values_follow_the_numeric_value_domain(name: str, changed_value: object) -> None:
    with pytest.raises(ValidationError, match="changed_value"):
        OwnerDecision.model_validate(
            _decision(name, decision="change", changed_value=changed_value)
        )


def test_p2k_evidence_rejects_coercive_boolean_and_wrong_version() -> None:
    payload = {
        "schema_version": "twinklr.p2k-evidence.v2",
        "created_at_utc": datetime(2026, 8, 26, tzinfo=UTC),
        "review_bundle_schema_version": "twinklr.quality-gate-review-bundle.v1",
        "review_bundle_sha256": "1" * 64,
        "decision_schema_version": "twinklr.owner-threshold-decisions.v1",
        "decision_sha256": "2" * 64,
        "accepted": "true",
        "accepted_on": date(2026, 8, 26),
    }
    with pytest.raises(ValidationError):
        P2KEvidenceManifest.model_validate(payload)
    payload["accepted"] = True
    payload["schema_version"] = "twinklr.p2k-evidence.v1"
    with pytest.raises(ValidationError):
        P2KEvidenceManifest.model_validate(payload)


def test_staged_artifact_verification_rejects_tamper_or_injected_review_input(
    tmp_path,
) -> None:
    candidate = tmp_path / "content_templates.json"
    candidate.write_text('{"templates": []}', encoding="utf-8")
    digest = ArtifactDigest(
        path=candidate.name,
        size_bytes=candidate.stat().st_size,
        sha256=sha256_file(candidate),
    )
    snapshot = TreeSnapshot(
        root=str(tmp_path),
        exists=True,
        file_count=1,
        sha256="3" * 64,
        files=[digest],
    )
    verify_staged_artifacts(snapshot, tmp_path, required_paths=(candidate.name,))

    candidate.write_text('{"templates": ["tampered"]}', encoding="utf-8")
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_staged_artifacts(snapshot, tmp_path, required_paths=(candidate.name,))

    injected = tmp_path / "target_roles.jsonl"
    injected.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not present in mining snapshot"):
        verify_staged_artifacts(snapshot, tmp_path, required_paths=(injected.name,))
