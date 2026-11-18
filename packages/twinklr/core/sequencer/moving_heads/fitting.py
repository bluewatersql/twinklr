"""Variation variants fitted to the rig: a reduced reach, derived in code.

The catalog's `wide` (each extent x1.5 of the base's) and `fast` (the movement period
halved) are targets, not all-or-nothing. Where a variation variant of an admitted template
fails the gate on a physical limit (a travel speed above the head's, or a value outside its
allowed range; `fittable`), the gate tries reduced strengths, strongest first, and admits
the first that passes. A fit never changes the period: the musical relation of the cycle
to the bar (where every head reveals) stays the catalog variant's, so only the REACH is
reduced (the speed goes as reach / period):

- **A wider reach at the catalog period** (`wide`, `wide+slow`, `wide+fast`): x1.4, x1.3,
  x1.25, x1.2 of the base's extent (`REACH_LADDER`; below x1.2 it would not read as wider
  and is not offered), each extent the catalog widens moving the same share of the way
  from its base to its target.
- **The halved period at the base's reach** (`fast`): the reach steps from the base's
  toward the family's own `narrow` extents (`NARROWING_SHARES`: a quarter, a half, three
  quarters of the way, each extent by the same share). At `narrow`'s extents it would be
  `narrow+fast` itself, so `fast` is then not offered; a FASTER step from the base
  resolves to `narrow+fast` (`arrangement`: "faster here needs a narrower reach").
- **Never fitted**: `narrow+fast` (nothing narrower to go to), `narrow`, `slow` and
  `narrow+slow`, any variant with a fast part on a ONCE family (`finite_snap_hold`: its
  one move is inside the entry window, so its rate does not show and a fitted `wide+fast`
  would only be a weaker `wide`), and zoom (no variant patches zoom).

A variant whose catalog strength fails otherwise (a mask too short to turn a wheel at the
halved cycle, a dark repositioning that cannot be planned), or whose reduced strength
fails so, is not fitted: it fails with that reason. Every value here is a first proposal
for the owner's W10 view. A fitted variant is part of the render identity
(`RenderingPipeline.fingerprint`); a rig where the catalog strength passes renders as
before.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from twinklr.core.sequencer.models.template import TemplateDoc, TemplatePreset

CATALOG_REACH = 1.5
"""The catalog's `wide`: each extent x1.5 of the base's."""

REACH_LADDER = (1.4, 1.3, 1.25, 1.2)
"""Reduced wider reaches tried after the catalog's, strongest first."""

MIN_REACH = REACH_LADDER[-1]
"""The least reach a fitted wide variant may have."""

NARROWING_SHARES = (0.25, 0.5, 0.75)
"""How far from the base's extents toward `narrow`'s a fitted `fast` goes, strongest
(widest) first."""

PHYSICAL_LIMITS = ("above the configured speed", "is outside the operable range")
"""What a gate failure says when it is a physical limit a reduced reach can meet."""


def fittable(reasons: list[str]) -> bool:
    """Whether every reason a rung failed for is a physical limit (`PHYSICAL_LIMITS`)."""
    return bool(reasons) and all(any(limit in r for limit in PHYSICAL_LIMITS) for r in reasons)


@dataclass(frozen=True)
class Fit:
    """A variation variant's fitted reach: `share` of the way from the base's extents
    toward `toward`'s (the catalog `wide` target, or `narrow`'s extents), `reach` that as a
    factor of the base's first such extent, and `because` what the catalog strength broke."""

    toward: Literal["wide", "narrow"]
    share: float
    reach: float
    because: str = field(default="", compare=False)

    def record(self) -> dict[str, Any]:
        """The offer's and the trace's entry."""
        return {
            "reach": self.reach,
            "toward": self.toward,
            "share": self.share,
            "because": self.because,
        }

    def describe(self, preset_id: str) -> str:
        """`wide fitted to this rig: x1.4 of the base's reach (...)`, `fast fitted to this
        rig: half the period at x0.8 of the base's reach (...)`."""
        what = (
            f"x{self.reach:g} of the base's reach (catalog x{CATALOG_REACH:g})"
            if self.toward == "wide"
            else f"half the period at x{self.reach:g} of the base's reach"
        )
        why = f"; at the catalog's strength {self.because}" if self.because else ""
        return f"{preset_id} fitted to this rig: {what}{why}"

    @staticmethod
    def from_record(record: dict[str, Any]) -> Fit:
        return Fit(
            toward=record["toward"],
            share=record["share"],
            reach=record["reach"],
            because=record.get("because", ""),
        )


def _extents(
    document: TemplateDoc, patching: TemplatePreset, *, wider: bool
) -> dict[tuple[str, str], tuple[float, float]]:
    """`patching`'s extents (step, key) → (base, target) that widen (`wider`) or narrow
    the base's."""
    steps = {step.step_id: step for step in document.template.steps}
    out: dict[tuple[str, str], tuple[float, float]] = {}
    for step_id, patch in patching.step_patches.items():
        movement = getattr(steps.get(step_id), "movement", None)
        if movement is None or not patch.movement:
            continue
        for key, target in patch.movement.items():
            base = getattr(movement, key, None)
            if not key.endswith("_extent_deg"):
                continue
            if not isinstance(target, (int, float)) or not isinstance(base, (int, float)):
                continue
            if base and (abs(target) > abs(base) if wider else abs(target) < abs(base)):
                out[step_id, key] = (float(base), float(target))
    return out


def _quickens(document: TemplateDoc, preset: TemplatePreset) -> bool:
    steps = {step.step_id: step for step in document.template.steps}
    for step_id, patch in preset.step_patches.items():
        movement = getattr(steps.get(step_id), "movement", None)
        base = getattr(movement, "period_beats", None)
        target = (patch.movement or {}).get("period_beats")
        if isinstance(base, (int, float)) and isinstance(target, (int, float)) and target < base:
            return True
    return False


def _narrow(document: TemplateDoc) -> TemplatePreset | None:
    return next((p for p in document.presets if p.preset_id == "narrow"), None)


def fits_for(document: TemplateDoc, preset: TemplatePreset, because: str = "") -> list[Fit]:
    """The reduced reaches the gate tries for `preset` after its catalog strength failed on
    a physical limit (`because`), strongest first (module docstring); empty for a variant
    that is never fitted."""
    from twinklr.core.sequencer.models.template import RepeatMode

    if document.template.repeat.mode == RepeatMode.ONCE and _quickens(document, preset):
        return []  # a ONCE family's rate does not show: fitting its fast part fits nothing
    wider = _extents(document, preset, wider=True)
    if wider:
        (base, target) = next(iter(wider.values()))
        return [
            Fit(
                toward="wide",
                share=round((r - 1) / (target / base - 1), 6),
                reach=r,
                because=because,
            )
            for r in REACH_LADDER
        ]
    if _extents(document, preset, wider=False) or not _quickens(document, preset):
        return []  # narrow+fast, or a variant with nothing to fit
    narrow = _narrow(document)
    toward = {} if narrow is None else _extents(document, narrow, wider=False)
    if not toward:
        return []
    (base, target) = next(iter(toward.values()))
    return [
        Fit(
            toward="narrow",
            share=share,
            reach=round((base + (target - base) * share) / base, 3),
            because=because,
        )
        for share in NARROWING_SHARES
    ]


def fitted_preset(document: TemplateDoc, preset: TemplatePreset, fit: Fit) -> TemplatePreset:
    """`preset` at `fit`: each extent `fit.share` of the way from the base's toward the
    catalog's wider target (`toward="wide"`) or toward `narrow`'s (`toward="narrow"`); the
    period and everything else as the catalog patches it."""
    if fit.toward == "wide":
        targets = _extents(document, preset, wider=True)
    else:
        narrow = _narrow(document)
        targets = {} if narrow is None else _extents(document, narrow, wider=False)
    patches = dict(preset.step_patches)
    for (step_id, key), (base, target) in targets.items():
        patch = patches.get(step_id)
        movement = dict(patch.movement or {}) if patch is not None else {}
        movement[key] = round(base + (target - base) * fit.share, 6)
        if patch is None:
            from twinklr.core.sequencer.models.template import StepPatch

            patches[step_id] = StepPatch(movement=movement)
        else:
            patches[step_id] = patch.model_copy(update={"movement": movement})
    return preset.model_copy(update={"step_patches": patches})
