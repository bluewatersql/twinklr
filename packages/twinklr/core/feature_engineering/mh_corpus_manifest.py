"""Fail-closed validation for an owner-local moving-head corpus manifest.

The source manifest is intentionally local and may contain private absolute paths. The
derived evidence document is safe to share: it binds the manifest by digest and exposes
only aggregate counts and the owner's sufficiency decision.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import hashlib
from pathlib import Path
import subprocess
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from twinklr.core.feature_engineering.evidence import (
    MHEvidenceManifest,
    P2KEvidenceManifest,
    Sha256Digest,
    StrictEvidenceModel,
    sha256_file,
)


class MovingHeadCorpusEntry(StrictEvidenceModel):
    """One provenance-bearing owner-local moving-head sequence."""

    package_id: str = Field(min_length=1)
    sequence_file_id: str = Field(min_length=1)
    vendor: str = Field(min_length=1)
    source_kind: Literal["owner_local_vendor_archive"]
    archive_path: Path
    archive_sha256: Sha256Digest
    sequence_path: Path
    sequence_sha256: Sha256Digest
    fixture_families: list[str] = Field(min_length=1)
    fixture_roles: list[str] = Field(min_length=1)

    @field_validator("archive_path", "sequence_path")
    @classmethod
    def _absolute_path(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("owner-local source paths must be absolute")
        return value

    @field_validator("fixture_families", "fixture_roles")
    @classmethod
    def _nonempty_unique_labels(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("labels must be non-empty")
        if len(normalized) != len(set(normalized)):
            raise ValueError("labels must be unique")
        return normalized


class MovingHeadCorpusSufficiency(StrictEvidenceModel):
    """Owner decision and explicit minima for allowing the P4-T7 spike."""

    decision: Literal["sufficient", "insufficient", "defer"]
    declared_by: str = Field(min_length=1)
    declared_at_utc: datetime
    minimum_sequences: Annotated[int, Field(strict=True, ge=1)]
    minimum_vendors: Annotated[int, Field(strict=True, ge=1)]
    minimum_fixture_families: Annotated[int, Field(strict=True, ge=1)]
    minimum_fixture_roles: Annotated[int, Field(strict=True, ge=1)]
    rationale: str = Field(min_length=1)

    @field_validator("declared_by", "rationale")
    @classmethod
    def _nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def _utc_declaration(self) -> MovingHeadCorpusSufficiency:
        if self.declared_at_utc.tzinfo is None or self.declared_at_utc.utcoffset() != UTC.utcoffset(
            self.declared_at_utc
        ):
            raise ValueError("declared_at_utc must be timezone-aware UTC")
        return self


class MovingHeadCorpusManifest(StrictEvidenceModel):
    """Private owner-local manifest consumed only by the offline validator."""

    schema_version: Literal["twinklr.mh-corpus-manifest.v1"]
    corpus_id: str = Field(min_length=1)
    created_at_utc: datetime
    entries: list[MovingHeadCorpusEntry] = Field(min_length=1)
    sufficiency: MovingHeadCorpusSufficiency

    @model_validator(mode="after")
    def _utc_created(self) -> MovingHeadCorpusManifest:
        if self.created_at_utc.tzinfo is None or self.created_at_utc.utcoffset() != UTC.utcoffset(
            self.created_at_utc
        ):
            raise ValueError("created_at_utc must be timezone-aware UTC")
        return self


def _require_private_manifest_location(manifest_path: Path, repository_root: Path) -> None:
    resolved_manifest = manifest_path.resolve()
    resolved_root = repository_root.resolve()
    try:
        relative = resolved_manifest.relative_to(resolved_root)
    except ValueError:
        return

    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative.as_posix()],
        cwd=resolved_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked.returncode == 0:
        raise ValueError("owner-local MH corpus manifest must not be tracked in git")
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", relative.as_posix()],
        cwd=resolved_root,
        check=False,
    )
    if ignored.returncode != 0:
        raise ValueError("owner-local MH corpus manifest inside the repository must be gitignored")


def _load_manifest(path: Path) -> MovingHeadCorpusManifest:
    try:
        return MovingHeadCorpusManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"cannot read MH corpus manifest: {error}") from error


def _validate_entry_files(entries: list[MovingHeadCorpusEntry]) -> None:
    logical_identities = [(entry.package_id, entry.sequence_file_id) for entry in entries]
    duplicate_logical = [key for key, count in Counter(logical_identities).items() if count > 1]
    if duplicate_logical:
        raise ValueError("duplicate logical sequence identity in MH corpus manifest")
    duplicate_content = [
        digest
        for digest, count in Counter(entry.sequence_sha256 for entry in entries).items()
        if count > 1
    ]
    if duplicate_content:
        raise ValueError("duplicate sequence content digest in MH corpus manifest")

    for entry in entries:
        for label, path, expected in (
            ("archive_sha256", entry.archive_path, entry.archive_sha256),
            ("sequence_sha256", entry.sequence_path, entry.sequence_sha256),
        ):
            if not path.is_file():
                raise ValueError(f"{label} source file does not exist: {path}")
            actual = sha256_file(path)
            if actual != expected:
                raise ValueError(f"{label} does not match owner-local file content")


def validate_mh_corpus_manifest(
    manifest_path: Path,
    *,
    p2k_evidence_path: Path,
    evidence_path: Path | None = None,
    require_sufficient: bool = False,
    repository_root: Path | None = None,
) -> dict[str, object]:
    """Validate private corpus evidence and optionally write a redacted digest binding."""
    manifest_path = manifest_path.resolve()
    p2k_evidence_path = p2k_evidence_path.resolve()
    root = repository_root or Path.cwd()
    _require_private_manifest_location(manifest_path, root)
    manifest = _load_manifest(manifest_path)
    p2k_evidence = P2KEvidenceManifest.model_validate_json(
        p2k_evidence_path.read_text(encoding="utf-8")
    )
    if p2k_evidence.accepted is not True:
        raise ValueError("P2K evidence is not owner-accepted")
    _validate_entry_files(manifest.entries)

    vendors = {entry.vendor for entry in manifest.entries}
    fixture_families = {label for entry in manifest.entries for label in entry.fixture_families}
    fixture_roles = {label for entry in manifest.entries for label in entry.fixture_roles}
    counts = {
        "sequences": len(manifest.entries),
        "vendors": len(vendors),
        "fixture_families": len(fixture_families),
        "fixture_roles": len(fixture_roles),
    }
    minimums = {
        "sequences": manifest.sufficiency.minimum_sequences,
        "vendors": manifest.sufficiency.minimum_vendors,
        "fixture_families": manifest.sufficiency.minimum_fixture_families,
        "fixture_roles": manifest.sufficiency.minimum_fixture_roles,
    }
    missing = [name for name, minimum in minimums.items() if counts[name] < minimum]
    if manifest.sufficiency.decision == "sufficient" and missing:
        raise ValueError(
            "owner declared sufficient but corpus misses declared minima: " + ", ".join(missing)
        )
    if require_sufficient and manifest.sufficiency.decision != "sufficient":
        raise ValueError("owner sufficiency decision is not sufficient")

    rationale_sha256 = hashlib.sha256(manifest.sufficiency.rationale.encode("utf-8")).hexdigest()
    evidence = MHEvidenceManifest.model_validate(
        {
            "schema_version": "twinklr.mh-corpus-evidence.v2",
            "manifest_sha256": sha256_file(manifest_path),
            "p2k_evidence_schema_version": p2k_evidence.schema_version,
            "p2k_evidence_sha256": sha256_file(p2k_evidence_path),
            "p2k_accepted_on": p2k_evidence.accepted_on,
            "counts": counts,
            "declared_minimums": minimums,
            "sufficiency": {
                "decision": manifest.sufficiency.decision,
                "declared_at_utc": manifest.sufficiency.declared_at_utc,
                "rationale_sha256": rationale_sha256,
                "meets_declared_minimums": not missing,
            },
            "redacted": True,
        }
    )
    if evidence_path is not None:
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(evidence.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return evidence.model_dump(mode="json")


__all__ = [
    "MovingHeadCorpusEntry",
    "MovingHeadCorpusManifest",
    "MovingHeadCorpusSufficiency",
    "validate_mh_corpus_manifest",
]
