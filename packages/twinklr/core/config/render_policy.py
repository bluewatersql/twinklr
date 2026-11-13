"""Refusal of job render policies the installed renderer cannot honor."""

from __future__ import annotations

from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import JobConfig


class UnsupportedRenderModeError(ValueError):
    """The job selects a moving-head render mode this renderer does not implement.

    Raised before any analysis, provider request, template load or output write,
    instead of falling back to the legacy renderer in silence.
    """


def preflight_render_policy(
    job_config: JobConfig, fixture_group: FixtureGroup | None = None
) -> None:
    """Refuse a job whose render policy the installed renderer cannot honor.

    Args:
        job_config: Job to check.
        fixture_group: Fixtures the job renders onto, when already loaded.

    Raises:
        UnsupportedRenderModeError: The job selects a mode other than `legacy_v1`,
            which is the only one implemented.
    """
    mode = job_config.moving_heads.mode
    if mode != "legacy_v1":
        raise UnsupportedRenderModeError(
            f"moving_heads.mode {mode!r} is not implemented yet; set it to 'legacy_v1' or omit it"
        )
