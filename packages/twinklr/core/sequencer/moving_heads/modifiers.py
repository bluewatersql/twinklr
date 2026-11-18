"""The planner's per-part modifiers, rendered (song-intent W10e).

A part's `modifiers` stays a free key/value list in the planner contract (integrator
decision 6); the renderer knows a closed set (`MODIFIERS`), each a deterministic change of
the variant the part plays (its preset applied, fitted or not), computed here rather than
authored as catalog presets. None is carried by another field: reach and rate are the
`variation` variants, and colour, gobo, intensity, events and transitions have their own.

- `spread`: how the template's wave runs across the heads, through the phase distribution
  that owns pan and tilt (the zoom and a visibility envelope follow it). `unison`: every
  head moves together (spread 0, a two-winged template keeping its mirror); `wide_wave`:
  the wave twice as wide; `reversed`: the wave runs from the other end of the rig. On a
  template whose heads move together: `wave`, a quarter-cycle wave from the rig's first
  head (it needs the rig's topology).
- `direction: reverse`: the path runs backwards in time. A circle or a figure-eight turns
  the other way (`PathTransform.reverse`), a sway starts to the other side (its extent,
  and a waving zoom's, negated: `-sin(x) = sin(-x)`), a finite move runs from its end
  back to its start. A periodic sweep runs the same both ways (`Movement` refuses its
  reverse), so it has none.
- `aim: low | high`: every step's start tilt `AIM_OFFSET_DEG` lower or higher.

Each is a phase shift, a time reversal or a translation in tilt of the variant's own
path, so no head moves faster. What can newly fail: a tilt range (`aim`), a rig without
a topology (`wave`), a dark gap set in time (an overlay's mask, a gap between steps) that
a head now meets at another pose and cannot reposition through (`spread`, `direction`),
and a section's entry, which can drop more of a head's first cue.

**Offer** (`pipeline._admit_modifiers`). Per admitted template, the gate proves each
recognised value it can apply (`candidates`) on the template's effective variant: compiled
at bar 1 over the song, and its first bar and two cycles must not play like the
unmodified variant's (`pipeline._cues_alike`, the twin-variant rule). Those that pass are
offered (`TemplateOffer.modifiers`) and the others recorded with why
(`modifier_refusals`). On every admitted variant a value that does not fit it is
excluded there (`modifier_exclusions`): an `aim` that would take a head's compiled tilt
range out of its operable range (`aim_fits`); a `spread` or `direction` whose dark
repositioning between a head's own cues cannot be planned. A spread that moves a
template's darkness (a visibility envelope following the wave) publishes each variant's
dark phases with it (`modifier_phases`), for repair's event predictions. A section's entry
depends on the section before, so the render decides it (below).

**Play** (`resolve_modifiers`, one function for the render and the plan repair). A part
plays every modifier offered for its template that fits the variant it plays, in the
fixed order of `MODIFIERS` whatever order the plan lists them in; each other entry is not
applied, with why and the template's valid set: a key the renderer does not know, a value
its key does not take, a second entry for a key one entry already plays, a value not
offered for the template here, a value that does not fit the variant played, or one the render
withdrew because it gave way to the song (`withdrawn`). **The song outranks the
arrangement:** a part's modifiers are one arrangement unit
(`pipeline._modifier_units`): the render plays them only where no event of the song is
worse than without them (`pipeline.worse`) and no head loses more of a cue in the part
or the next one (`pipeline._darkened_by_modifiers`), first all of them, then, where a spread plays
with others, all but the spread (a spread is the one modifier that moves a template's
darkness), else none, traced with the event they gave way to. Without a gate result for
a template, every value `candidates` applies plays, as a template the gate did not judge
plays every preset it declares. Every value here is a first proposal for the owner's W10
view.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.topology import PhaseDistribution
from twinklr.core.sequencer.models.template import (
    RELATIVE_PATH_SHAPES,
    PathTransform,
    Template,
    TemplatePreset,
    TemplateStep,
)
from twinklr.core.sequencer.moving_heads.compile.preset import apply_preset

if TYPE_CHECKING:
    from twinklr.core.sequencer.moving_heads.song_intent import TemplateOffer

MODIFIERS: dict[str, tuple[str, ...]] = {
    "spread": ("unison", "wave", "wide_wave", "reversed"),
    "direction": ("reverse",),
    "aim": ("low", "high"),
}
"""The modifier keys the renderer knows, in the order a part applies them, and each key's
values."""

AIM_OFFSET_DEG = 10.0
"""Proposed: how far `aim` moves every step's start tilt (well over `TWIN_POSE_DEG`)."""

WAVE_SPREAD_CYCLES = 0.25
"""Proposed: the spread `wave` gives a template whose heads move together, a quarter
cycle, as the catalog's own waves."""

AIM_MARGIN_DEG = 1e-6
"""`aim_fits` keeps this far inside an operable range, so a pose the compile would put on
its edge by rounding is never offered."""

Modifier = tuple[str, str]
"""A recognised `(key, value)`."""


class AskedModifier(Protocol):
    """A plan's modifier entry (`PlanModifier`)."""

    @property
    def key(self) -> str: ...

    @property
    def value(self) -> str: ...


def spelled(modifier: Modifier) -> str:
    """`key=value`, as the offer, the trace and repair name a modifier."""
    return f"{modifier[0]}={modifier[1]}"


def _normalised(text: str) -> str:
    return "_".join(text.strip().lower().replace("-", " ").split())


def _wave(step: TemplateStep) -> PhaseDistribution | None:
    """The distribution that owns the step's pan, if any."""
    return next((spec for spec in step.distribution if ChannelName.PAN in spec.domains), None)


def _spread_step(step: TemplateStep, value: str) -> TemplateStep | None:
    """The step with `spread` `value`, or None where it does not apply."""
    spec = _wave(step)
    spread = 0.0 if spec is None else spec.spread_cycles
    if value == "wave":
        if spread:
            return None
        if spec is not None:
            changed = spec.model_copy(update={"spread_cycles": WAVE_SPREAD_CYCLES})
        elif any({ChannelName.PAN, ChannelName.TILT} & set(s.domains) for s in step.distribution):
            return None  # tilt is owned apart from pan: a wave could not keep them together
        else:
            return step.model_copy(
                update={
                    "distribution": (
                        *step.distribution,
                        PhaseDistribution(
                            domains=(ChannelName.PAN, ChannelName.TILT),
                            spread_cycles=WAVE_SPREAD_CYCLES,
                        ),
                    )
                }
            )
    elif not spread or spec is None:
        return None
    elif value == "unison":
        changed = spec.model_copy(update={"spread_cycles": 0.0})
    elif value == "wide_wave":
        changed = spec.model_copy(update={"spread_cycles": spread * 2})
    else:  # reversed
        flipped = "forward" if spec.direction == "reverse" else "reverse"
        changed = spec.model_copy(update={"direction": flipped})
    return step.model_copy(
        update={"distribution": tuple(changed if s is spec else s for s in step.distribution)}
    )


def _reverse_step(step: TemplateStep) -> TemplateStep | None:
    """The step with its path run backwards in time, or None where it has none to run."""
    movement = step.movement
    if movement.shape == "hold" or not (movement.pan_extent_deg or movement.tilt_extent_deg):
        return None
    if movement.shape in RELATIVE_PATH_SHAPES:
        if movement.shape == "sweep" and movement.mode == "periodic":
            return None  # the same both ways: `Movement` refuses it
        transform = movement.transform or PathTransform()
        reversed_ = movement.model_copy(
            update={"transform": transform.model_copy(update={"reverse": not transform.reverse})}
        )
        return step.model_copy(update={"movement": reversed_})
    negated = {
        "pan_extent_deg": -movement.pan_extent_deg,
        "tilt_extent_deg": -movement.tilt_extent_deg,
    }
    zoom = step.zoom
    if movement.shape == "linear":
        # From its end back to its start: the start moves to the end.
        if movement.start_pan_deg is None or movement.start_tilt_deg is None or _referenced(step):
            return None
        negated["start_pan_deg"] = movement.start_pan_deg + movement.pan_extent_deg
        negated["start_tilt_deg"] = movement.start_tilt_deg + movement.tilt_extent_deg
    elif zoom is not None and zoom.shape == "sine":
        zoom = zoom.model_copy(update={"extent_deg": -zoom.extent_deg})
    return step.model_copy(update={"movement": movement.model_copy(update=negated), "zoom": zoom})


def _referenced(step: TemplateStep) -> bool:
    """Whether a rig position preset, not the step, sets its start aim."""
    return step.component_refs is not None and step.component_refs.position_id is not None


def _aim_step(step: TemplateStep, value: str) -> TemplateStep | None:
    movement = step.movement
    if movement.start_tilt_deg is None or _referenced(step):
        return None
    offset = AIM_OFFSET_DEG if value == "high" else -AIM_OFFSET_DEG
    return step.model_copy(
        update={
            "movement": movement.model_copy(
                update={"start_tilt_deg": movement.start_tilt_deg + offset}
            )
        }
    )


_WHY_NOT = {
    "unison": "its heads already move together (no wave to unify)",
    "wave": "its heads already move in a wave",
    "wide_wave": "its heads move together (no wave to widen)",
    "reversed": "its heads move together (no wave to reverse)",
    "reverse": "it has no path that runs differently backwards (a periodic sweep runs the "
    "same both ways)",
    "low": "no step sets its own start tilt",
    "high": "no step sets its own start tilt",
}


def _changed(template: Template, modifier: Modifier) -> Template | None:
    key, value = modifier
    steps = []
    changed = False
    for step in template.steps:
        if key == "spread":
            new = _spread_step(step, value)
        elif key == "direction":
            new = _reverse_step(step)
        else:
            new = _aim_step(step, value)
        changed |= new is not None
        steps.append(step if new is None else new)
    if not changed:
        return None
    try:  # the step models' own checks, as a template file's
        return Template.model_validate(
            template.model_copy(update={"steps": steps}).model_dump(mode="python")
        )
    except ValueError:
        return None


def candidates(template: Template) -> dict[str, str | None]:
    """Per recognised `key=value`, None where it changes `template` (a variant's: its
    preset applied), else why it does not apply to it."""
    return {
        spelled((key, value)): (
            None
            if _changed(template, (key, value)) is not None
            else f"{template.template_id} cannot: {_WHY_NOT[value]}"
        )
        for key, values in MODIFIERS.items()
        for value in values
    }


def modify(template: Template, modifiers: Sequence[Modifier]) -> Template:
    """`template` (a variant's: its preset applied) with each modifier applied, in the
    order of `MODIFIERS`.

    Raises:
        ValueError: For a modifier that does not apply to it (`candidates`).
    """
    order = [(key, value) for key, values in MODIFIERS.items() for value in values]
    for modifier in sorted(modifiers, key=order.index):
        changed = _changed(template, modifier)
        if changed is None:
            raise ValueError(f"{spelled(modifier)} does not apply to {template.template_id}")
        template = changed
    return template


def played_template(
    template: Template, preset: TemplatePreset | None, modifiers: Sequence[Modifier]
) -> tuple[Template, TemplatePreset | None]:
    """What `compile_template` compiles for a part playing `preset` with `modifiers`: the
    template and preset as they are without modifiers, else the template with the preset
    applied and the modifiers on top, and no preset."""
    if not modifiers:
        return template, preset
    return modify(apply_preset(template, preset) if preset else template, modifiers), None


def aim_fits(
    value: str,
    tilt: Mapping[str, tuple[float, float]],
    operable: Mapping[str, tuple[float, float]],
) -> str | None:
    """None where moving each head's tilt range (`tilt`, as a variant compiles it) by the
    `aim` offset keeps it in the head's operable tilt range (`operable`); else why not,
    naming the first head that leaves it."""
    offset = AIM_OFFSET_DEG if value == "high" else -AIM_OFFSET_DEG
    for fixture_id, (low, high) in sorted(tilt.items()):
        least, most = operable[fixture_id]
        moved = (low + offset, high + offset)
        if moved[0] - AIM_MARGIN_DEG < least or moved[1] + AIM_MARGIN_DEG > most:
            return (
                f"aim {value} would take {fixture_id}'s tilt to {moved[0]:g}..{moved[1]:g} "
                f"degrees, outside its operable range {least:g}..{most:g}"
            )
    return None


def offered_set(offered: TemplateOffer | None, template: Template) -> list[str]:
    """The `key=value`s a template plays here: its offer's, else every one `candidates`
    applies (no gate judged it)."""
    if offered is None:
        return [name for name, why in candidates(template).items() if why is None]
    return [spelled((key, value)) for key, values in offered.modifiers.items() for value in values]


@dataclass(frozen=True)
class ModifierPlay:
    """What a part's modifiers play (`resolve_modifiers`)."""

    asked: tuple[str, ...]
    """Each entry as the plan wrote it, `key=value`."""
    applied: tuple[Modifier, ...]
    """What plays, in the order applied."""
    not_applied: tuple[tuple[str, str], ...]
    """Each entry that does not play (as written) and why, with what the template takes
    here."""

    def record(self) -> dict[str, Any]:
        """The trace's `arrangement.modifiers` entry."""
        record: dict[str, Any] = {
            "asked": list(self.asked),
            "applied": [spelled(modifier) for modifier in self.applied],
        }
        if self.not_applied:
            record["not_applied"] = [
                {"modifier": name, "reason": why} for name, why in self.not_applied
            ]
        return record


def resolve_modifiers(
    asked: Sequence[AskedModifier],
    template: Template,
    offered: TemplateOffer | None,
    variant: str,
    *,
    withdrawn: Mapping[str, str] | None = None,
) -> ModifierPlay:
    """What a part's `asked` modifiers play on `template` (canonical, its base) playing
    `variant` (`base` for no preset), over the gate's `offered` template (None where no
    gate judged it); `withdrawn`, per key, why the render does not play it here (it gave
    way to the song: `pipeline.RenderingPipeline._part_modifiers`) (module docstring)."""
    valid = offered_set(offered, template)
    excluded = {} if offered is None else offered.modifier_exclusions.get(variant, {})
    refused = {} if offered is None else offered.modifier_refusals
    seen: dict[str, str] = {}
    applied: list[Modifier] = []
    not_applied: list[tuple[str, str]] = []
    for entry in asked:
        name = f"{entry.key}={entry.value}"
        key, value = _normalised(entry.key), _normalised(entry.value)
        here = f"{template.template_id} takes {', '.join(valid) or 'none'} here"
        if key not in MODIFIERS:
            why = f"the renderer knows no modifier {entry.key!r} (it knows {', '.join(MODIFIERS)})"
        elif value not in MODIFIERS[key]:
            why = f"{key} takes {' or '.join(MODIFIERS[key])}, not {entry.value!r}"
        elif key in seen:
            why = f"the part already plays {key} ({seen[key]}); only one entry for a key plays"
        elif spelled((key, value)) not in valid:
            reason = refused.get(spelled((key, value)))
            why = f"not offered for {template.template_id} here" + (f": {reason}" if reason else "")
        elif spelled((key, value)) in excluded:
            why = f"it does not fit {variant}: {excluded[spelled((key, value))]}"
        elif key in (withdrawn or {}):
            seen[key] = value
            why = (withdrawn or {})[key]
        else:
            seen[key] = value
            applied.append((key, value))
            continue
        not_applied.append((name, f"{why}; {here}"))
    order = [(key, value) for key, values in MODIFIERS.items() for value in values]
    return ModifierPlay(
        asked=tuple(f"{entry.key}={entry.value}" for entry in asked),
        applied=tuple(sorted(applied, key=order.index)),
        not_applied=tuple(not_applied),
    )
