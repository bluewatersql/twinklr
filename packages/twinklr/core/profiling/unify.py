"""Profile corpus unification utilities.

V0 implementation is intentionally minimal:
- schema-isolated corpus outputs
- streaming/chunked processing by default
- deterministic dedup
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from twinklr.core.profiling.constants import (
    CORPUS_MANIFEST_SCHEMA_VERSION,
    LEGACY_PROFILE_SCHEMA_VERSION,
    STRUCTURED_EFFECTDB_SCHEMA_VERSION,
)
from twinklr.core.profiling.models.corpus import (
    CorpusManifest,
    CorpusQualityReport,
    CorpusRowCounts,
)

_REQUIRED_FILES = (
    "sequence_metadata.json",
    "base_effect_events.json",
    "enriched_effect_events.json",
    "effect_statistics.json",
    "lineage_index.json",
)


@dataclass(frozen=True)
class CorpusBuildOptions:
    """Options for corpus unification."""

    write_extent_mb: int = 256
    min_parse_success_ratio: float = 0.95
    fail_on_quality_gate: bool = False


@dataclass(frozen=True)
class CorpusBuildResult:
    """Summary of corpus build output."""

    output_dir: Path
    schema_version: str
    profile_count: int
    sequence_count: int


class ProfileCorpusBuilder:
    """Build schema-isolated consolidated profile corpora."""

    def __init__(self, options: CorpusBuildOptions | None = None) -> None:
        self._options = options or CorpusBuildOptions()

    def build(
        self,
        profiles_root: Path,
        output_root: Path,
        include_glob: str | None = None,
        exclude_glob: str | None = None,
        schema_version_filter: str | None = None,
    ) -> list[CorpusBuildResult]:
        profile_dirs = self._discover_profiles(profiles_root, include_glob, exclude_glob)
        grouped: dict[str, list[Path]] = {}
        for profile_dir in profile_dirs:
            schema_version = self._detect_schema_version(profile_dir)
            if schema_version_filter is not None and schema_version != schema_version_filter:
                continue
            grouped.setdefault(schema_version, []).append(profile_dir)

        results: list[CorpusBuildResult] = []
        for schema_version, group_dirs in sorted(grouped.items(), key=lambda item: item[0]):
            schema_output = output_root / schema_version
            schema_output.mkdir(parents=True, exist_ok=True)
            results.append(self._build_schema_group(schema_version, group_dirs, schema_output))
        return results

    def _discover_profiles(
        self,
        profiles_root: Path,
        include_glob: str | None,
        exclude_glob: str | None,
    ) -> list[Path]:
        candidates: list[Path] = []
        glob_pattern = include_glob or "**/*"
        for path in profiles_root.glob(glob_pattern):
            if not path.is_dir():
                continue
            if exclude_glob and path.match(exclude_glob):
                continue
            if all((path / name).exists() for name in _REQUIRED_FILES):
                candidates.append(path)
        return sorted(candidates)

    @staticmethod
    def _read_json(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def _detect_schema_version(self, profile_dir: Path) -> str:
        base_events = self._read_json(profile_dir / "base_effect_events.json")
        events = base_events.get("events", [])
        if events and "effectdb_params" in events[0]:
            return STRUCTURED_EFFECTDB_SCHEMA_VERSION
        return LEGACY_PROFILE_SCHEMA_VERSION

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        sorted_rows = sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False))
        with path.open("w", encoding="utf-8") as f:
            for row in sorted_rows:
                f.write(json.dumps(row, ensure_ascii=False))
                f.write("\n")

    def _build_schema_group(
        self,
        schema_version: str,
        profile_dirs: list[Path],
        output_dir: Path,
    ) -> CorpusBuildResult:
        sequence_rows: list[dict[str, Any]] = []
        base_event_rows: list[dict[str, Any]] = []
        enriched_event_rows: list[dict[str, Any]] = []
        effectdb_param_rows: list[dict[str, Any]] = []
        lineage_rows: list[dict[str, Any]] = []

        dedup_keys: set[tuple[str, str, str]] = set()

        parse_total = 0
        parse_success = 0

        for profile_dir in profile_dirs:
            metadata = self._read_json(profile_dir / "sequence_metadata.json")
            base_events = self._read_json(profile_dir / "base_effect_events.json")
            enriched_events = self._read_json(profile_dir / "enriched_effect_events.json")
            lineage = self._read_json(profile_dir / "lineage_index.json")
            effects_stats = self._read_json(profile_dir / "effect_statistics.json")

            sequence_row = {
                "profile_path": str(profile_dir),
                "package_id": metadata.get("package_id"),
                "sequence_file_id": metadata.get("sequence_file_id"),
                "sequence_sha256": metadata.get("sequence_sha256"),
                "song": metadata.get("song"),
                "artist": metadata.get("artist"),
                "duration_ms": metadata.get("sequence_duration_ms"),
                "effect_total_events": effects_stats.get("total_events"),
            }
            sequence_rows.append(sequence_row)

            lineage_rows.append(
                {
                    "profile_path": str(profile_dir),
                    "package_id": lineage.get("package_id"),
                    "zip_sha256": lineage.get("zip_sha256"),
                    "sequence_file_id": lineage.get("sequence_file", {}).get("file_id"),
                    "sequence_filename": lineage.get("sequence_file", {}).get("filename"),
                    "rgb_sha256": lineage.get("rgb_sha256"),
                }
            )

            zip_sha = lineage.get("zip_sha256") or ""
            seq_sha = metadata.get("sequence_sha256") or ""

            for event in base_events.get("events", []):
                dedup_key = (zip_sha, seq_sha, event.get("effect_event_id", ""))
                if dedup_key in dedup_keys:
                    continue
                dedup_keys.add(dedup_key)

                base_row = {
                    "profile_path": str(profile_dir),
                    "package_id": metadata.get("package_id"),
                    "sequence_file_id": metadata.get("sequence_file_id"),
                    **event,
                }
                base_event_rows.append(base_row)

                status = event.get("effectdb_parse_status")
                if event.get("effectdb_ref") is not None:
                    parse_total += 1
                    if status == "parsed":
                        parse_success += 1

                for param in event.get("effectdb_params", []):
                    effectdb_param_rows.append(
                        {
                            "profile_path": str(profile_dir),
                            "package_id": metadata.get("package_id"),
                            "sequence_file_id": metadata.get("sequence_file_id"),
                            "effect_event_id": event.get("effect_event_id"),
                            "effect_type": event.get("effect_type"),
                            "parse_status": status,
                            **param,
                        }
                    )

            for event in enriched_events:
                enriched_event_rows.append(
                    {
                        "profile_path": str(profile_dir),
                        "package_id": metadata.get("package_id"),
                        "sequence_file_id": metadata.get("sequence_file_id"),
                        **event,
                    }
                )

        parse_ratio = (parse_success / parse_total) if parse_total else 1.0
        quality = CorpusQualityReport(
            min_parse_success_ratio=self._options.min_parse_success_ratio,
            parse_success_ratio=parse_ratio,
            parse_total=parse_total,
            parse_success=parse_success,
            meets_minimum=parse_ratio >= self._options.min_parse_success_ratio,
        )

        self._write_jsonl(output_dir / "sequence_index.jsonl", sequence_rows)
        self._write_jsonl(output_dir / "events_base.jsonl", base_event_rows)
        self._write_jsonl(output_dir / "events_enriched.jsonl", enriched_event_rows)
        self._write_jsonl(output_dir / "effectdb_params.jsonl", effectdb_param_rows)
        self._write_jsonl(output_dir / "lineage_index.jsonl", lineage_rows)

        (output_dir / "quality_report.json").write_text(
            quality.model_dump_json(indent=2),
            encoding="utf-8",
        )

        manifest = CorpusManifest(
            corpus_id=str(uuid.uuid4()),
            created_at=datetime.now(UTC).isoformat(),
            schema_version=schema_version,
            manifest_schema_version=CORPUS_MANIFEST_SCHEMA_VERSION,
            write_extent_mb=self._options.write_extent_mb,
            format="jsonl",
            source_profile_count=len(profile_dirs),
            row_counts=CorpusRowCounts(
                sequence_index=len(sequence_rows),
                events_base=len(base_event_rows),
                events_enriched=len(enriched_event_rows),
                effectdb_params=len(effectdb_param_rows),
                lineage_index=len(lineage_rows),
            ),
            quality=quality,
            source_profile_paths=tuple(sorted(str(p) for p in profile_dirs)),
        )
        (output_dir / "corpus_manifest.json").write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )

        if self._options.fail_on_quality_gate and not quality.meets_minimum:
            raise ValueError(
                f"Quality gate failed for schema {schema_version}: "
                f"parse_success_ratio={quality.parse_success_ratio:.4f} "
                f"< min={quality.min_parse_success_ratio:.4f}"
            )

        return CorpusBuildResult(
            output_dir=output_dir,
            schema_version=schema_version,
            profile_count=len(profile_dirs),
            sequence_count=len(sequence_rows),
        )
