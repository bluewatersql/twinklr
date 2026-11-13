"""Read-only diagnostics for moving-head controls the legacy renderer ignores.

The legacy renderer keeps the look the owner accepted in xLights
(`memories/decisions/mh-render-matches-pre-cleanup-look.md`), which leaves some
controls a plan, template or rig can request without effect. This module reports each
one that is actually requested. It repairs nothing and changes no output.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    PlanSection,
    flatten_plan_segment,
)
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.fixtures.instances import FixtureInstance
from twinklr.core.config.fixtures.physical import MovementLimits
from twinklr.core.curves.library import CurveLibrary
from twinklr.core.sequencer.models.context import FixtureContext, SectionRenderIntent
from twinklr.core.sequencer.models.enum import ChannelName, Intensity, TemplateRole
from twinklr.core.sequencer.models.moving_heads.rig import rig_profile_from_fixture_group
from twinklr.core.sequencer.models.template import Template, TemplateDoc, TemplateStep
from twinklr.core.sequencer.moving_heads.compile.intent_resolution import apply_template_intent
from twinklr.core.sequencer.moving_heads.compile.preset import apply_preset
from twinklr.core.sequencer.moving_heads.fixture_builder import build_fixture_contexts
from twinklr.core.sequencer.moving_heads.handlers.dimmers.default import DefaultDimmerHandler
from twinklr.core.sequencer.moving_heads.handlers.wheels import PLAN_INTENT_CHANNEL_WINDOW_MAX
from twinklr.core.sequencer.moving_heads.libraries.dimmer import DimmerLibrary
from twinklr.core.sequencer.moving_heads.libraries.movement import MovementLibrary
from twinklr.core.sequencer.moving_heads.templates import get_template
from twinklr.core.sequencer.moving_heads.templates.library import TemplateNotFoundError
from twinklr.core.sequencer.moving_heads.utils import resolve_semantic_group

DiagnosticCode = Literal[
    "legacy_ignored",
    "unsupported_attribute",
    "unsupported_backend_channel",
    "unknown_initial_state",
    "unknown_motion_rate",
    "infeasible_transition",
    "lock_conflict",
    "output_budget_exceeded",
]
"""The shared contract's bounded code vocabulary (architecture §6)."""


class LegacyControl(StrEnum):
    """A control the legacy renderer accepts and does not apply."""

    PAN_TILT_FINE = "pan_tilt_fine"
    MOVEMENT_INTENSITY = "movement_intensity"
    MOVEMENT_LIMITS = "movement_limits"
    TEMPLATE_DIMMER_FLOOR = "template_dimmer_floor"
    SHUTTER_CHANNEL_SCOPE = "shutter_channel_scope"


class MHDiagnostic(BaseModel):
    """One structured moving-head diagnostic.

    `control` names the ignored control for `legacy_ignored` and is None for every
    other code.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: DiagnosticCode
    severity: Literal["info", "warning", "error"]
    message: str
    fixture_id: str | None = None
    section_id: str | None = None
    channel: str | None = None
    control: LegacyControl | None = None
    action: Literal["unchanged", "rejected", "substituted"]

    @model_validator(mode="after")
    def _control_names_legacy_codes_only(self) -> Self:
        if (self.code == "legacy_ignored") != (self.control is not None):
            raise ValueError("control is required for legacy_ignored and forbidden otherwise")
        return self


_MOVEMENT_HOLDS = frozenset({CurveLibrary.HOLD, CurveLibrary.MOVEMENT_HOLD})
_DEFAULT_LIMITS = MovementLimits()


def audit_legacy_controls(
    plan: ChoreographyPlan,
    fixtures: FixtureGroup,
    templates: Sequence[TemplateDoc],
) -> tuple[MHDiagnostic, ...]:
    """Report every requested control the legacy renderer ignores.

    Order: per fixture in group order (16-bit fine channels, then movement limits),
    then per flattened plan section in plan order (movement intensity, template
    dimmer floor, then shutter per targeted fixture). Inputs are read, never modified.
    A section may spell its template any way the template registry resolves.

    Args:
        plan: The choreography plan to render.
        fixtures: The rig.
        templates: Template documents the plan names; their order does not matter.

    Returns:
        The diagnostics, empty when nothing ineffective is requested.

    Raises:
        ValueError: If a section names a template the registry or `templates` lacks.
    """
    docs = {doc.template.template_id: doc for doc in templates}
    instances = fixtures.expand_fixtures()
    contexts = build_fixture_contexts(rig_profile_from_fixture_group(fixtures), fixtures)
    diagnostics: list[MHDiagnostic] = []

    for instance in instances:
        diagnostics.extend(_pan_tilt_fine(instance))
        diagnostics.extend(_movement_limits(instance))

    for section in _flatten(plan):
        template = _resolve_template(section, docs)
        diagnostics.extend(_movement_intensity(section, template))
        diagnostics.extend(_template_dimmer_floor(section, template))
        diagnostics.extend(_shutter_channel_scope(section, template, instances, contexts))

    return tuple(diagnostics)


def _ignored(control: LegacyControl, message: str, **where: str | None) -> MHDiagnostic:
    return MHDiagnostic(
        code="legacy_ignored",
        severity="warning",
        message=message,
        control=control,
        action="unchanged",
        **where,
    )


def _flatten(plan: ChoreographyPlan) -> Iterator[PlanSection]:
    """Sections as the renderer iterates them (`RenderingPipeline.iterate_plan_sections`)."""
    for section in plan.sections:
        if section.segments:
            for segment in section.segments:
                yield flatten_plan_segment(section, segment)
        else:
            yield section


def _resolve_template(section: PlanSection, docs: dict[str, TemplateDoc]) -> Template:
    """The template a section compiles: its preset, then the section's intensity.

    Looks the template up and resolves its preset as `RenderingPipeline.render`
    does, then applies both as `compile_template` does.
    """
    # Deferred: the pipeline imports this module.
    from twinklr.core.sequencer.moving_heads.pipeline import resolve_section_preset

    try:
        template_id = get_template(section.template_id or "").template.template_id
    except TemplateNotFoundError as error:
        raise ValueError(f"Template not found: {section.template_id}") from error
    doc = docs.get(template_id)
    if doc is None:
        raise ValueError(f"Template not found: {section.template_id}")

    template = doc.template
    preset = resolve_section_preset(section, doc)
    if preset is not None:
        template = apply_preset(template, preset)
    if not section.legacy_intent_omitted:
        template = apply_template_intent(template, SectionRenderIntent(intensity=section.intensity))
    return template


def _pan_tilt_fine(instance: FixtureInstance) -> list[MHDiagnostic]:
    """`DmxSettingsBuilder` flags a fine channel's inversion but writes no value to it."""
    mapping = instance.config.dmx_mapping
    if not mapping.use_16bit_pan_tilt:
        return []
    return [
        _ignored(
            LegacyControl.PAN_TILT_FINE,
            f"Fixture {instance.fixture_id} requests 16-bit {axis} with fine channel "
            f"{channel}; legacy output writes only the 8-bit coarse {axis} value and "
            f"no value to channel {channel}.",
            fixture_id=instance.fixture_id,
            channel=f"{axis}_fine",
        )
        for axis, channel in (("pan", mapping.pan_fine), ("tilt", mapping.tilt_fine))
        if channel is not None
    ]


def _movement_limits(instance: FixtureInstance) -> list[MHDiagnostic]:
    """The movement handler bounds pan/tilt to 0-255, never to the fixture's window.

    Most geometry handlers ignore the window too, so even hold-only movement can
    leave it: the window bounds no section.
    """
    limits = instance.config.limits
    window = (limits.pan_min, limits.pan_max, limits.tilt_min, limits.tilt_max)
    default = (
        _DEFAULT_LIMITS.pan_min,
        _DEFAULT_LIMITS.pan_max,
        _DEFAULT_LIMITS.tilt_min,
        _DEFAULT_LIMITS.tilt_max,
    )
    if window == default:
        return []
    return [
        _ignored(
            LegacyControl.MOVEMENT_LIMITS,
            f"Fixture {instance.fixture_id} declares pan {limits.pan_min}-{limits.pan_max} "
            f"and tilt {limits.tilt_min}-{limits.tilt_max}; legacy movement is not "
            "bounded by that window.",
            fixture_id=instance.fixture_id,
        )
    ]


def _movement_intensity(section: PlanSection, template: Template) -> list[MHDiagnostic]:
    """The movement handler renders `params["intensity"]`, defaulting to SMOOTH.

    A step that holds both axes renders the same curve at every intensity, so
    ignoring its request changes nothing and it is not reported.
    """
    ignored = [
        (step.step_id, step.movement.intensity, effective)
        for step in template.steps
        if not _holds_position(step)
        and step.movement.intensity
        != (effective := Intensity(step.movement.params.get("intensity", Intensity.SMOOTH)))
    ]
    if not ignored:
        return []
    detail = ", ".join(
        f"{step_id} requests {requested.value}, renders {effective.value}"
        for step_id, requested, effective in ignored
    )
    return [
        _ignored(
            LegacyControl.MOVEMENT_INTENSITY,
            f"Section {section.section_name} ({template.template_id}): {detail}.",
            section_id=section.section_name,
        )
    ]


def _holds_position(step: TemplateStep) -> bool:
    pattern = MovementLibrary.get_pattern(step.movement.movement_type)
    tilt = pattern.resolve_tilt_curve(step.geometry.geometry_type)
    return pattern.pan_curve in _MOVEMENT_HOLDS and tilt in _MOVEMENT_HOLDS


def _template_dimmer_floor(section: PlanSection, template: Template) -> list[MHDiagnostic]:
    """The dimmer handler takes its floor from the rig calibration, not the template.

    Reported when the declared floor is above the lower bound of the range the
    template's own dimmer steps may span. Whether a render reaches that bound depends
    on the curve and its length, so the message claims only the range.
    """
    floor = template.defaults.get("dimmer_floor_dmx")
    if floor is None:
        return []
    lows = [low for step in template.steps if (low := _dimmer_range_low_dmx(step)) is not None]
    if not lows or min(lows) >= floor:
        return []
    return [
        _ignored(
            LegacyControl.TEMPLATE_DIMMER_FLOOR,
            f"Section {section.section_name} ({template.template_id}) declares a dimmer "
            f"floor of {floor} DMX, which is not applied; its dimmer range extends down "
            f"to {min(lows):.0f} DMX.",
            section_id=section.section_name,
            channel=ChannelName.DIMMER.value,
        )
    ]


def _dimmer_range_low_dmx(step: TemplateStep) -> float | None:
    """Lower bound of a step's dimmer range, by `DefaultDimmerHandler`'s arithmetic.

    None for a pattern the floor would exempt (blackout) or the library lacks.
    """
    pattern = DimmerLibrary.PATTERNS.get(step.dimmer.dimmer_type)
    if pattern is None or pattern.bypasses_dimmer_floor:
        return None
    params = DefaultDimmerHandler()._resolve_categorical_params(pattern, step.dimmer.intensity)
    if pattern.curve == CurveLibrary.HOLD:
        return float(params.max_intensity)
    # The handler maps a curve's base value 0 to this level.
    dimmer = step.dimmer
    return 255.0 * dimmer.min_norm + params.min_intensity * (dimmer.max_norm - dimmer.min_norm)


def _shutter_channel_scope(
    section: PlanSection,
    template: Template,
    instances: Sequence[FixtureInstance],
    contexts: Sequence[FixtureContext],
) -> list[MHDiagnostic]:
    """The shutter handler drops intent above channel 16; the exporter emits the default.

    Section events reach every fixture a step of the template renders; a step's own
    shutter reaches the fixtures that step targets.
    """
    section_events = not section.legacy_intent_omitted and bool(section.shutter_events)
    steps = [step for step in template.steps if section_events or step.shutter is not None]
    targeted = {fixture_id for step in steps for fixture_id in _target_fixture_ids(step, contexts)}
    diagnostics = []
    for instance in instances:
        mapping = instance.config.dmx_mapping
        channel = mapping.shutter
        if (
            instance.fixture_id not in targeted
            or channel is None
            or channel <= PLAN_INTENT_CHANNEL_WINDOW_MAX
        ):
            continue
        diagnostics.append(
            _ignored(
                LegacyControl.SHUTTER_CHANNEL_SCOPE,
                f"Section {section.section_name}: shutter intent for fixture "
                f"{instance.fixture_id} is dropped because its shutter is on channel "
                f"{channel}, above {PLAN_INTENT_CHANNEL_WINDOW_MAX}; channel {channel} "
                f"still emits the declared default {mapping.shutter_default}.",
                fixture_id=instance.fixture_id,
                section_id=section.section_name,
                channel=ChannelName.SHUTTER.value,
            )
        )
    return diagnostics


def _target_fixture_ids(step: TemplateStep, contexts: Sequence[FixtureContext]) -> set[str]:
    """Fixtures a step compiles for, resolved as `template_compiler` resolves them.

    Empty where the compiler rejects the rig shape, since nothing renders there.
    """
    rig_roles: list[TemplateRole] = []
    for context in contexts:
        try:
            role = TemplateRole(context.role)
        except ValueError:
            continue
        if role not in rig_roles:
            rig_roles.append(role)
    try:
        target_roles = resolve_semantic_group(step.target, rig_roles)
    except ValueError:
        return set()
    return {context.fixture_id for context in contexts if context.role in target_roles}
