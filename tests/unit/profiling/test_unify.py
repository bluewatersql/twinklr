"""Unit tests for profile corpus unifier."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from twinklr.core.profiling.constants import CORPUS_MANIFEST_SCHEMA_VERSION
from twinklr.core.profiling.unify import CorpusBuildOptions, ProfileCorpusBuilder


def _write_profile_dir(root: Path, name: str, *, structured: bool) -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)

    (d / "sequence_metadata.json").write_text(
        json.dumps(
            {
                "package_id": f"pkg-{name}",
                "sequence_file_id": f"seq-{name}",
                "sequence_sha256": f"sha-{name}",
                "song": "Song",
                "artist": "Artist",
                "sequence_duration_ms": 1000,
            }
        ),
        encoding="utf-8",
    )

    event = {
        "effect_event_id": f"evt-{name}",
        "target_name": "Arch 1",
        "layer_index": 0,
        "layer_name": "Main",
        "effect_type": "Bars",
        "start_ms": 0,
        "end_ms": 100,
        "config_fingerprint": "fp",
        "effectdb_ref": 0,
    }
    if structured:
        event.update(
            {
                "effectdb_settings_raw": "E_SLIDER_Speed=10",
                "effectdb_parse_status": "parsed",
                "effectdb_params": [
                    {
                        "namespace": "E",
                        "control_type": "SLIDER",
                        "param_name_raw": "Speed",
                        "param_name_normalized": "speed",
                        "value_raw": "10",
                        "value_type": "int",
                        "value_int": 10,
                        "value_float": 10.0,
                        "value_bool": None,
                        "value_string": None,
                    }
                ],
                "effectdb_parse_errors": [],
            }
        )

    (d / "base_effect_events.json").write_text(
        json.dumps(
            {
                "package_id": f"pkg-{name}",
                "sequence_file_id": f"seq-{name}",
                "sequence_sha256": f"sha-{name}",
                "events": [event],
            }
        ),
        encoding="utf-8",
    )

    (d / "enriched_effect_events.json").write_text(json.dumps([event]), encoding="utf-8")
    (d / "effect_statistics.json").write_text(json.dumps({"total_events": 1}), encoding="utf-8")
    (d / "lineage_index.json").write_text(
        json.dumps(
            {
                "package_id": f"pkg-{name}",
                "zip_sha256": f"zip-{name}",
                "sequence_file": {"file_id": f"seq-{name}", "filename": "sequence.xsq"},
                "rgb_sha256": None,
            }
        ),
        encoding="utf-8",
    )
    return d


def test_unify_groups_by_schema_version(tmp_path: Path) -> None:
    profiles_root = tmp_path / "profiles"
    output_root = tmp_path / "corpus"

    _write_profile_dir(profiles_root, "structured", structured=True)
    _write_profile_dir(profiles_root, "legacy", structured=False)

    builder = ProfileCorpusBuilder(
        CorpusBuildOptions(write_extent_mb=256, min_parse_success_ratio=0.5)
    )
    results = builder.build(profiles_root=profiles_root, output_root=output_root)

    assert len(results) == 2
    schema_versions = {result.schema_version for result in results}
    assert "v0_effectdb_structured_1" in schema_versions
    assert "legacy_profile_1" in schema_versions


def test_unify_writes_manifest_and_quality(tmp_path: Path) -> None:
    profiles_root = tmp_path / "profiles"
    output_root = tmp_path / "corpus"

    _write_profile_dir(profiles_root, "structured-a", structured=True)
    _write_profile_dir(profiles_root, "structured-b", structured=True)

    builder = ProfileCorpusBuilder(
        CorpusBuildOptions(write_extent_mb=256, min_parse_success_ratio=0.95)
    )
    results = builder.build(profiles_root=profiles_root, output_root=output_root)

    result = next(r for r in results if r.schema_version == "v0_effectdb_structured_1")
    manifest = json.loads((result.output_dir / "corpus_manifest.json").read_text(encoding="utf-8"))
    quality = json.loads((result.output_dir / "quality_report.json").read_text(encoding="utf-8"))

    assert manifest["write_extent_mb"] == 256
    assert manifest["manifest_schema_version"] == CORPUS_MANIFEST_SCHEMA_VERSION
    assert manifest["schema_version"] == "v0_effectdb_structured_1"
    assert quality["meets_minimum"] is True


def test_unify_deterministic_jsonl_and_manifest_order(tmp_path: Path) -> None:
    profiles_root = tmp_path / "profiles"
    output_root_a = tmp_path / "corpus_a"
    output_root_b = tmp_path / "corpus_b"

    _write_profile_dir(profiles_root, "b-structured", structured=True)
    _write_profile_dir(profiles_root, "a-structured", structured=True)

    builder = ProfileCorpusBuilder(
        CorpusBuildOptions(write_extent_mb=256, min_parse_success_ratio=0.95)
    )
    builder.build(profiles_root=profiles_root, output_root=output_root_a)
    builder.build(profiles_root=profiles_root, output_root=output_root_b)

    out_a = output_root_a / "v0_effectdb_structured_1"
    out_b = output_root_b / "v0_effectdb_structured_1"

    for fname in [
        "sequence_index.jsonl",
        "events_base.jsonl",
        "events_enriched.jsonl",
        "effectdb_params.jsonl",
        "lineage_index.jsonl",
    ]:
        assert (out_a / fname).read_text(encoding="utf-8") == (out_b / fname).read_text(
            encoding="utf-8"
        )

    man_a = json.loads((out_a / "corpus_manifest.json").read_text(encoding="utf-8"))
    man_b = json.loads((out_b / "corpus_manifest.json").read_text(encoding="utf-8"))
    assert man_a["source_profile_paths"] == man_b["source_profile_paths"]
    assert man_a["row_counts"] == man_b["row_counts"]


def test_unify_fail_on_quality_gate(tmp_path: Path) -> None:
    profiles_root = tmp_path / "profiles"
    output_root = tmp_path / "corpus"

    _write_profile_dir(profiles_root, "structured", structured=True)

    builder = ProfileCorpusBuilder(
        CorpusBuildOptions(
            write_extent_mb=256,
            min_parse_success_ratio=1.01,
            fail_on_quality_gate=True,
        )
    )
    with pytest.raises(ValueError, match="Quality gate failed"):
        builder.build(profiles_root=profiles_root, output_root=output_root)
