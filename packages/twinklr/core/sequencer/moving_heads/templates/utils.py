from typing import ClassVar

from twinklr.core.config.poses import PanPose
from twinklr.core.sequencer.models.enum import TemplateRole


class TemplateRoleHelper:
    IN_OUT_LEFT_RIGHT: ClassVar[list[TemplateRole]] = [
        TemplateRole.OUTER_LEFT,
        TemplateRole.INNER_LEFT,
        TemplateRole.INNER_RIGHT,
        TemplateRole.OUTER_RIGHT,
    ]


class PoseByRoleHelper:
    """Preset pan pose mappings for common layouts."""

    FAN_POSE_WIDE: ClassVar[dict[TemplateRole, PanPose]] = {
        TemplateRole.OUTER_LEFT: PanPose.WIDE_LEFT,
        TemplateRole.INNER_LEFT: PanPose.LEFT,
        TemplateRole.INNER_RIGHT: PanPose.RIGHT,
        TemplateRole.OUTER_RIGHT: PanPose.WIDE_RIGHT,
    }

    FAN_POSE_NARROW: ClassVar[dict[TemplateRole, PanPose]] = {
        TemplateRole.OUTER_LEFT: PanPose.MID_LEFT,
        TemplateRole.INNER_LEFT: PanPose.LEFT,
        TemplateRole.INNER_RIGHT: PanPose.RIGHT,
        TemplateRole.OUTER_RIGHT: PanPose.MID_RIGHT,
    }
