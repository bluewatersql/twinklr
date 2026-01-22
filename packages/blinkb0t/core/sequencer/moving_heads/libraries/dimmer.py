from __future__ import annotations

from enum import Enum

from blinkb0t.core.curves.library import CurveLibrary
from blinkb0t.core.sequencer.models.enum import Intensity
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

    curve: CurveLibrary
    base_params: dict[str, float | int | str] = Field(default_factory=dict)
    categorical_params: dict[Intensity, DimmerCategoricalParams]


DEFAULT_DIMMER_PARAMS = {
    Intensity.SMOOTH: DimmerCategoricalParams(min_intensity=0, max_intensity=128, period=4.0),
    Intensity.DRAMATIC: DimmerCategoricalParams(min_intensity=0, max_intensity=224, period=1.25),
    Intensity.INTENSE: DimmerCategoricalParams(min_intensity=0, max_intensity=255, period=0.25),
}


class DimmerType(str, Enum):
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    HOLD = "hold"
    PULSE = "pulse"
    NONE = "none"


class DimmerLibrary:
    """Library of predefined dimmer patterns."""

    PATTERNS: dict[DimmerType, DimmerPattern] = {
        DimmerType.FADE_IN: DimmerPattern(
            id="fade_in",
            name="Fade In",
            description="Linear fade from 0 to full intensity",
            curve=CurveLibrary.LINEAR,
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
        DimmerType.FADE_OUT: DimmerPattern(
            id="fade_out",
            name="Fade Out",
            description="Linear fade from full intensity to 0",
            curve=CurveLibrary.LINEAR,
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
        DimmerType.HOLD: DimmerPattern(
            id="hold",
            name="Hold",
            description="Hold intensity at full",
            curve=CurveLibrary.HOLD,
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
        DimmerType.PULSE: DimmerPattern(
            id="pulse",
            name="Pulse",
            description="Pulse intensity between min and max",
            curve=CurveLibrary.PULSE,
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

    @classmethod
    def get_all_metadata(cls) -> list[dict[str, str]]:
        """Get metadata for all dimmer patterns (optimized for LLM context).

        Returns:
            List of dictionaries with pattern metadata

        Example:
            >>> meta = DimmerLibrary.get_all_metadata()
            >>> meta[0]["dimmer_id"]
            'fade_in'
        """
        return [
            {
                "dimmer_id": pattern.id,
                "name": pattern.name,
                "description": pattern.description,
                "curve": pattern.curve.value,
            }
            for pattern in cls.PATTERNS.values()
        ]
