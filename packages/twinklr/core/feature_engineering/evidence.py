"""Typed, strict evidence contracts shared by owner-run tooling."""

from __future__ import annotations

from datetime import UTC, date, datetime
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StringConstraints,
    field_validator,
    model_validator,
)

Sha256Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
NumericValue = StrictInt | StrictFloat
NumericValueName = Literal[
    "recipe_promotion_min_support",
    "recipe_promotion_min_stability",
    "promotion_run_default_min_support",
    "promotion_run_default_min_stability",
    "propensity_min_support",
    "target_role_score_cutoff",
    "recipe_promotion_max_per_family",
    "recipe_promotion_max_per_cluster",
]

NUMERIC_VALUE_NAMES: tuple[str, ...] = (
    "recipe_promotion_min_support",
    "recipe_promotion_min_stability",
    "promotion_run_default_min_support",
    "promotion_run_default_min_stability",
    "propensity_min_support",
    "target_role_score_cutoff",
    "recipe_promotion_max_per_family",
    "recipe_promotion_max_per_cluster",
)


class StrictEvidenceModel(BaseModel):
    """Base for exact evidence schemas: no coercion and no unknown fields."""

    model_config = ConfigDict(extra="forbid", strict=True)


class OwnerDecision(StrictEvidenceModel):
    """One owner-authored decision over a bound numeric review value."""

    name: NumericValueName
    current_value: NumericValue
    decision: Literal["keep", "change", "defer"]
    changed_value: NumericValue | None
    decided_on: date
    rationale: str = Field(min_length=1)

    @field_validator("rationale")
    @classmethod
    def _nonblank_rationale(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("rationale must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def _decision_value_contract(self) -> OwnerDecision:
        if (
            self.changed_value is not None
            and isinstance(self.changed_value, float)
            and not math.isfinite(self.changed_value)
        ):
            raise ValueError("changed_value must be finite")
        if self.decision == "change" and self.changed_value is None:
            raise ValueError("change decision requires changed_value")
        if self.decision != "change" and self.changed_value is not None:
            raise ValueError("changed_value is allowed only for a change decision")
        if self.changed_value is not None:
            integer_names = {
                "recipe_promotion_min_support",
                "promotion_run_default_min_support",
                "propensity_min_support",
                "recipe_promotion_max_per_family",
                "recipe_promotion_max_per_cluster",
            }
            if self.name in integer_names:
                if type(self.changed_value) is not int or self.changed_value < 1:
                    raise ValueError("changed_value must be a positive integer for this value")
            elif type(self.changed_value) is not float or not 0.0 <= self.changed_value <= 1.0:
                raise ValueError("changed_value must be a float between zero and one")
        return self


class OwnerDecisionRecord(StrictEvidenceModel):
    """Exactly one decision for each numeric value in the review contract."""

    schema_version: Literal["twinklr.owner-threshold-decisions.v1"]
    report_schema_version: Literal["quality_gate_distribution_report_v2"]
    report_sha256: Sha256Digest
    review_bundle_schema_version: Literal["twinklr.quality-gate-review-bundle.v1"]
    review_bundle_sha256: Sha256Digest
    decisions: list[OwnerDecision] = Field(min_length=8, max_length=8)

    @model_validator(mode="after")
    def _one_decision_per_value(self) -> OwnerDecisionRecord:
        names = tuple(decision.name for decision in self.decisions)
        if len(set(names)) != len(names) or set(names) != set(NUMERIC_VALUE_NAMES):
            raise ValueError("decisions must contain exactly one decision for each numeric value")
        return self


class ArtifactDigest(StrictEvidenceModel):
    """One path-addressed artifact digest."""

    path: str = Field(min_length=1)
    size_bytes: StrictInt = Field(ge=0)
    sha256: Sha256Digest


class TreeSnapshot(StrictEvidenceModel):
    """Deterministic snapshot of a bounded staging tree."""

    root: str = Field(min_length=1)
    exists: StrictBool
    file_count: StrictInt = Field(ge=0)
    sha256: Sha256Digest | None
    files: list[ArtifactDigest]

    @model_validator(mode="after")
    def _unique_paths(self) -> TreeSnapshot:
        paths = [artifact.path for artifact in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("tree snapshot artifact paths must be unique")
        if self.file_count != len(self.files):
            raise ValueError("tree snapshot file_count must equal files length")
        return self


class SourceProvenance(StrictEvidenceModel):
    git_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    git_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    tracked_diff_sha256: Sha256Digest


class ToolProvenance(StrictEvidenceModel):
    path: str = Field(min_length=1)
    exists: StrictBool
    sha256: Sha256Digest


class CorpusFileProvenance(StrictEvidenceModel):
    path: str = Field(min_length=1)
    size_bytes: StrictInt = Field(ge=0)
    sha256: Sha256Digest


class CorpusProvenance(StrictEvidenceModel):
    path: str = Field(min_length=1)
    tree_sha256: Sha256Digest
    files: dict[str, CorpusFileProvenance]
    input_fingerprint_sha256: Sha256Digest


class ProfileProvenance(StrictEvidenceModel):
    package_id: str = Field(min_length=1)
    sequence_file_id: str = Field(min_length=1)
    sequence_sha256: Sha256Digest
    path: str = Field(min_length=1)
    tree_sha256: Sha256Digest
    file_count: StrictInt = Field(ge=1)
    files: list[ArtifactDigest]


class MusicIndexProvenance(StrictEvidenceModel):
    path: str | None
    exists: StrictBool
    size_bytes: StrictInt | None = Field(default=None, ge=0)
    sha256: Sha256Digest | None
    explicitly_disabled: StrictBool

    @model_validator(mode="after")
    def _existence_contract(self) -> MusicIndexProvenance:
        present = self.path is not None and self.size_bytes is not None and self.sha256 is not None
        if self.exists != present or self.explicitly_disabled == self.exists:
            raise ValueError("music-index provenance fields disagree")
        return self


class RunProvenance(StrictEvidenceModel):
    source: SourceProvenance
    tools: dict[str, ToolProvenance]
    corpus: CorpusProvenance
    profiles: list[ProfileProvenance]
    music_library_index: MusicIndexProvenance


class MiningInvocation(StrictEvidenceModel):
    exact_command: str = Field(min_length=1)
    exact_rerun_command: str = Field(min_length=1)
    effective_options: dict[str, object]


class RerunVerification(StrictEvidenceModel):
    previous_run_after_stats: dict[str, object] | None
    current_run_before_stats: dict[str, object] | None
    current_run_after_stats: dict[str, object] | None
    before_matches_previous_after: StrictBool
    after_matches_before: StrictBool
    input_fingerprint_matches_previous: StrictBool
    source_provenance_matches_previous: StrictBool
    entity_key_digests_match: StrictBool
    entity_content_digests_match: StrictBool
    duplicate_identity_count: StrictInt = Field(ge=0)
    verified_unchanged_rerun: StrictBool
    status: Literal["needs_identical_second_run", "changed", "verified"]


class ContentHashIdentity(StrictEvidenceModel):
    required: StrictBool
    implementation: str = Field(min_length=1)
    verification: RerunVerification


class CandidateStaging(StrictEvidenceModel):
    recursive_artifacts: TreeSnapshot
    note: str = Field(min_length=1)


class CorpusRunIdentity(StrictEvidenceModel):
    path: str = Field(min_length=1)
    sequence_index_sha256: Sha256Digest


class FeatureStoreReference(StrictEvidenceModel):
    backend: Literal["sqlite"]
    path: str = Field(min_length=1)


class StoreSnapshots(StrictEvidenceModel):
    before: dict[str, object]
    after: dict[str, object]


class LiveCatalogImmutability(StrictEvidenceModel):
    before: TreeSnapshot
    after: TreeSnapshot
    unchanged: StrictBool


class MiningRunManifest(StrictEvidenceModel):
    """Exact manifest shared by owner mining and threshold review."""

    schema_version: Literal["twinklr.owner-mining-run.v2"]
    created_at_utc: datetime
    invocation: MiningInvocation
    corpus: CorpusRunIdentity
    output_dir: str = Field(min_length=1)
    sequence_count: StrictInt = Field(ge=1)
    provenance: RunProvenance
    candidate_staging: CandidateStaging
    content_hash_identity: ContentHashIdentity
    feature_store: FeatureStoreReference
    feature_store_snapshots: StoreSnapshots
    live_catalog_immutability: LiveCatalogImmutability

    @model_validator(mode="after")
    def _utc_timestamp(self) -> MiningRunManifest:
        if self.created_at_utc.tzinfo is None or self.created_at_utc.utcoffset() != UTC.utcoffset(
            self.created_at_utc
        ):
            raise ValueError("created_at_utc must be timezone-aware UTC")
        return self


ArtifactRole = Literal[
    "mining_manifest",
    "content_candidates",
    "orchestration_candidates",
    "promotion_report",
    "distribution_report_json",
    "distribution_report_markdown",
]


class EvidenceArtifact(ArtifactDigest):
    role: ArtifactRole


class QualityGateReviewBundle(StrictEvidenceModel):
    schema_version: Literal["twinklr.quality-gate-review-bundle.v1"]
    created_at_utc: datetime
    mining_manifest_schema_version: Literal["twinklr.owner-mining-run.v2"]
    mining_manifest_sha256: Sha256Digest
    report_schema_version: Literal["quality_gate_distribution_report_v2"]
    report_sha256: Sha256Digest
    artifacts: list[EvidenceArtifact]

    @model_validator(mode="after")
    def _artifact_contract(self) -> QualityGateReviewBundle:
        if self.created_at_utc.tzinfo is None or self.created_at_utc.utcoffset() != UTC.utcoffset(
            self.created_at_utc
        ):
            raise ValueError("created_at_utc must be timezone-aware UTC")
        roles = [artifact.role for artifact in self.artifacts]
        paths = [artifact.path for artifact in self.artifacts]
        required = {
            "mining_manifest",
            "promotion_report",
            "distribution_report_json",
            "distribution_report_markdown",
        }
        if len(roles) != len(set(roles)) or len(paths) != len(set(paths)):
            raise ValueError("review-bundle artifact roles and paths must be unique")
        if not required.issubset(roles) or not {
            "content_candidates",
            "orchestration_candidates",
        }.intersection(roles):
            raise ValueError("review bundle is missing required artifacts")
        return self


class P2KEvidenceManifest(StrictEvidenceModel):
    """Final accepted P2K evidence consumed by the MH prerequisite validator."""

    schema_version: Literal["twinklr.p2k-evidence.v2"]
    created_at_utc: datetime
    review_bundle_schema_version: Literal["twinklr.quality-gate-review-bundle.v1"]
    review_bundle_sha256: Sha256Digest
    decision_schema_version: Literal["twinklr.owner-threshold-decisions.v1"]
    decision_sha256: Sha256Digest
    accepted: StrictBool
    accepted_on: date

    @model_validator(mode="after")
    def _utc_timestamp(self) -> P2KEvidenceManifest:
        if self.created_at_utc.tzinfo is None or self.created_at_utc.utcoffset() != UTC.utcoffset(
            self.created_at_utc
        ):
            raise ValueError("created_at_utc must be timezone-aware UTC")
        return self


class MHEvidenceCounts(StrictEvidenceModel):
    sequences: StrictInt = Field(ge=1)
    vendors: StrictInt = Field(ge=1)
    fixture_families: StrictInt = Field(ge=1)
    fixture_roles: StrictInt = Field(ge=1)


class MHSufficiencyEvidence(StrictEvidenceModel):
    decision: Literal["sufficient", "insufficient", "defer"]
    declared_at_utc: datetime
    rationale_sha256: Sha256Digest
    meets_declared_minimums: StrictBool

    @model_validator(mode="after")
    def _utc_timestamp(self) -> MHSufficiencyEvidence:
        if self.declared_at_utc.tzinfo is None or self.declared_at_utc.utcoffset() != UTC.utcoffset(
            self.declared_at_utc
        ):
            raise ValueError("declared_at_utc must be timezone-aware UTC")
        return self


class MHEvidenceManifest(StrictEvidenceModel):
    """Redacted combined re-entry binding for both P4-T7 prerequisites."""

    schema_version: Literal["twinklr.mh-corpus-evidence.v2"]
    manifest_sha256: Sha256Digest
    p2k_evidence_schema_version: Literal["twinklr.p2k-evidence.v2"]
    p2k_evidence_sha256: Sha256Digest
    p2k_accepted_on: date
    counts: MHEvidenceCounts
    declared_minimums: MHEvidenceCounts
    sufficiency: MHSufficiencyEvidence
    redacted: Literal[True]


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 digest of a file without loading it all at once."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    """Hash a JSON-compatible value using the repository's canonical representation."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _overlaps(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def validate_owner_run_paths(
    *,
    output_dir: Path,
    feature_store_db: Path,
    protected_roots: tuple[Path, ...],
) -> None:
    """Reject staging paths that could overwrite a protected input or live catalog."""
    resolved_output = output_dir.resolve(strict=False)
    resolved_store = feature_store_db.resolve(strict=False)
    if not resolved_store.is_relative_to(resolved_output) or resolved_store == resolved_output:
        raise ValueError("feature store must be a file inside the dedicated output directory")
    for root in protected_roots:
        resolved_root = root.resolve(strict=False)
        if _overlaps(resolved_output, resolved_root):
            raise ValueError(
                f"owner output overlaps protected root: {resolved_output} and {resolved_root}"
            )


def _safe_descendants(root: Path) -> list[Path]:
    """Preflight a tree without following links and return deepest paths first."""
    resolved_root = root.resolve(strict=True)
    pending = [root]
    descendants: list[Path] = []
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                mode = path.lstat().st_mode
                if stat.S_ISLNK(mode):
                    raise ValueError(f"refusing symbolic link in owned output: {path}")
                resolved = path.resolve(strict=True)
                if not resolved.is_relative_to(resolved_root) or resolved == resolved_root:
                    raise ValueError(f"owned output descendant escapes resolved root: {path}")
                descendants.append(path)
                if stat.S_ISDIR(mode):
                    pending.append(path)
    return sorted(descendants, key=lambda path: len(path.parts), reverse=True)


def clean_owned_output_dir(output_dir: Path, *, preserved_paths: tuple[Path, ...]) -> None:
    """Clean a pre-owned staging tree only after a no-follow containment preflight."""
    if not output_dir.exists():
        output_dir.mkdir(parents=True)
        return
    root_mode = output_dir.lstat().st_mode
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        raise ValueError("owned output root must be a real directory, not a symbolic link")
    resolved_root = output_dir.resolve(strict=True)
    preserved = {path.resolve(strict=False) for path in preserved_paths}
    if any(not path.is_relative_to(resolved_root) for path in preserved):
        raise ValueError("preserved path escapes owned output root")
    descendants = _safe_descendants(output_dir)
    for path in descendants:
        resolved = path.resolve(strict=True)
        if resolved in preserved:
            continue
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            if not any(path.iterdir()):
                path.rmdir()
        else:
            path.unlink()


def verify_staged_artifacts(
    snapshot: TreeSnapshot,
    run_dir: Path,
    *,
    required_paths: tuple[str, ...],
) -> None:
    """Verify every consumed review input against the mining-time snapshot."""
    by_path = {artifact.path: artifact for artifact in snapshot.files}
    resolved_root = run_dir.resolve(strict=True)
    for relative in required_paths:
        expected = by_path.get(relative)
        if expected is None:
            raise ValueError(f"review input not present in mining snapshot: {relative}")
        path = run_dir / relative
        mode = path.lstat().st_mode
        if not stat.S_ISREG(mode):
            raise ValueError(f"review input must be a regular staged file: {relative}")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(resolved_root):
            raise ValueError(f"review input escapes staged root: {relative}")
        if path.stat().st_size != expected.size_bytes or sha256_file(path) != expected.sha256:
            raise ValueError(f"staged artifact digest mismatch: {relative}")


def verify_evidence_artifacts(artifacts: list[EvidenceArtifact], run_dir: Path) -> None:
    """Verify every path bound by a review bundle against its current bytes."""
    resolved_root = run_dir.resolve(strict=True)
    for artifact in artifacts:
        path = run_dir / artifact.path
        mode = path.lstat().st_mode
        if not stat.S_ISREG(mode):
            raise ValueError(f"bound evidence artifact must be a regular file: {artifact.path}")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(resolved_root):
            raise ValueError(f"bound evidence artifact escapes run directory: {artifact.path}")
        if path.stat().st_size != artifact.size_bytes or sha256_file(path) != artifact.sha256:
            raise ValueError(f"bound evidence artifact digest mismatch: {artifact.path}")


def snapshot_tree(root: Path) -> TreeSnapshot:
    """Snapshot a bounded tree deterministically without following symbolic links."""
    if not root.exists():
        return TreeSnapshot(root=str(root), exists=False, file_count=0, sha256=None, files=[])
    resolved_root = root.resolve(strict=True)
    artifacts: list[ArtifactDigest] = []
    aggregate = hashlib.sha256()
    for path in sorted(_safe_descendants(root)):
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError(f"tree snapshot supports only regular files: {path}")
        relative = path.relative_to(root).as_posix()
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(resolved_root):
            raise ValueError(f"tree snapshot path escapes root: {relative}")
        digest = sha256_file(path)
        artifacts.append(
            ArtifactDigest(path=relative, size_bytes=path.stat().st_size, sha256=digest)
        )
        aggregate.update(relative.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(digest.encode("ascii"))
        aggregate.update(b"\0")
    return TreeSnapshot(
        root=str(root),
        exists=True,
        file_count=len(artifacts),
        sha256=aggregate.hexdigest(),
        files=artifacts,
    )


__all__ = [
    "NUMERIC_VALUE_NAMES",
    "MHEvidenceManifest",
    "MiningRunManifest",
    "OwnerDecision",
    "OwnerDecisionRecord",
    "P2KEvidenceManifest",
    "QualityGateReviewBundle",
    "Sha256Digest",
    "canonical_sha256",
    "clean_owned_output_dir",
    "sha256_file",
    "snapshot_tree",
    "validate_owner_run_paths",
    "verify_evidence_artifacts",
    "verify_staged_artifacts",
]
