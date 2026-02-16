"""Common pipeline stages shared between display and moving-head pipelines.

Both the display sequencer and the moving-head sequencer share the same
audio analysis prefix: audio → profile + lyrics → macro. This module
provides a factory for those shared stages so each pipeline definition
can compose them without duplication.
"""

from __future__ import annotations

from twinklr.core.agents.audio.lyrics.stage import LyricsStage
from twinklr.core.agents.audio.profile.stage import AudioProfileStage
from twinklr.core.agents.audio.stages.analysis import AudioAnalysisStage
from twinklr.core.agents.sequencer.macro_planner.stage import MacroPlannerStage
from twinklr.core.pipeline import ExecutionPattern, StageDefinition


def build_common_stages(
    display_groups: list[dict[str, object]],
) -> list[StageDefinition]:
    """Build the shared pipeline prefix stages.

    Stages (in order):
        1. ``audio`` — Analyze audio file for tempo, structure, features
        2. ``profile`` — Generate musical analysis and creative guidance
        3. ``lyrics`` — Conditional lyric/narrative analysis (skipped if no lyrics)
        4. ``macro`` — Generate high-level choreography strategy

    The ``lyrics`` stage is conditional and non-critical: it runs only when
    the audio analysis detects lyrics (``has_lyrics`` state flag).

    Args:
        display_groups: Display group configurations for the MacroPlannerStage.
            Each dict must have ``role_key``, ``model_count``, and ``group_type``.

    Returns:
        List of 4 StageDefinitions in dependency order.

    Example:
        >>> stages = build_common_stages(display_groups=[
        ...     {"role_key": "OUTLINE", "model_count": 10, "group_type": "string"},
        ... ])
        >>> [s.id for s in stages]
        ['audio', 'profile', 'lyrics', 'macro']
    """
    return [
        StageDefinition(
            id="audio",
            stage=AudioAnalysisStage(),
            input_type="str",
            output_type="SongBundle",
            description="Analyze audio file for tempo, structure, features",
        ),
        StageDefinition(
            id="profile",
            stage=AudioProfileStage(),
            inputs=["audio"],
            input_type="SongBundle",
            output_type="AudioProfileModel",
            description="Generate musical analysis and creative guidance",
        ),
        StageDefinition(
            id="lyrics",
            stage=LyricsStage(),
            inputs=["audio"],
            pattern=ExecutionPattern.CONDITIONAL,
            condition=lambda ctx: ctx.get_state("has_lyrics", False),
            critical=False,
            input_type="SongBundle",
            output_type="LyricContextModel",
            description="Generate narrative and thematic analysis (if lyrics available)",
        ),
        StageDefinition(
            id="macro",
            stage=MacroPlannerStage(display_groups=display_groups),
            inputs=["profile", "lyrics"],
            input_type="dict[str, Any]",
            output_type="list[MacroSectionPlan]",
            description="Generate high-level choreography strategy",
        ),
    ]
