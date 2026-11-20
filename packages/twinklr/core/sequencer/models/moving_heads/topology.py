"""Stable rig topology and phase distribution for the moving-head renderer (P2.2).

A `FixtureTopology` describes the canonical full rig: where each head sits, by row,
column and a unique ordinal. A template step's `PhaseDistribution`s spread
phase over it, each over its own domains (pan, tilt, dimmer, shutter). A head's rank is
its place in the canonical `(row, column, ordinal, fixture_id)` order of the whole rig,
fixed before any head is selected, so rendering a subset of heads, or a rig with a head
missing, leaves a hole instead of rephasing the others. A row derived from
`position_index` ranks each head by its index, so a skipped index is a hole too.

Per spec: two mirrored wings fold the ordered rig (`min(i, n-1-i)`); blocks of
`block_size` consecutive (folded) ranks share a slot; `group_count` interleaves the
blocks into that many slots. The offset is `spread_cycles * slot / (S - 1)`, exactly,
with `spread_cycles` taken at its decimal value; `reverse` counts slots from the other
end. Slot 0 leads: a head's phase in a domain is the step phase minus its offset. Two
wings also give the pan displacement a sign, left -1, right +1, and 0 at an odd center.
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.timing.musical_phase import exact_decimal

if TYPE_CHECKING:
    from twinklr.core.config.fixtures.groups import FixtureGroup

PHASE_DOMAINS: tuple[ChannelName, ...] = (
    ChannelName.PAN,
    ChannelName.TILT,
    ChannelName.DIMMER,
    ChannelName.SHUTTER,
)
"""Channels whose physical phase can be distributed. Color and gobo are held states."""


class TopologyMember(BaseModel):
    """One head's place in the canonical rig."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fixture_id: Annotated[str, Field(pattern=r"\S")]
    row: int
    column: int
    ordinal: int


class FixtureTopology(BaseModel):
    """The canonical full rig, including heads a group may lack (missing or disabled)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    members: tuple[TopologyMember, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_identity(self) -> FixtureTopology:
        for name in ("fixture_id", "ordinal"):
            values = [getattr(member, name) for member in self.members]
            repeated = sorted({value for value in values if values.count(value) > 1})
            if repeated:
                raise ValueError(f"topology members repeat {name} {repeated}")
        return self

    @property
    def canonical_ids(self) -> tuple[str, ...]:
        """Every member's fixture id in canonical `(row, column, ordinal, fixture_id)` order."""
        ordered = sorted(
            self.members,
            key=lambda member: (member.row, member.column, member.ordinal, member.fixture_id),
        )
        return tuple(member.fixture_id for member in ordered)

    def slots(self) -> tuple[dict[str, int], int]:
        """Each member's rank, its place in canonical order, and the rig's slot count."""
        ids = self.canonical_ids
        return {fixture_id: rank for rank, fixture_id in enumerate(ids)}, len(ids)


class DerivedRowTopology(FixtureTopology):
    """One row derived from each fixture's `position.position_index` (its column).

    A head's rank is its index minus one, so an index the file skips is an empty slot
    and a missing head keeps its place whenever the remaining indices show it; the slot
    count is the highest index.
    """

    def slots(self) -> tuple[dict[str, int], int]:
        """Each head's rank and the slot count.

        Raises:
            ValueError: Naming the fixtures that share a position_index.
        """
        columns = [member.column for member in self.members]
        shared = sorted(
            member.fixture_id for member in self.members if columns.count(member.column) > 1
        )
        if shared:
            raise ValueError(
                f"fixtures {shared} share a position_index, so the row derived from it "
                "cannot rank them; give each its own index or declare a topology"
            )
        return {member.fixture_id: member.column - 1 for member in self.members}, max(columns)


class PhaseDistribution(BaseModel):
    """A phase spread over the rig topology for the listed domains of one step.

    With two wings, mirror_pan=False folds phase slots without reflecting pan travel.
    It requires the pan domain; existing two-wing distributions mirror by default.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    domains: tuple[ChannelName, ...] = Field(min_length=1)
    block_size: int = Field(default=1, ge=1)
    group_count: int | None = Field(default=None, ge=1)
    wings: Literal[1, 2] = 1
    mirror_pan: bool = Field(default=True, exclude_if=lambda value: value)
    spread_cycles: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    direction: Literal["forward", "reverse"] = "forward"

    @model_validator(mode="after")
    def _validate_domains(self) -> PhaseDistribution:
        if not self.mirror_pan and (self.wings != 2 or ChannelName.PAN not in self.domains):
            raise ValueError("mirror_pan=False requires two wings and the pan domain")
        unphased = [domain.value for domain in self.domains if domain not in PHASE_DOMAINS]
        if unphased:
            raise ValueError(
                f"domains {unphased} carry no phase; only pan, tilt, dimmer and shutter do"
            )
        if len(set(self.domains)) != len(self.domains):
            raise ValueError("a distribution lists a domain more than once")
        return self


class ResolvedFixturePhase(BaseModel):
    """One head's canonical rank, its phase offset per domain and its pan sign."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: int
    phase_by_channel: dict[ChannelName, Fraction]
    pan_sign: Literal[-1, 0, 1]


def check_domain_ownership(specs: Sequence[PhaseDistribution]) -> None:
    """Reject two distributions that both own a domain.

    Raises:
        ValueError: Naming the domains owned twice.
    """
    owned = [domain for spec in specs for domain in spec.domains]
    repeated = sorted({domain.value for domain in owned if owned.count(domain) > 1})
    if repeated:
        raise ValueError(f"distributions both own domains {repeated}")


def resolve_distribution(
    topology: FixtureTopology,
    specs: Sequence[PhaseDistribution],
    selected_fixture_ids: tuple[str, ...],
) -> dict[str, ResolvedFixturePhase]:
    """Each selected head's phase offsets and pan sign, from its rank in the full rig.

    A domain no spec owns has offset 0; the pan sign comes from the spec owning pan, and
    is +1 when none does or it has one wing. The result for a head depends only on the
    topology and the specs, never on which other heads are selected.

    Raises:
        ValueError: If two specs own a domain, a selected head is not in the topology,
            or a derived row's heads share a position_index.
    """
    check_domain_ownership(specs)
    ranks, count = topology.slots()
    unknown = [fixture_id for fixture_id in selected_fixture_ids if fixture_id not in ranks]
    if unknown:
        raise ValueError(f"fixtures {unknown} are not members of the rig topology")

    resolved: dict[str, ResolvedFixturePhase] = {}
    for fixture_id in selected_fixture_ids:
        rank = ranks[fixture_id]
        offsets = dict.fromkeys(PHASE_DOMAINS, Fraction(0))
        sign: Literal[-1, 0, 1] = 1
        for spec in specs:
            for domain in spec.domains:
                offsets[domain] = _offset(spec, rank, count)
            if ChannelName.PAN in spec.domains and spec.wings == 2 and spec.mirror_pan:
                center = Fraction(count - 1, 2)
                sign = -1 if rank < center else 1 if rank > center else 0
        resolved[fixture_id] = ResolvedFixturePhase(
            rank=rank, phase_by_channel=offsets, pan_sign=sign
        )
    return resolved


def _offset(spec: PhaseDistribution, rank: int, count: int) -> Fraction:
    def block(rank: int) -> int:
        folded = min(rank, count - 1 - rank) if spec.wings == 2 else rank
        return folded // spec.block_size

    blocks = max(block(index) for index in range(count)) + 1
    b = block(rank)
    if spec.group_count is None:
        slots, slot = blocks, b
    else:
        slots, slot = min(blocks, spec.group_count), b % spec.group_count
    if slots == 1:
        return Fraction(0)
    if spec.direction == "reverse":
        slot = slots - 1 - slot
    return exact_decimal(spec.spread_cycles) * Fraction(slot, slots - 1)


def rig_topology(group: FixtureGroup) -> FixtureTopology | None:
    """The group's topology, else one row derived from `position.position_index`.

    The derived row (`DerivedRowTopology`) orders heads as
    `rig_profile_from_fixture_group` does, by `(position_index, fixture_id)`, and ranks
    each by its index, keeping skipped indices as empty slots. None when the group
    declares no topology and some fixture declares no position.
    """
    if group.topology is not None:
        return group.topology
    indexes: dict[str, int] = {}
    for fixture in group.expand_fixtures():
        position = fixture.config.position
        if position is None:
            return None
        indexes[fixture.fixture_id] = position.position_index
    if not indexes:
        return None
    ordered = sorted(indexes, key=lambda fixture_id: (indexes[fixture_id], fixture_id))
    return DerivedRowTopology(
        members=tuple(
            TopologyMember(
                fixture_id=fixture_id, row=0, column=indexes[fixture_id], ordinal=ordinal
            )
            for ordinal, fixture_id in enumerate(ordered)
        )
    )
