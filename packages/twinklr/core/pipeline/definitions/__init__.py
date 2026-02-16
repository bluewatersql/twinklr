"""Pipeline definitions — reusable factory functions for building pipelines.

Provides factory functions that return PipelineDefinition objects for the
two main sequencer pipelines:

- **Display pipeline**: audio → profile + lyrics → macro → groups (FAN_OUT) →
  aggregate → holistic → asset_resolution → display_render
- **Moving heads pipeline**: audio → profile + lyrics → macro → moving_heads → render

Both pipelines share common prefix stages (audio, profile, lyrics, macro)
defined in the ``common`` module.

Usage:
    >>> from twinklr.core.pipeline.definitions import build_display_pipeline
    >>> pipeline = build_display_pipeline(display_graph, catalog, display_groups)
    >>> result = await PipelineExecutor().execute(pipeline, audio_path, context)
"""

from twinklr.core.pipeline.definitions.common import build_common_stages
from twinklr.core.pipeline.definitions.display import build_display_pipeline
from twinklr.core.pipeline.definitions.moving_heads import build_moving_heads_pipeline

__all__ = [
    "build_common_stages",
    "build_display_pipeline",
    "build_moving_heads_pipeline",
]
