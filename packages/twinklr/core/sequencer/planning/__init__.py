"""Planning domain - strategic planning models.

Models for macro-level and group-level choreography planning.
"""

from twinklr.core.sequencer.planning.group_plan import (
    CorrectionResult,
    Deviation,
    GroupPlanSet,
    LanePlan,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.planning.models import (
    CallResponsePair,
    FocalAssignment,
    FocalRole,
    FocalRoleKind,
    MacroPlan,
    MacroSection,
    MotifEvolution,
    MotifThread,
    PaletteRef,
    PaletteRoleRef,
    PaletteStop,
    PaletteTransition,
)

__all__ = [
    # Group planning output models
    "CallResponsePair",
    "CorrectionResult",
    "Deviation",
    # Macro planning models
    "FocalAssignment",
    "FocalRole",
    "FocalRoleKind",
    "GroupPlanSet",
    "LanePlan",
    "MacroPlan",
    "MacroSection",
    "MotifEvolution",
    "MotifThread",
    "PaletteRef",
    "PaletteRoleRef",
    "PaletteStop",
    "PaletteTransition",
    "SectionCoordinationPlan",
]
