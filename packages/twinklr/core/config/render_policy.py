"""Refusal of job render policies the installed renderer cannot honor."""

from __future__ import annotations

from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import JobConfig, MHRenderPolicy


class UnsupportedRenderModeError(ValueError):
    """The job selects a moving-head render mode this run cannot honor.

    Raised before any analysis, provider request, template load or output write,
    instead of falling back to the legacy renderer in silence.
    """


def preflight_render_policy(
    job_config: JobConfig, fixture_group: FixtureGroup | None = None
) -> None:
    """Refuse a job whose render policy the renderer cannot honor for this rig.

    `legacy_v1` has no prerequisites. `physical_v2` needs, for every fixture in the
    rig, a `physical_profile` and a usable run-supplied initial state (the transaction
    pass fails every profiled fixture whose initial state is unknown, unsettled or
    contradicts its profile, whenever its first cue is); an initial state must also
    name a fixture of the rig. Profiles the DMX backend cannot address are already
    rejected when the fixture file loads. Without a fixture group nothing about the
    rig is known, so a physical job passes this check until its fixtures are loaded.

    Args:
        job_config: Job to check.
        fixture_group: Fixtures the job renders onto, when already loaded.

    Raises:
        UnsupportedRenderModeError: Naming each failing fixture and missing item.
    """
    policy = job_config.moving_heads
    if policy.mode == "legacy_v1" or fixture_group is None:
        return

    problems: list[str] = []
    fixtures = fixture_group.expand_fixtures()
    for fixture in fixtures:
        profile = fixture.config.physical_profile
        if profile is None:
            problems.append(f"{fixture.fixture_id}: physical_profile is missing")
            continue
        initial = policy.initial_states.get(fixture.fixture_id)
        reasons = list(profile.check_initial_state(initial))
        if initial is not None and not initial.settled:
            reasons.append("initial state is not settled")
        problems.extend(
            f"{fixture.fixture_id}: moving_heads.initial_states[{fixture.fixture_id!r}]: {reason}"
            for reason in reasons
        )
    known = {fixture.fixture_id for fixture in fixtures}
    problems.extend(
        f"moving_heads.initial_states[{fixture_id!r}] names no fixture of the rig"
        for fixture_id in sorted(policy.initial_states.keys() - known)
    )
    if problems:
        raise UnsupportedRenderModeError(
            f"moving_heads.mode {policy.mode!r} cannot render this rig: "
            + "; ".join(problems)
            + ". Add the missing items, or set moving_heads.mode to 'legacy_v1'"
        )


def require_legacy_render(policy: MHRenderPolicy, *, command: str) -> None:
    """Refuse a non-legacy render mode for a command that renders only legacy output.

    Raises:
        UnsupportedRenderModeError: The policy selects a mode other than `legacy_v1`.
    """
    mode = policy.mode
    if mode != "legacy_v1":
        raise UnsupportedRenderModeError(
            f"`twinklr {command}` does not support moving_heads.mode {mode!r}; render the "
            "physical sequence with `twinklr run`, or set the mode to 'legacy_v1'"
        )
