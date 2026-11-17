"""Refusal of jobs whose rig the moving-head renderer cannot honor."""

from __future__ import annotations

import json

from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.fixtures.capabilities import PROFILE_GUIDE
from twinklr.core.config.models import JobConfig


class UnsupportedRenderModeError(ValueError):
    """The moving-head renderer cannot honor this job's rig or policy.

    Raised before any analysis, provider request, template load or output write.
    """


def preflight_render_policy(
    job_config: JobConfig, fixture_group: FixtureGroup | None = None
) -> None:
    """Refuse a job whose render policy the renderer cannot honor for this rig.

    The renderer needs, for every fixture in the rig, a `physical_profile` and a usable run-supplied initial state (the transaction
    pass fails every profiled fixture whose initial state is unknown, unsettled or
    contradicts its profile, whenever its first cue is); an initial state must also
    name a fixture of the rig, and every fixture needs its own, non-blank xLights model
    name, because frames are written per fixture. Profiles the DMX backend cannot address are already
    rejected when the fixture file loads. Without a fixture group nothing about the
    rig is known, so a job passes this check until its fixtures are loaded.

    Args:
        job_config: Job to check.
        fixture_group: Fixtures the job renders onto, when already loaded.

    Raises:
        UnsupportedRenderModeError: Naming each failing fixture and what to add: where
            a profile goes, and for fixtures without an initial state the entries their
            profiles' default bytes give, as one object to paste after checking it.
    """
    policy = job_config.moving_heads
    if fixture_group is None:
        return

    problems: list[str] = []
    missing_profile = False
    suggested: dict[str, object] = {}
    fixtures = fixture_group.expand_fixtures()
    for fixture in fixtures:
        profile = fixture.config.physical_profile
        if profile is None:
            missing_profile = True
            problems.append(
                f"{fixture.fixture_id}: physical_profile is missing; add one to its config, "
                "or once as base_config.physical_profile for identical heads"
            )
            continue
        initial = policy.initial_states.get(fixture.fixture_id)
        if initial is None:
            suggested[fixture.fixture_id] = profile.default_initial_state().model_dump(mode="json")
        reasons = list(profile.check_initial_state(initial))
        if initial is not None and not initial.settled:
            reasons.append("initial state is not settled")
        problems.extend(
            f"{fixture.fixture_id}: moving_heads.initial_states[{fixture.fixture_id!r}]: {reason}"
            for reason in reasons
        )
    # Frames go to each fixture's own model, never a shared one.
    by_model: dict[str, list[str]] = {}
    for fixture in fixtures:
        if not fixture.xlights_model_name.strip():
            problems.append(f"{fixture.fixture_id}: xlights_model_name is blank")
        else:
            by_model.setdefault(fixture.xlights_model_name, []).append(fixture.fixture_id)
    for model, fixture_ids in by_model.items():
        if len(fixture_ids) > 1:
            names = f"{', '.join(fixture_ids[:-1])} and {fixture_ids[-1]}"
            problems.append(f"{names}: both map to xLights model {model!r}")
    known = {fixture.fixture_id for fixture in fixtures}
    problems.extend(
        f"moving_heads.initial_states[{fixture_id!r}] names no fixture of the rig"
        for fixture_id in sorted(policy.initial_states.keys() - known)
    )
    if problems:
        guidance = []
        if suggested:
            guidance.append(
                f"To start {', '.join(suggested)} at their profiles' default bytes, add to "
                f"moving_heads.initial_states: {json.dumps(suggested)}; pasting it asserts "
                "that each head really rests there, settled and dark as stated, when the "
                "sequence starts"
            )
        if missing_profile or suggested:
            guidance.append(f"A minimal profile and initial states: {PROFILE_GUIDE}")
        raise UnsupportedRenderModeError(
            "the moving-head renderer cannot render this rig: "
            + "; ".join(problems)
            + "".join(f". {line}" for line in guidance)
            + ". Add the missing items"
        )
