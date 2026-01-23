"""Geometry handlers for moving head sequencer.

This package provides handlers that resolve static fixture positions
for various geometric formations and patterns.
"""

from blinkb0t.core.sequencer.moving_heads.handlers.geometry.alternating_updown import (
    AlternatingUpDownHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.audience_scan import (
    AudienceScanAsymHandler,
    AudienceScanHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.center_out import (
    CenterOutHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.chevron import (
    ChevronVHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.fan import FanHandler
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.mirror_lr import (
    MirrorLRHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.none import (
    NoneGeometryHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.rainbow_arc import (
    RainbowArcHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.role_pose import (
    RolePoseHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.role_pose_tilt_bias import (
    RolePoseTiltBiasHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.scattered import (
    ScatteredChaosHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.spotlight_cluster import (
    SpotlightClusterHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.tilt_bias_by_group import (
    TiltBiasByGroupHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.tunnel_cone import (
    TunnelConeHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.wall_wash import (
    WallWashHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.wave_lr import WaveLRHandler
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.x_cross import XCrossHandler

__all__ = [
    "AlternatingUpDownHandler",
    "AudienceScanAsymHandler",
    "AudienceScanHandler",
    "CenterOutHandler",
    "ChevronVHandler",
    "FanHandler",
    "MirrorLRHandler",
    "NoneGeometryHandler",
    "RainbowArcHandler",
    "RolePoseHandler",
    "RolePoseTiltBiasHandler",
    "ScatteredChaosHandler",
    "SpotlightClusterHandler",
    "TiltBiasByGroupHandler",
    "TunnelConeHandler",
    "WallWashHandler",
    "WaveLRHandler",
    "XCrossHandler",
]
