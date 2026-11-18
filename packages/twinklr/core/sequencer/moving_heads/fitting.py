"""Variation variants fitted to the rig: reduced strengths toward base, derived in code.

The catalog's `wide` (each extent x1.5 of the base's) and `fast` (the movement period
halved) are targets, not all-or-nothing. Where a variation variant of an admitted template
fails the gate (it differs from its base only in extents and period, so it fails on a
physical limit: a travel speed, a range, a repositioning too fast), the gate tries the
reduced strengths below, strongest first, and admits the first that passes and still
differs visibly from base (`MIN_REACH`, `MIN_RATE`; below them it is not offered). The
narrowing and slowing parts of a variant (`narrow`, `slow`, the `narrow+`/`+slow` halves of
a combination) keep their catalog values.

- **Reach** (a wide component): x1.5 (the catalog) → `REACH_LADDER` (x1.4, x1.3, x1.25,
  x1.2) of the base's extent; each extent the catalog widens moves the same share of the
  way from its base to its target.
- **Rate** (a fast component): the catalog's period (the base's halved), then each whole
  beat longer than it, up to `MIN_RATE` of the base's (a 4-beat base: 2, then 3 beats). A
  rate is never fitted to a fraction of a beat other than the catalog's own.
- **A combination** (`wide+fast`, `narrow+fast`, `wide+slow`) fits its fitted parts
  together, reach first: every rate at x1.5, then every rate at x1.4, and so on.

Every value here is a first proposal for the owner's W10 view. A fitted variant is part of
the render identity (`RenderingPipeline.fingerprint`); a rig where the catalog strength
passes renders as before.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from twinklr.core.sequencer.models.template import TemplateDoc, TemplatePreset

CATALOG_REACH = 1.5
"""The catalog's `wide`: each extent x1.5 of the base's."""

REACH_LADDER = (1.4, 1.3, 1.25, 1.2)
"""Reduced reach strengths tried after the catalog's, strongest first."""

MIN_REACH = REACH_LADDER[-1]
"""The least reach a fitted wide variant may have: below x1.2 of the base it is not
offered (it would not read as wider)."""

MIN_RATE = 0.75
"""The longest period a fitted fast variant may have, as a share of the base's: a 4-beat
movement must come back in 3 beats or less (x1.33 the rate) to read as faster."""


@dataclass(frozen=True)
class Fit:
    """A variation variant's fitted strength: its reach factor and its movement period,
    each None where the catalog's value plays."""

    reach: float | None = None
    period_beats: float | None = None

    def record(self) -> dict[str, float]:
        """The trace's and the offer's entry: only what is fitted."""
        out: dict[str, float] = {}
        if self.reach is not None:
            out["reach"] = self.reach
        if self.period_beats is not None:
            out["period_beats"] = self.period_beats
        return out

    def describe(self, preset_id: str) -> str:
        """`wide at x1.4 of the authored reach on this rig` and the like."""
        parts = []
        if self.reach is not None:
            parts.append(f"x{self.reach:g} of the base's reach (catalog x{CATALOG_REACH:g})")
        if self.period_beats is not None:
            parts.append(f"a {self.period_beats:g}-beat movement period")
        return f"{preset_id} fitted to this rig: " + " and ".join(parts)

    @staticmethod
    def from_record(record: dict[str, Any]) -> Fit:
        return Fit(reach=record.get("reach"), period_beats=record.get("period_beats"))


def _components(
    document: TemplateDoc, preset: TemplatePreset
) -> tuple[dict[tuple[str, str], tuple[float, float]], dict[str, tuple[float, float]]]:
    """The preset's widening extents (step, key) → (base, target) and its quickening
    periods step → (base, target); a narrowing or slowing value is neither."""
    steps = {step.step_id: step for step in document.template.steps}
    reach: dict[tuple[str, str], tuple[float, float]] = {}
    rate: dict[str, tuple[float, float]] = {}
    for step_id, patch in preset.step_patches.items():
        step = steps.get(step_id)
        movement = getattr(step, "movement", None)
        if step is None or movement is None or not patch.movement:
            continue
        for key, target in patch.movement.items():
            base = getattr(movement, key, None)
            if not isinstance(target, (int, float)) or not isinstance(base, (int, float)):
                continue
            if key.endswith("_extent_deg") and abs(target) > abs(base) > 0:
                reach[step_id, key] = (float(base), float(target))
            elif key == "period_beats" and 0 < target < base:
                rate[step_id] = (float(base), float(target))
    return reach, rate


def fits_for(document: TemplateDoc, preset: TemplatePreset) -> list[Fit]:
    """The reduced strengths the gate tries for `preset` after its catalog strength fails,
    strongest first (module docstring); empty for a variant with nothing to fit."""
    reach, rate = _components(document, preset)
    if not reach and not rate:
        return []
    reaches: list[float | None] = [None, *REACH_LADDER] if reach else [None]
    periods: list[float | None] = [None]
    if rate:
        base, target = next(iter(rate.values()))
        periods += [
            float(beats)
            for beats in range(math.floor(target) + 1, math.floor(MIN_RATE * base + 1e-9) + 1)
        ]
    return [
        Fit(reach=r, period_beats=p) for r in reaches for p in periods if (r, p) != (None, None)
    ]


def fitted_preset(document: TemplateDoc, preset: TemplatePreset, fit: Fit) -> TemplatePreset:
    """`preset` at strength `fit`: each widening extent `fit.reach` of its base's (the same
    share of the way from base to target), each quickening period `fit.period_beats`;
    everything else as the catalog patches it."""
    reach, rate = _components(document, preset)
    patches = {}
    for step_id, patch in preset.step_patches.items():
        movement = dict(patch.movement or {})
        for (patched, key), (base, target) in reach.items():
            if patched == step_id and fit.reach is not None:
                share = (fit.reach - 1) / (target / base - 1)
                movement[key] = round(base + (target - base) * share, 6)
        if step_id in rate and fit.period_beats is not None:
            movement["period_beats"] = fit.period_beats
        patches[step_id] = patch.model_copy(update={"movement": movement or patch.movement})
    return preset.model_copy(update={"step_patches": patches})
