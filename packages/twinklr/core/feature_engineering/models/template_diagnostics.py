"""Template diagnostics contracts for mined-template quality review."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.feature_engineering.models.templates import TemplateKind


class TemplateDiagnosticFlag(str, Enum):
    """Flags indicating a potentially low-value template."""

    LOW_SUPPORT = "low_support"
    HIGH_CONCENTRATION = "high_concentration"
    HIGH_VARIANCE = "high_variance"
    OVER_GENERIC = "over_generic"


class TemplateDiagnosticThresholds(BaseModel):
    """Thresholds used to compute template diagnostics flags."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    low_support_max_count: int = Field(ge=1)
    high_concentration_min_ratio: float = Field(ge=0.0, le=1.0)
    high_variance_min_score: float = Field(ge=0.0, le=1.0)
    over_generic_min_support_count: int = Field(ge=1)
    over_generic_max_dominant_taxonomy_ratio: float = Field(ge=0.0, le=1.0)


class TemplateDiagnosticRow(BaseModel):
    """Per-template diagnostics row."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    template_id: str
    template_kind: TemplateKind
    effect_family: str
    role: str | None = None

    support_count: int = Field(ge=0)
    distinct_pack_count: int = Field(ge=0)
    distinct_sequence_count: int = Field(ge=0)

    concentration_ratio: float = Field(ge=0.0, le=1.0)
    dominant_taxonomy_label: str
    dominant_taxonomy_ratio: float = Field(ge=0.0, le=1.0)
    variance_score: float = Field(ge=0.0, le=1.0)

    flags: tuple[TemplateDiagnosticFlag, ...] = ()


class TemplateDiagnosticsReport(BaseModel):
    """Corpus-level template diagnostics artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    diagnostics_version: str
    thresholds: TemplateDiagnosticThresholds

    total_templates: int = Field(ge=0)
    flagged_template_count: int = Field(ge=0)

    low_support_templates: tuple[str, ...] = ()
    high_concentration_templates: tuple[str, ...] = ()
    high_variance_templates: tuple[str, ...] = ()
    over_generic_templates: tuple[str, ...] = ()

    rows: tuple[TemplateDiagnosticRow, ...] = ()
