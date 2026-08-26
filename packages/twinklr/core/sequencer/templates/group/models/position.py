"""Categorical display position shared by choreography consumers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from twinklr.core.sequencer.vocabulary.spatial import (
    DepthZone,
    DisplayZone,
    HorizontalZone,
    VerticalZone,
)


class GroupPosition(BaseModel):
    """Categorical spatial position for a choreography group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    horizontal: HorizontalZone = HorizontalZone.CENTER
    vertical: VerticalZone = VerticalZone.MID
    depth: DepthZone = DepthZone.NEAR
    zone: DisplayZone | None = None
