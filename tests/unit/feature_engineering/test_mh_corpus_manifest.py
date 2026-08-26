"""Owner-local moving-head corpus manifest contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from twinklr.core.feature_engineering.mh_corpus_manifest import validate_mh_corpus_manifest


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(tmp_path: Path, *, sufficient: bool = True) -> Path:
    archive = tmp_path / "owner-vendor-pack.zip"
    sequence = tmp_path / "moving-head-show.xsq"
    archive.write_bytes(b"synthetic archive")
    sequence.write_bytes(b"synthetic sequence")
    manifest = tmp_path / "mh-corpus-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "twinklr.mh-corpus-manifest.v1",
                "corpus_id": "owner-local-mh-corpus",
                "created_at_utc": "2026-08-26T12:00:00Z",
                "entries": [
                    {
                        "package_id": "vendor-pack-1",
                        "sequence_file_id": "show-1",
                        "vendor": "synthetic-vendor",
                        "source_kind": "owner_local_vendor_archive",
                        "archive_path": str(archive.resolve()),
                        "archive_sha256": _sha256(archive),
                        "sequence_path": str(sequence.resolve()),
                        "sequence_sha256": _sha256(sequence),
                        "fixture_families": ["beam"],
                        "fixture_roles": ["air"],
                    }
                ],
                "sufficiency": {
                    "decision": "sufficient" if sufficient else "insufficient",
                    "declared_by": "owner",
                    "declared_at_utc": "2026-08-26T12:00:00Z",
                    "minimum_sequences": 1,
                    "minimum_vendors": 1,
                    "minimum_fixture_families": 1,
                    "minimum_fixture_roles": 1,
                    "rationale": "Synthetic declaration for contract validation.",
                },
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_manifest_validator_hashes_owner_files_and_emits_redacted_evidence(
    tmp_path: Path,
) -> None:
    manifest = _manifest(tmp_path)
    evidence_path = tmp_path / "mh-corpus-evidence.json"

    evidence = validate_mh_corpus_manifest(
        manifest,
        evidence_path=evidence_path,
        require_sufficient=True,
        repository_root=Path(__file__).parents[3],
    )

    assert evidence["schema_version"] == "twinklr.mh-corpus-evidence.v1"
    assert evidence["manifest_sha256"] == _sha256(manifest)
    assert evidence["counts"] == {
        "sequences": 1,
        "vendors": 1,
        "fixture_families": 1,
        "fixture_roles": 1,
    }
    assert evidence["sufficiency"]["decision"] == "sufficient"
    assert len(evidence["sufficiency"]["rationale_sha256"]) == 64
    serialized = evidence_path.read_text(encoding="utf-8")
    assert "owner-vendor-pack.zip" not in serialized
    assert "moving-head-show.xsq" not in serialized
    assert "synthetic-vendor" not in serialized
    assert "show-1" not in serialized


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("wrong_hash", "sequence_sha256"),
        ("duplicate_identity", "duplicate logical sequence identity"),
        ("duplicate_content", "duplicate sequence content digest"),
        ("insufficient_counts", "declared sufficient"),
        ("relative_path", "absolute"),
    ],
)
def test_manifest_validator_rejects_invalid_or_insufficient_owner_evidence(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    manifest = _manifest(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    entry = payload["entries"][0]
    if mutation == "wrong_hash":
        entry["sequence_sha256"] = "0" * 64
    elif mutation == "relative_path":
        entry["sequence_path"] = "relative/show.xsq"
    elif mutation == "duplicate_identity":
        payload["entries"].append(dict(entry))
    elif mutation == "duplicate_content":
        duplicate = dict(entry)
        duplicate["package_id"] = "vendor-pack-2"
        duplicate["sequence_file_id"] = "show-2"
        payload["entries"].append(duplicate)
    elif mutation == "insufficient_counts":
        payload["sufficiency"]["minimum_sequences"] = 2
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        validate_mh_corpus_manifest(
            manifest,
            require_sufficient=True,
            repository_root=Path(__file__).parents[3],
        )


def test_manifest_validator_requires_owner_sufficiency_declaration(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, sufficient=False)

    with pytest.raises(ValueError, match="owner sufficiency decision is not sufficient"):
        validate_mh_corpus_manifest(
            manifest,
            require_sufficient=True,
            repository_root=Path(__file__).parents[3],
        )
