from blinkb0t.core.config.poses import PanPose
from blinkb0t.core.sequencer.models.enum import TemplateRole


class TemplateRoleHelper:
    IN_OUT_LEFT_RIGHT = [
        TemplateRole.OUTER_LEFT,
        TemplateRole.INNER_LEFT,
        TemplateRole.INNER_RIGHT,
        TemplateRole.OUTER_RIGHT,
    ]


class PoseByRoleHelper:
    FAN_POSE_WIDE = {
        TemplateRole.OUTER_LEFT: PanPose.WIDE_LEFT,
        TemplateRole.INNER_LEFT: PanPose.LEFT,
        TemplateRole.INNER_RIGHT: PanPose.RIGHT,
        TemplateRole.OUTER_RIGHT: PanPose.WIDE_RIGHT,
    }
