"""Sequencing v2 core models (Step 1 – MVP).

This module defines the foundational Pydantic models for a clean,
compiler-based moving-head sequencing architecture.

Guiding principles implemented here:
- Fixtures, groups, and orders are *rig config* (not templates)
- Pydantic for all models
- Validation ensures config correctness early
- Models are data-only (no rendering); helpers are minimal and side-effect free

You can drop this into your repo and wire it up via DI.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# -------------------------
# Playback plan (what to compile)
# -------------------------


class PlaybackWindowBars(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_bar: float = Field(default=0.0, ge=0.0)
    duration_bars: float = Field(..., gt=0.0)


class PlaybackPlan(BaseModel):
    """Request to compile a template for a given time window."""

    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(..., min_length=1)
    preset_id: str | None = Field(default=None, description="Optional preset to apply")

    window: PlaybackWindowBars

    # Optional categorical knobs (shape depends on your schema).
    modifiers: dict[str, Any] = Field(default_factory=dict)

    # Optional per-cycle overrides (MVP: leave as Any; formalize later)
    per_cycle_overrides: list[dict[str, Any]] = Field(default_factory=list)
