from __future__ import annotations

from rig_models import RigProfile

from blinkb0t.core.config.fixtures import FixtureGroup
from blinkb0t.core.domains.sequencer.moving_heads.models.base import (
    OrderMode,
    SemanticGroup,
    TemplateRole,
)


def rig_profile_from_fixture_group(
    group: FixtureGroup,
    *,
    rig_id: str | None = None,
    infer_semantic_groups: bool = True,
    infer_orders: bool = True,
    infer_roles: bool = True,
    dimmer_floor_dmx: int | None = None,
) -> RigProfile:
    """Create a RigProfile from a FixtureGroup.

    Assumptions (MVP):
    - ordering is based on FixturePosition.position_index when available
    - rooftop 4-head common groups/orders can be inferred

    You can turn off inference and provide groups/orders/roles explicitly.

    Example Usage:
    from rig_adapters import rig_profile_from_fixture_group

    rig = rig_profile_from_fixture_group(
        moving_heads_group,
        rig_id="rooftop_4",
        dimmer_floor_dmx=60,  # set your real floor here
    )
    """

    fixtures = group.expand_fixtures()

    # Order left->right using position_index when present, otherwise fixture_id.
    def _sort_key(fx):
        pos = getattr(fx.config, "position", None)
        if pos is not None and getattr(pos, "position_index", None) is not None:
            return (int(pos.position_index), fx.fixture_id)
        return (10_000, fx.fixture_id)

    fixtures_sorted = sorted(fixtures, key=_sort_key)
    fixture_ids = [f.fixture_id for f in fixtures_sorted]

    groups: dict[SemanticGroup, list[str]] = {}
    orders: dict[OrderMode, list[str]] = {}
    role_bindings: dict[str, TemplateRole] = {}

    if infer_orders:
        orders[OrderMode.LEFT_TO_RIGHT] = list(fixture_ids)
        orders[OrderMode.RIGHT_TO_LEFT] = list(reversed(fixture_ids))

        # Outside-in / inside-out require at least 4 fixtures to be meaningful.
        if len(fixture_ids) >= 4:
            # OUTSIDE_IN: [1, N, 2, N-1, ...]
            outside_in: list[str] = []
            left = 0
            right = len(fixture_ids) - 1
            while left <= right:
                if left == right:
                    outside_in.append(fixture_ids[left])
                else:
                    outside_in.append(fixture_ids[left])
                    outside_in.append(fixture_ids[right])
                left += 1
                right -= 1
            orders[OrderMode.OUTSIDE_IN] = outside_in
            orders[OrderMode.INSIDE_OUT] = list(reversed(outside_in))

            odds = fixture_ids[::2]
            evens = fixture_ids[1::2]
            orders[OrderMode.ODD_EVEN] = odds + evens

    if infer_semantic_groups:
        groups[SemanticGroup.ALL] = list(fixture_ids)
        mid = len(fixture_ids) // 2
        groups[SemanticGroup.LEFT] = fixture_ids[:mid]
        groups[SemanticGroup.RIGHT] = fixture_ids[mid:]

        if len(fixture_ids) >= 4:
            groups[SemanticGroup.OUTER] = [fixture_ids[0], fixture_ids[-1]]
            groups[SemanticGroup.INNER] = fixture_ids[1:-1]

        groups[SemanticGroup.ODD] = fixture_ids[::2]
        groups[SemanticGroup.EVEN] = fixture_ids[1::2]

    if infer_roles:
        role_bindings = _resolve_role_bindings(fixture_ids)

    calib_kwargs = {}
    if dimmer_floor_dmx is not None:
        calib_kwargs["dimmer_floor_dmx"] = dimmer_floor_dmx

    return RigProfile(
        rig_id=rig_id or group.group_id,
        fixtures=fixture_ids,
        groups=groups,
        orders=orders,
        role_bindings=role_bindings,
        calibration=calib_kwargs or {},
    )


def _resolve_role_bindings(fixture_ids: list[str]) -> dict[str, TemplateRole]:
    """
    Deterministically bind each fixture (ordered left->right) to a TemplateRole.

    Contract (matches the semantics we discussed):
    - N=4 special-case maps to OUTER/INNER/INNER/OUTER (your POC layout)
    - Even N>=6:
        1 FAR_LEFT, 2 OUTER_LEFT, 3 INNER_LEFT (if N>=8), mids, CENTER_LEFT, CENTER_RIGHT, mids, INNER_RIGHT, OUTER_RIGHT, FAR_RIGHT
      where MID_* can be a multi-fixture band for larger rigs (e.g., N=12).
    - Odd N is handled sensibly (CENTER is the single middle fixture), but your
      main targets (4/6/8/12) are even.
    """
    n = len(fixture_ids)
    if n == 0:
        return {}

    # --- Exactly 4 fixtures ---
    if n == 4:
        return {
            fixture_ids[0]: TemplateRole.OUTER_LEFT,
            fixture_ids[1]: TemplateRole.INNER_LEFT,
            fixture_ids[2]: TemplateRole.INNER_RIGHT,
            fixture_ids[3]: TemplateRole.OUTER_RIGHT,
        }

    role_bindings: dict[str, TemplateRole] = {}

    def bind(idx: int, role: TemplateRole) -> None:
        # deterministic: first bind wins (avoid overwriting if logic overlaps)
        if 0 <= idx < n and fixture_ids[idx] not in role_bindings:
            role_bindings[fixture_ids[idx]] = role

    # --- Anchors ---
    bind(0, TemplateRole.FAR_LEFT)
    bind(n - 1, TemplateRole.FAR_RIGHT)

    # --- Outer band (only distinct once there are at least 6 fixtures) ---
    if n >= 6:
        bind(1, TemplateRole.OUTER_LEFT)
        bind(n - 2, TemplateRole.OUTER_RIGHT)

    # --- Centers ---
    if n % 2 == 0:
        # even: center pair
        cl = (n // 2) - 1
        cr = n // 2
        bind(cl, TemplateRole.CENTER_LEFT)
        bind(cr, TemplateRole.CENTER_RIGHT)

        # --- Inner band (distinct once there is room between outer and center => N>=8) ---
        if n >= 8:
            il = 2
            ir = n - 3
            bind(il, TemplateRole.INNER_LEFT)
            bind(ir, TemplateRole.INNER_RIGHT)

            # --- Mid bands: anything between INNER and CENTER on each side ---
            for i in range(il + 1, cl):
                bind(i, TemplateRole.MID_LEFT)
            for i in range(cr + 1, ir):
                bind(i, TemplateRole.MID_RIGHT)

        # For N=6, INNER/MID conceptually alias to center roles; fixture->role is already covered.
        # For N=8, MID aliases to center roles; fixture->role is already covered.

    else:
        # odd: single center
        c = n // 2
        bind(c, TemplateRole.CENTER)

        # nearest neighbors get CENTER_LEFT / CENTER_RIGHT if present
        bind(c - 1, TemplateRole.CENTER_LEFT)
        bind(c + 1, TemplateRole.CENTER_RIGHT)

        # make OUTER distinct once there are enough fixtures
        if n >= 7:
            bind(1, TemplateRole.OUTER_LEFT)
            bind(n - 2, TemplateRole.OUTER_RIGHT)

        # make INNER distinct once there's room (odd analogue of N>=8 => N>=9)
        if n >= 9:
            il = 2
            ir = n - 3
            bind(il, TemplateRole.INNER_LEFT)
            bind(ir, TemplateRole.INNER_RIGHT)

            # mid bands between inner and center-neighbor
            for i in range(il + 1, c - 1):
                bind(i, TemplateRole.MID_LEFT)
            for i in range(c + 2, ir):
                bind(i, TemplateRole.MID_RIGHT)

    # --- Fill any remaining unbound fixtures deterministically (rare edge cases) ---
    # Prefer to classify by side and proximity so nothing is left unassigned.
    if len(role_bindings) < n:
        # Compute a "center" index for side classification
        center_pos = (n - 1) / 2.0
        for i, fid in enumerate(fixture_ids):
            if fid in role_bindings:
                continue
            if i < center_pos:
                role_bindings[fid] = TemplateRole.MID_LEFT
            elif i > center_pos:
                role_bindings[fid] = TemplateRole.MID_RIGHT
            else:
                role_bindings[fid] = TemplateRole.CENTER

    return role_bindings
