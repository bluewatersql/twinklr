"""Fail-closed validation for an owner-local moving-head corpus manifest.

The source manifest is intentionally local and may contain private absolute paths. The
derived evidence document is safe to share: it binds the manifest by digest and exposes
only aggregate counts and the owner's sufficiency decision.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MovingHeadCorpusEntry(BaseModel):
    """One provenance-bearing owner-local moving-head sequence."""

    model_config = ConfigDict(extra="forbid")

    package_id: str = Field(min_length=1)
    sequence_file_id: str = Field(min_length=1)
    vendor: str = Field(min_length=1)
    source_kind: Literal["owner_local_vendor_archive"]
    archive_path: Path
    archive_sha256: str
    sequence_path: Path
    sequence_sha256: str
    fixture_families: list[str] = Field(min_length=1)
    fixture_roles: list[str] = Field(min_length=1)

    @field_validator("archive_path", "sequence_path")
    @classmethod
    def _absolute_path(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("owner-local source paths must be absolute")
        return value

    @field_validator("archive_sha256", "sequence_sha256")
    @classmethod
    def _sha256_digest(cls, value: str) -> str:
        normalized = value.lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError("must be a 64-character SHA-256 digest")
        return normalized

    @field_validator("fixture_families", "fixture_roles")
    @classmethod
    def _nonempty_unique_labels(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("labels must be non-empty")
        if len(normalized) != len(set(normalized)):
            raise ValueError("labels must be unique")
        return normalized


class MovingHeadCorpusSufficiency(BaseModel):
    """Owner decision and explicit minima for allowing the P4-T7 spike."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["sufficient", "insufficient", "defer"]
    declared_by: str = Field(min_length=1)
    declared_at_utc: datetime
    minimum_sequences: int = Field(ge=1)
    minimum_vendors: int = Field(ge=1)
    minimum_fixture_families: int = Field(ge=1)
    minimum_fixture_roles: int = Field(ge=1)
    rationale: str = Field(min_length=1)


class MovingHeadCorpusManifest(BaseModel):
    """Private owner-local manifest consumed only by the offline validator."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["twinklr.mh-corpus-manifest.v1"]
    corpus_id: str = Field(min_length=1)
    created_at_utc: datetime
    entries: list[MovingHeadCorpusEntry] = Field(min_length=1)
    sufficiency: MovingHeadCorpusSufficiency


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read MH corpus manifest: {error}") from error
    return MovingHeadCorpusManifest.model_validate(raw)


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
            actual = _sha256(path)
            if actual != expected:
                raise ValueError(f"{label} does not match owner-local file content")


def validate_mh_corpus_manifest(
    manifest_path: Path,
    *,
    evidence_path: Path | None = None,
    require_sufficient: bool = False,
    repository_root: Path | None = None,
) -> dict[str, object]:
    """Validate private corpus evidence and optionally write a redacted digest binding."""
    manifest_path = manifest_path.resolve()
    root = repository_root or Path.cwd()
    _require_private_manifest_location(manifest_path, root)
    manifest = _load_manifest(manifest_path)
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
    evidence: dict[str, object] = {
        "schema_version": "twinklr.mh-corpus-evidence.v1",
        "manifest_sha256": _sha256(manifest_path),
        "counts": counts,
        "declared_minimums": minimums,
        "sufficiency": {
            "decision": manifest.sufficiency.decision,
            "declared_at_utc": manifest.sufficiency.declared_at_utc.isoformat(),
            "rationale_sha256": rationale_sha256,
            "meets_declared_minimums": not missing,
        },
        "privacy": {
            "redacted": True,
            "omitted": [
                "corpus_id",
                "package_id",
                "sequence_file_id",
                "vendor",
                "source_paths",
                "source_digests",
                "fixture_labels",
                "owner_identity",
                "rationale_text",
            ],
        },
    }
    if evidence_path is not None:
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return evidence


__all__ = [
    "MovingHeadCorpusEntry",
    "MovingHeadCorpusManifest",
    "MovingHeadCorpusSufficiency",
    "validate_mh_corpus_manifest",
]
