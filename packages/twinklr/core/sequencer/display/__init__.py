"""Display renderer package.

Renders GroupPlanSet into xLights .xsq effects for pixel/display models.
This is the non-moving-head rendering pipeline.
"""

from twinklr.core.sequencer.display.renderer import (
    DisplayRenderer,
    RenderResult,
)

__all__ = [
    "DisplayRenderer",
    "RenderResult",
]
