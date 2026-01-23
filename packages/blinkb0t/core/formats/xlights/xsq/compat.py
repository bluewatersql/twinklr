from __future__ import annotations

from blinkb0t.core.formats.xlights.models.effect_placement import EffectPlacement
from blinkb0t.core.formats.xlights.models.xsq import Effect


def effect_placement_to_effect(placement: EffectPlacement) -> Effect:
    """Convert EffectPlacement to Effect model.

    Args:
        placement: EffectPlacement dataclass

    Returns:
        Effect model
    """
    return Effect(
        effect_type=placement.effect_name,
        start_time_ms=placement.start_ms,
        end_time_ms=placement.end_ms,
        palette=str(placement.palette) if placement.palette else "0",
        ref=placement.ref,
        label=placement.effect_label,
        parameters={},
    )
