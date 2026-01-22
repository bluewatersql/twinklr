from __future__ import annotations

from blinkb0t.core.curves.library import CurveId
from blinkb0t.core.sequencer.moving_heads.models.intensity import Intensity
from pydantic import BaseModel, ConfigDict, Field


class DimmerCategoricalParams(BaseModel):
    """Categorical parameters for dimmer intensity levels."""

    model_config = ConfigDict(frozen=True)

    min_intensity: int = Field(ge=0, le=255)
    max_intensity: int = Field(ge=0, le=255)
    period: float = Field(gt=0.0)  # Period in bars\


class DimmerPattern(BaseModel):
    """Definition of a dimmer pattern."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str

    curve: CurveId
    base_params: dict[str, float | int | str] = Field(default_factory=dict)
    categorical_params: dict[Intensity, DimmerCategoricalParams]


DEFAULT_DIMMER_PARAMS = {
    Intensity.SMOOTH: DimmerCategoricalParams(min_intensity=0, max_intensity=128, period=4.0),
    Intensity.DRAMATIC: DimmerCategoricalParams(min_intensity=0, max_intensity=224, period=1.25),
    Intensity.INTENSE: DimmerCategoricalParams(min_intensity=0, max_intensity=255, period=0.25),
}


class DimmerLibrary:
    """Library of predefined dimmer patterns."""

    PATTERNS: dict[str, DimmerPattern] = {
        "fade_in": DimmerPattern(
            id="fade_in",
            name="Fade In",
            description="Linear fade from 0 to full intensity",
            curve=CurveId.RAMP,
            categorical_params={
                Intensity.SMOOTH: DimmerCategoricalParams(
                    min_intensity=0, max_intensity=128, period=4.0
                ),
                Intensity.DRAMATIC: DimmerCategoricalParams(
                    min_intensity=0, max_intensity=255, period=1.0
                ),
                Intensity.INTENSE: DimmerCategoricalParams(
                    min_intensity=0, max_intensity=255, period=0.5
                ),
            },
        ),
        "fade_out": DimmerPattern(
            id="fade_out",
            name="Fade Out",
            description="Linear fade from full intensity to 0",
            curve=CurveId.RAMP,
            categorical_params={
                Intensity.SMOOTH: DimmerCategoricalParams(
                    min_intensity=0, max_intensity=128, period=4.0
                ),
                Intensity.DRAMATIC: DimmerCategoricalParams(
                    min_intensity=0, max_intensity=255, period=1.0
                ),
                Intensity.INTENSE: DimmerCategoricalParams(
                    min_intensity=0, max_intensity=255, period=0.5
                ),
            },
        ),
        "hold": DimmerPattern(
            id="hold",
            name="Hold",
            description="Hold intensity at full",
            curve=CurveId.HOLD,
            categorical_params={
                Intensity.SMOOTH: DimmerCategoricalParams(
                    min_intensity=0, max_intensity=128, period=4.0
                ),
                Intensity.DRAMATIC: DimmerCategoricalParams(
                    min_intensity=0, max_intensity=255, period=1.0
                ),
                Intensity.INTENSE: DimmerCategoricalParams(
                    min_intensity=0, max_intensity=255, period=0.5
                ),
            },
        ),
        "pulse": DimmerPattern(
            id="pulse",
            name="Pulse",
            description="Pulse intensity between min and max",
            curve=CurveId.PULSE,
            categorical_params={
                Intensity.SMOOTH: DimmerCategoricalParams(
                    min_intensity=0, max_intensity=128, period=4.0
                ),
                Intensity.DRAMATIC: DimmerCategoricalParams(
                    min_intensity=0, max_intensity=255, period=1.0
                ),
                Intensity.INTENSE: DimmerCategoricalParams(
                    min_intensity=0, max_intensity=255, period=0.5
                ),
            },
        ),
    }
