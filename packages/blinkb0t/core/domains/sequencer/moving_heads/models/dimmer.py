# sequencing_v2/dimmer/dimmer_models.py


from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.domains.sequencer.moving_heads.models.base import IntensityLevel
from blinkb0t.core.domains.sequencing.libraries.moving_heads.dimmers import DimmerID


class Dimmer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimmer_id: DimmerID
    intensity: IntensityLevel = IntensityLevel.SMOOTH
    min_norm: float = Field(0.0, ge=0.0, le=1.0)
    max_norm: float = Field(1.0, ge=0.0, le=1.0)
    cycles: float = Field(1.0, gt=0.0)
