"""The structured diagnostic the moving-head renderer reports."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

DiagnosticCode = Literal[
    "unsupported_attribute",
    "unsupported_backend_channel",
    "unknown_initial_state",
    "unknown_motion_rate",
    "infeasible_transition",
    "lock_conflict",
    "output_budget_exceeded",
]
"""The shared contract's bounded code vocabulary (architecture §6)."""


class MHDiagnostic(BaseModel):
    """One structured moving-head diagnostic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: DiagnosticCode
    severity: Literal["info", "warning", "error"]
    message: str
    fixture_id: str | None = None
    section_id: str | None = None
    channel: str | None = None
    action: Literal["unchanged", "rejected", "substituted"]
