# sequencing_v2/movement/movement_models.py
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.domains.sequencer.moving_heads.models.base import IntensityLevel
from blinkb0t.core.domains.sequencing.libraries.moving_heads.movements import MovementID


class MovementSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    movement_id: MovementID
    intensity: IntensityLevel = IntensityLevel.SMOOTH
    cycles: float = Field(1.0, gt=0.0)  # how many oscillations over the step
