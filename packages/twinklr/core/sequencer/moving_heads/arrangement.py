"""The planner's motif and variation, resolved to the variant each part plays (song-intent W10b, W10c).

A family's variants sit on a grid: reach `narrow | base | wide` by rate `slow | base | fast`
(the catalog's presets `narrow`, `slow`, `wide`, `fast` and the four `reach+rate`
combinations; `base` is no preset). Every value below is a first proposal for the owner's
W10 view (plan: `changes/2026_11_12_mh_true_up/plan/w10-arrangement.md`).

**Motif relation** (`motif_relations`). Equal `motif_id`s are the same idea, with or
without a macro plan. The first section carrying a motif, in plan order, introduces it;
every later one relates to that introducing section (its *source*): with a macro motif
thread that lists the section, by the thread's `evolution` (a repeated INTRODUCE
restates); otherwise it varies where the planner set a `variation`, else restates. The
relation and source are code-owned (`PlanSection.motif_relation`, `motif_source_id`):
plan time (`with_motif_relations`) derives and writes both, overwriting whatever arrived,
and the render derives them again; the one value the render keeps from the plan is a
later carrier's RESOLVE, which only a macro thread can give and which plan time wrote.

**Variation** (`resolve_arrangement`). One step on one axis of the grid (NARROW, WIDEN on
reach; SLOWER, FASTER on rate) from a source variant:

- a later motif carrier: the introducing section's part at the same index (its last part
  where it has fewer), as that part plays;
- an introducing section: its own preset where the planner named an admitted one, else
  the family's effective variant;
- a section without a motif, with a step to take: the previous section in plan order with
  a part on the same family, as it plays; otherwise its own preset, else the effective
  variant.

A FASTER step whose variant the rig does not play at the source's reach plays the
same rate one reach step narrower where it does (never two: that would read as NARROW),
noted ("faster here needs a narrower reach"). **The song outranks the arrangement:** a
section whose step would make one of the plan's events worse than with every part on its
source variant takes its next candidate, and at the last gives way to the event and plays
its source (`GiveWay`, `RenderingPipeline._settle_arrangement`). So every carrier varies the introduced look
by one step: a restating section plays the
introducer's variant, and a RESOLVE with no variation set steps from it SLOWER, else
NARROW, else restates. The step carries the source's reach and rate *class* across
templates by name. A step off the grid, a variant not admitted for the part's template on
this rig and song, or a source variant not on the grid plays the source variant (or,
where that is not admitted for this template, the template's effective variant), with the
reason; so does a step to a ladder variant (`narrow`, `slow`) the gate found to play the
same frames as the base here. A section with no motif and no variation plays exactly as
before (its named preset, else the effective variant): no part is resolved.

The render (`pipeline.RenderingPipeline`) and the plan repair (`rig_repair`) both call
`resolve_arrangement`, the render with the gate's admission and the repair with its offer.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection

VARIATION_PRESETS = frozenset(
    {"wide", "fast", "narrow+slow", "narrow+fast", "wide+slow", "wide+fast"}
)
"""The catalog's variation variants beyond `narrow` and `slow` (song-intent W10a): reach
`narrow|wide` by rate `slow|fast` and their combinations. Each is dry-compiled and offered
when it passes, but none is ever a template's effective variant: they ask for more reach
or rate, or would admit a template its ladder (base, `narrow`, `slow`) refuses."""

BASE = "base"
"""The name of the variant that applies no preset."""

_REACH = ("narrow", None, "wide")
_RATE = ("slow", None, "fast")
_STEPS = {"NARROW": (0, -1), "WIDEN": (0, 1), "SLOWER": (1, -1), "FASTER": (1, 1)}
_EDGES = {"NARROW": "narrowest", "WIDEN": "widest", "SLOWER": "slowest", "FASTER": "fastest"}


def grid_position(variant: str) -> tuple[int, int] | None:
    """A variant's place on the reach-by-rate grid (indexes into narrow/base/wide and
    slow/base/fast); None for a preset off it."""
    if variant == BASE:
        return 1, 1
    reach, _, rate = variant.partition("+")
    if not rate:
        if reach in _REACH:
            return _REACH.index(reach), 1
        if reach in _RATE:
            return 1, _RATE.index(reach)
        return None
    if reach in ("narrow", "wide") and rate in ("slow", "fast"):
        return _REACH.index(reach), _RATE.index(rate)
    return None


def grid_variant(reach: int, rate: int) -> str:
    """The variant at a place on the grid."""
    names = [name for name in (_REACH[reach], _RATE[rate]) if name is not None]
    return "+".join(names) if names else BASE


@dataclass(frozen=True)
class VariantOptions:
    """What a template can play on this rig and song: its effective variant and the
    variants admitted (`BASE` for no preset)."""

    effective: str
    admitted: frozenset[str]
    plays_as_base: frozenset[str] = frozenset()
    """Admitted variants that play the same frames as the base here: never a step."""


@dataclass(frozen=True)
class PartVariant:
    """One part's resolved variant and how it was reached."""

    section_id: str
    part_index: int
    template_id: str
    asked: str
    """The section's variation (`NONE` where the motif alone decides)."""
    relative_to: str
    """What the step is taken from, in words."""
    source: str
    """The variant the step is taken from."""
    plays: str
    """The variant the part plays (`BASE` for no preset)."""
    named: str | None
    """The preset the planner named for the part, if any."""
    reason: str | None = None
    """Why the part plays its source variant instead of the step, or plays its template's
    effective variant instead of its source's."""
    note: str | None = None
    """How a step that plays was reached otherwise than asked (a FASTER step that needs a
    narrower reach on this rig)."""

    @property
    def preset_id(self) -> str | None:
        """The preset the part plays, None for the base."""
        return None if self.plays == BASE else self.plays

    def record(self) -> dict[str, object]:
        """The trace's entry."""
        record: dict[str, object] = {
            "asked": self.asked,
            "relative_to": self.relative_to,
            "from": self.source,
            "plays": self.plays,
        }
        if self.named is not None and self.named != self.preset_id:
            record["named"] = self.named
        if self.reason:
            record["reason"] = self.reason
        if self.note:
            record["note"] = self.note
        return record


@dataclass(frozen=True)
class SectionArrangement:
    """One plan section's motif relation and the variant each part plays (None for a
    part that plays as without arrangement)."""

    section_id: str
    motif_id: str | None
    relation: str | None
    source_id: str | None
    parts: tuple[PartVariant | None, ...]

    def record(self, part_index: int) -> dict[str, object]:
        """The trace's `arrangement` entry for one of the section's parts."""
        record: dict[str, object] = {}
        if self.motif_id is not None:
            record["motif"] = {
                "id": self.motif_id,
                "relation": self.relation,
                **({"source": self.source_id} if self.source_id else {}),
            }
        variant = self.parts[part_index] if part_index < len(self.parts) else None
        if variant is not None:
            record["variation"] = variant.record()
        return record


def motif_relations(
    plan: ChoreographyPlan,
    threads: Mapping[str, tuple[Sequence[str], str]] | None = None,
    *,
    keep_resolve: bool = False,
) -> dict[str, tuple[str, str | None]]:
    """Per section carrying a motif, its relation and source section (the motif's
    introducing section), as the module docstring says; `threads`, per motif id, the
    macro thread's section ids and evolution. Values written on the plan are never read,
    except, with `keep_resolve` (the render, which has no macro plan), a later carrier's
    RESOLVE."""
    out: dict[str, tuple[str, str | None]] = {}
    introduced: dict[str, str] = {}
    for section in plan.sections:
        motif = section.motif_id
        if motif is None:
            continue
        source = introduced.get(motif)
        if source is None:
            out[section.section_id] = ("INTRODUCE", None)
            introduced[motif] = section.section_id
            continue
        thread = (threads or {}).get(motif)
        if thread is not None and section.section_id in thread[0]:
            relation = "RESTATE" if thread[1] == "INTRODUCE" else thread[1]
        elif keep_resolve and section.motif_relation == "RESOLVE":
            relation = "RESOLVE"
        else:
            relation = "RESTATE" if section.variation.value == "NONE" else "VARY"
        out[section.section_id] = (relation, source)
    return out


def with_motif_relations(
    plan: ChoreographyPlan, threads: Mapping[str, tuple[Sequence[str], str]] | None = None
) -> ChoreographyPlan:
    """The plan with each section's motif relation and source derived and written
    (code-owned: whatever arrived is overwritten, and cleared on a section without a
    motif), from the macro motif threads where given; with threads, a section no thread
    lists and a repeated introduction (played as a restatement) are recorded in
    `plan.repairs`."""
    from twinklr.core.agents.sequencer.moving_heads.models import PlanRepair, RepairAction

    relations = motif_relations(plan, threads)
    repairs = list(plan.repairs)
    for section in plan.sections:
        motif = section.motif_id
        if motif is None or threads is None:
            continue
        relation, source = relations[section.section_id]
        thread = threads.get(motif)
        if thread is None or section.section_id not in thread[0]:
            why = (
                f"no macro motif thread lists section {section.section_id!r}: its relation "
                f"({relation}) follows plan order"
            )
        elif source is not None and thread[1] == "INTRODUCE":
            why = (
                f"the macro thread introduces motif {motif!r}, which section {source!r} "
                "already introduced: this section restates it"
            )
        else:
            continue
        record = PlanRepair(
            section_id=section.section_id,
            item=f"motif {motif}",
            action=RepairAction.RECORDED,
            reason=why,
        )
        if record not in repairs:  # normalising twice records once
            repairs.append(record)
    sections = [
        section.model_copy(
            update={
                "motif_relation": relations.get(section.section_id, (None, None))[0],
                "motif_source_id": relations.get(section.section_id, (None, None))[1],
            }
        )
        for section in plan.sections
    ]
    return plan.model_copy(update={"sections": sections, "repairs": repairs})


@dataclass(frozen=True)
class GiveWay:
    """A section whose variation gave way to its events (`RenderingPipeline.render`): the
    variants it may not play (each worsened an event against its source variant) and the
    event it gave way to, in words."""

    rejected: frozenset[str]
    because: str


def resolve_arrangement(
    plan: ChoreographyPlan,
    options: Callable[[str], VariantOptions],
    canonical: Callable[[str], str] = lambda template_id: template_id,
    *,
    give_way: Mapping[str, GiveWay] | None = None,
    steps: bool = True,
) -> dict[str, SectionArrangement]:
    """Per plan section with a motif or a variation, its relation and each part's resolved
    variant (module docstring); `options` gives a template's (canonical id) effective and
    admitted variants, `canonical` a template id's canonical form. `give_way`, per section,
    the variants it may not play (the next candidate plays: a FASTER step's narrower
    reach, else the source variant); without `steps` every part plays its source (the
    song's events are judged against that)."""
    relations = motif_relations(plan, keep_resolve=True)
    played: dict[tuple[str, int], tuple[str, str]] = {}
    """Per (section, part index), the template and the variant it plays."""
    out: dict[str, SectionArrangement] = {}
    for section in plan.sections:
        relation, source_id = relations.get(section.section_id, (None, None))
        arranged = section.motif_id is not None or section.variation.value != "NONE"
        parts: list[PartVariant | None] = []
        for index, part in enumerate(section.parts):
            template_id = canonical(part.template_id)
            choice = options(template_id)
            named = part.preset_id or None
            own = named if named is not None and named in choice.admitted else choice.effective
            if not arranged:
                played[section.section_id, index] = (template_id, own)
                parts.append(None)
                continue
            variant = _resolve_part(
                section,
                index,
                template_id,
                choice,
                own,
                named,
                relation,
                source_id,
                played,
                (give_way or {}).get(section.section_id),
                steps,
            )
            played[section.section_id, index] = (template_id, variant.plays)
            parts.append(variant)
        if arranged:
            out[section.section_id] = SectionArrangement(
                section_id=section.section_id,
                motif_id=section.motif_id,
                relation=relation,
                source_id=source_id,
                parts=tuple(parts),
            )
    return out


def _resolve_part(
    section: PlanSection,
    index: int,
    template_id: str,
    choice: VariantOptions,
    own: str,
    named: str | None,
    relation: str | None,
    source_id: str | None,
    played: Mapping[tuple[str, int], tuple[str, str]],
    give_way: GiveWay | None = None,
    stepping: bool = True,
) -> PartVariant:
    asked = section.variation.value
    source_parts = [k for k in played if k[0] == source_id]
    if relation not in (None, "INTRODUCE") and source_parts:
        at = min(index, len(source_parts) - 1)
        source = played[source_parts[at]][1]
        relative_to = (
            f"motif {section.motif_id!r} as section {source_id!r} introduced it, part {at + 1}"
        )
    else:
        # Without a motif, a part with a step to take steps from the previous section on
        # its template; an introducing section, or one with no step, from its own.
        previous = [
            variant
            for (section_id, _), (template, variant) in played.items()
            if template == template_id and section_id != section.section_id
        ]
        if previous and asked != "NONE" and section.motif_id is None:
            source = previous[-1]
            earlier = next(
                section_id
                for (section_id, _), (template, _) in reversed(list(played.items()))
                if template == template_id and section_id != section.section_id
            )
            relative_to = f"the previous section on {template_id} ({earlier!r})"
        else:
            source = own
            relative_to = "its own preset" if named and own == named else "its effective variant"
    steps: list[str] = []
    if not stepping:
        steps = []
    elif asked != "NONE":
        steps = [asked]
    elif relation == "RESOLVE":
        steps = ["SLOWER", "NARROW"]
    rejected = frozenset() if give_way is None else give_way.rejected

    def fallback(why: str) -> PartVariant:
        if source in choice.admitted:
            plays, why_now = source, why
        else:
            plays = choice.effective
            why_now = (
                f"{why}; {source!r} is not admitted for {template_id} on this rig and song, so "
                "it plays its effective variant"
                if why
                else f"{source!r} is not admitted for {template_id} on this rig and song, so it "
                "plays its effective variant"
            )
        return PartVariant(
            section_id=section.section_id,
            part_index=index,
            template_id=template_id,
            asked=asked,
            relative_to=relative_to,
            source=source,
            plays=plays,
            named=named,
            reason=why_now or None,
        )

    if not steps:
        return fallback("")
    position = grid_position(source)
    if position is None:
        return fallback(f"{asked}: the source variant {source!r} is not on the reach/rate grid")
    reasons = []
    for step in steps:
        axis, delta = _STEPS[step]
        place = list(position)
        place[axis] += delta
        if not 0 <= place[axis] <= 2:
            reasons.append(f"{step}: {source!r} is already the {_EDGES[step]} variant")
            continue
        target = grid_variant(place[0], place[1])
        # The candidates: the step, then for FASTER the same rate one reach step narrower
        # (the rig's speed is a speed of reach per period; never two steps, which would
        # read as NARROW).
        candidates = [target]
        if step == "FASTER" and place[0] > 0:
            candidates.append(grid_variant(place[0] - 1, place[1]))
        note = None
        chosen = None
        for candidate in candidates:
            if candidate in choice.plays_as_base or candidate not in choice.admitted:
                why = (
                    f"{candidate!r} of {template_id} plays the same as base here"
                    if candidate in choice.plays_as_base
                    else f"{candidate!r} of {template_id} is not admitted on this rig and song"
                )
            elif candidate in rejected:
                assert give_way is not None
                why = f"{candidate!r} gave way to {give_way.because}"
            else:
                chosen = candidate
                break
            note = f"{step}: {why}" if note is None else f"{note}; {why}"
        if chosen is None:
            reasons.append(note or step)
            continue
        if chosen != target:
            note = f"{note}; faster here needs a narrower reach: it plays {chosen!r}"
        target = chosen
        return PartVariant(
            section_id=section.section_id,
            part_index=index,
            template_id=template_id,
            asked=asked if asked != "NONE" else f"RESOLVE ({step})",
            relative_to=relative_to,
            source=source,
            plays=target,
            named=named,
            note=note,
        )
    if give_way is not None and any("gave way to" in reason for reason in reasons):
        return fallback(
            f"the variation gave way to {give_way.because} ({'; '.join(reasons)}): it plays "
            "the source variant"
        )
    return fallback("; ".join(reasons) + ": it plays the source variant")


def options_from_variants(
    variants: Mapping[str, Collection[str]],
    declared: Callable[[str], Sequence[str]],
    plays_as_base: Mapping[str, Collection[str]] | None = None,
) -> Callable[[str], VariantOptions]:
    """`resolve_arrangement`'s options from a gate's admitted variants per template (each in
    its rung order, `BASE` for no preset) and those of them that play as its base; a
    template the gate did not judge plays every preset it declares, and its base by
    default."""

    def options(template_id: str) -> VariantOptions:
        admitted = variants.get(template_id)
        if admitted is None:
            return VariantOptions(
                effective=BASE, admitted=frozenset({BASE, *declared(template_id)})
            )
        ladder = [v for v in admitted if v not in VARIATION_PRESETS]
        return VariantOptions(
            effective=ladder[0] if ladder else BASE,
            admitted=frozenset(admitted),
            plays_as_base=frozenset((plays_as_base or {}).get(template_id, ())),
        )

    return options
