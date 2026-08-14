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
    """Preset pan pose mappings for common layouts.

    Every role in the spatial vocabulary is mapped, not only the four a 4-head rig
    uses: a role with no entry falls back to a centred pan, so on a larger rig the
    fixtures outside the four-head vocabulary all pointed straight ahead. There are
    fewer pan poses than roles, so the outermost pairs share the widest pose.
    """

    FAN_POSE_WIDE: ClassVar[dict[TemplateRole, PanPose]] = {
        TemplateRole.FAR_LEFT: PanPose.WIDE_LEFT,
        TemplateRole.OUTER_LEFT: PanPose.WIDE_LEFT,
        TemplateRole.MID_LEFT: PanPose.MID_LEFT,
        TemplateRole.CENTER_LEFT: PanPose.MID_LEFT,
        TemplateRole.INNER_LEFT: PanPose.LEFT,
        TemplateRole.LEFT: PanPose.LEFT,
        TemplateRole.CENTER: PanPose.CENTER,
        TemplateRole.RIGHT: PanPose.RIGHT,
        TemplateRole.INNER_RIGHT: PanPose.RIGHT,
        TemplateRole.CENTER_RIGHT: PanPose.MID_RIGHT,
        TemplateRole.MID_RIGHT: PanPose.MID_RIGHT,
        TemplateRole.OUTER_RIGHT: PanPose.WIDE_RIGHT,
        TemplateRole.FAR_RIGHT: PanPose.WIDE_RIGHT,
    }

    FAN_POSE_NARROW: ClassVar[dict[TemplateRole, PanPose]] = {
        TemplateRole.FAR_LEFT: PanPose.MID_LEFT,
        TemplateRole.OUTER_LEFT: PanPose.MID_LEFT,
        TemplateRole.MID_LEFT: PanPose.MID_LEFT,
        TemplateRole.CENTER_LEFT: PanPose.LEFT,
        TemplateRole.INNER_LEFT: PanPose.LEFT,
        TemplateRole.LEFT: PanPose.LEFT,
        TemplateRole.CENTER: PanPose.CENTER,
        TemplateRole.RIGHT: PanPose.RIGHT,
        TemplateRole.INNER_RIGHT: PanPose.RIGHT,
        TemplateRole.CENTER_RIGHT: PanPose.RIGHT,
        TemplateRole.MID_RIGHT: PanPose.MID_RIGHT,
        TemplateRole.OUTER_RIGHT: PanPose.MID_RIGHT,
        TemplateRole.FAR_RIGHT: PanPose.MID_RIGHT,
    }
