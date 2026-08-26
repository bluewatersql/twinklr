"""Strict, replayable inputs for deterministic combined-show evaluation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.sequencer.display.xlights_mapping import XLightsMapping
from twinklr.core.sequencer.planning import MacroPlan
from twinklr.core.sequencer.templates.group.models.choreography import ChoreographyGraph

SHA256_PATTERN = r"^[0-9a-f]{64}$"
MANIFEST_VERSION = "twinklr-show-evaluation-manifest.v1"
TRACE_VERSION = "twinklr-xsq-trace.v2"


class ShowCapability(BaseModel):
    """Which rendered backends are actually present in the artifact."""

    has_display: bool
    has_moving_heads: bool
    cross_part_applicable: bool

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def require_truthful_cross_part_capability(self) -> ShowCapability:
        if self.cross_part_applicable != (self.has_display and self.has_moving_heads):
            raise ValueError("cross_part_applicable must equal display && moving-head capability")
        return self


class MovingHeadTraceSource(BaseModel):
    """Strict source identity carried by a moving-head trace entry."""

    fixture_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", frozen=True)


class FallbackSubstitution(BaseModel):
    """Explicit display effect substitution provenance."""

    requested_effect_type: str = Field(min_length=1)
    substituted_effect_type: str = Field(min_length=1)
    reason: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", frozen=True)


class ShowTraceEntry(BaseModel):
    """The trace-v2 fields evaluation consumes; unknown fields fail closed."""

    element_name: str = Field(min_length=1)
    effect_name: str = Field(min_length=1)
    logical_layer: int = Field(ge=0)
    file_layer: int = Field(ge=0)
    live_layer: int = Field(ge=0)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    effectdb_ref: int = Field(ge=0)
    palette_ref: int | None = Field(default=None, ge=0)
    backend: Literal["display", "moving_head"]
    event_id: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    lane: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    placement_id: str | None = None
    placement_index: int | None = Field(default=None, ge=0)
    fallback_substitution: FallbackSubstitution | None = None
    sources: list[MovingHeadTraceSource] | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def valid_interval(self) -> ShowTraceEntry:
        if self.end_ms <= self.start_ms:
            raise ValueError("trace entry end_ms must be greater than start_ms")
        if self.backend == "moving_head" and not self.sources:
            raise ValueError("moving-head trace entries require sources")
        if self.backend == "display" and self.sources is not None:
            raise ValueError("display trace entries may not carry moving-head sources")
        return self


class ShowTraceV2(BaseModel):
    """Strict trace-v2 document with count integrity."""

    schema_version: Literal["twinklr-xsq-trace.v2"]
    entry_count: int = Field(ge=0)
    fallback_substitutions: int = Field(ge=0)
    entries: list[ShowTraceEntry]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def count_matches(self) -> ShowTraceV2:
        if self.entry_count != len(self.entries):
            raise ValueError("trace entry_count does not match entries")
        actual_fallbacks = sum(entry.fallback_substitution is not None for entry in self.entries)
        if self.fallback_substitutions != actual_fallbacks:
            raise ValueError("trace fallback_substitutions does not match substituted entries")
        return self


class ShowEvaluationManifest(BaseModel):
    """Today's typed show contract and immutable artifact provenance."""

    schema_version: Literal["twinklr-show-evaluation-manifest.v1"] = (
        "twinklr-show-evaluation-manifest.v1"
    )
    xsq_path: Path
    trace_path: Path
    xsq_sha256: str = Field(pattern=SHA256_PATTERN)
    trace_sha256: str = Field(pattern=SHA256_PATTERN)
    macro_plan_sha256: str = Field(pattern=SHA256_PATTERN)
    choreography_graph_sha256: str = Field(pattern=SHA256_PATTERN)
    xlights_mapping_sha256: str = Field(pattern=SHA256_PATTERN)
    macro_plan: MacroPlan
    choreography_graph: ChoreographyGraph
    xlights_mapping: XLightsMapping
    moving_head_target_ids: list[str]
    capability: ShowCapability

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_contract(self) -> ShowEvaluationManifest:
        if not self.moving_head_target_ids == sorted(set(self.moving_head_target_ids)):
            raise ValueError("moving_head_target_ids must be sorted and unique")
        graph_ids = {group.id for group in self.choreography_graph.groups}
        if not set(self.moving_head_target_ids) <= graph_ids:
            raise ValueError("moving_head_target_ids must exist in choreography_graph")
        mapping_ids = [entry.choreo_id for entry in self.xlights_mapping.entries]
        if len(mapping_ids) != len(set(mapping_ids)):
            raise ValueError("xLights mapping contains duplicate choreography ids")
        if set(mapping_ids) != graph_ids:
            raise ValueError(
                "xLights mapping must cover every choreography graph group exactly once"
            )
        expected = {
            "macro_plan_sha256": identity_sha256(self.macro_plan),
            "choreography_graph_sha256": identity_sha256(self.choreography_graph),
            "xlights_mapping_sha256": identity_sha256(self.xlights_mapping),
        }
        for field, digest in expected.items():
            if getattr(self, field) != digest:
                raise ValueError(f"{field} does not match embedded current model")
        if self.capability.has_moving_heads != bool(self.moving_head_target_ids):
            raise ValueError("moving-head capability does not match target ownership")
        return self


def identity_sha256(value: BaseModel) -> str:
    """Stable hash of a current Pydantic model without computed lookup fields."""
    payload = value.model_dump(mode="json", exclude_computed_fields=True)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    """Hash a required regular file."""
    if not path.is_file():
        raise FileNotFoundError(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_show_evaluation_manifest(
    *,
    path: Path,
    xsq_path: Path,
    trace_path: Path,
    macro_plan: MacroPlan,
    choreography_graph: ChoreographyGraph,
    xlights_mapping: XLightsMapping,
    moving_head_target_ids: set[str] | frozenset[str],
) -> ShowEvaluationManifest:
    """Validate the emitted trace and atomically write a relative-path manifest."""
    trace = load_show_trace(trace_path)
    backends = {entry.backend for entry in trace.entries}
    ids = sorted(moving_head_target_ids)
    manifest = ShowEvaluationManifest(
        xsq_path=Path(xsq_path.name),
        trace_path=Path(trace_path.name),
        xsq_sha256=file_sha256(xsq_path),
        trace_sha256=file_sha256(trace_path),
        macro_plan_sha256=identity_sha256(macro_plan),
        choreography_graph_sha256=identity_sha256(choreography_graph),
        xlights_mapping_sha256=identity_sha256(xlights_mapping),
        macro_plan=macro_plan,
        choreography_graph=choreography_graph,
        xlights_mapping=xlights_mapping,
        moving_head_target_ids=ids,
        capability=ShowCapability(
            has_display="display" in backends,
            has_moving_heads="moving_head" in backends,
            cross_part_applicable={"display", "moving_head"} <= backends,
        ),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        manifest.model_dump_json(indent=2, exclude_computed_fields=True),
        encoding="utf-8",
    )
    temporary.replace(path)
    return manifest


def load_show_trace(path: Path) -> ShowTraceV2:
    """Load trace-v2 strictly; trace-v1 and unknown backends are rejected."""
    return cast("ShowTraceV2", ShowTraceV2.model_validate_json(path.read_text(encoding="utf-8")))


def load_show_evaluation_manifest(path: Path) -> ShowEvaluationManifest:
    """Load a manifest and verify all relative artifact references and hashes."""
    manifest = ShowEvaluationManifest.model_validate_json(path.read_text(encoding="utf-8"))
    if manifest.xsq_path.is_absolute() or manifest.trace_path.is_absolute():
        raise ValueError("show evaluation artifact paths must be relative to the manifest")
    xsq_path = path.parent / manifest.xsq_path
    trace_path = path.parent / manifest.trace_path
    if file_sha256(xsq_path) != manifest.xsq_sha256:
        raise ValueError("XSQ SHA-256 does not match show evaluation manifest")
    if file_sha256(trace_path) != manifest.trace_sha256:
        raise ValueError("trace SHA-256 does not match show evaluation manifest")
    trace = load_show_trace(trace_path)
    backends = {entry.backend for entry in trace.entries}
    if manifest.capability.has_display != ("display" in backends):
        raise ValueError("display capability does not match trace")
    if manifest.capability.has_moving_heads != ("moving_head" in backends):
        raise ValueError("moving-head capability does not match trace")
    return cast("ShowEvaluationManifest", manifest)


__all__ = [
    "MANIFEST_VERSION",
    "ShowCapability",
    "ShowEvaluationManifest",
    "ShowTraceEntry",
    "ShowTraceV2",
    "file_sha256",
    "identity_sha256",
    "load_show_evaluation_manifest",
    "load_show_trace",
    "write_show_evaluation_manifest",
]
