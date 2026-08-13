"""Evidence for P4-F26 beyond "degraded ordering": the 8-head rig renders no
section segments at all.

`_infer_fixture_role` (`fixture_builder.py`) only has spatial role maps for group
sizes 1-4 (`_ROLE_MAPS`); for any other size it falls back to positional names like
`ALL_0`..`ALL_7`. Every builtin template resolves its step target through
`resolve_semantic_group`, which matches fixtures by *role name* against the
template's declared `roles` (e.g. `TemplateRoleHelper.IN_OUT_LEFT_RIGHT` ->
`OUTER_LEFT`/`INNER_LEFT`/`INNER_RIGHT`/`OUTER_RIGHT`). None of the positional
`ALL_N` names for an 8-fixture rig match any declared role, so
`compile_template`'s `target_fixtures` filter (`template_compiler.py:129-136`)
comes back empty for every step and every section is silently skipped
(`continue` at `:137-139`) -- no exception, no warning surfaced by the pipeline.

This is a stronger manifestation than the phase-1P spec anticipated ("fragile
beyond [4 fixtures]", P4-F26) -- the pipeline does not merely order an 8-fixture
chase oddly, it renders *nothing* for any section on an 8-fixture rig using the
shipped role-mapping. Recorded here as evidence for P1P-T5/P1P-T11's scope, per
the P1P-T2 spec's guidance for exactly this risk ("do not fix it in this task").

Only the (also-defective, see `test_transition_segments_emit_all_zero`) transition
segments survive, because transition compilation does not filter by role.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.golden.harness import RIGS, build_fixture_group
from twinklr.core.sequencer.models.moving_heads.rig import rig_profile_from_fixture_group
from twinklr.core.sequencer.moving_heads.fixture_builder import build_fixture_contexts

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.golden.harness import RenderResult, RigSpec


def test_8head_rig_renders_no_section_segments(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """KNOWN-WRONG PIN (P4-F26, more severe than "degraded ordering"): zero section output.

    Every plan section (`intro`, `chorus`, `drop`, `breakdown`) is silently skipped for
    the 8-head rig; only the three inter-section transitions render. If this test
    starts failing because non-transition segments appear, the role-mapping fix has
    landed and this pin (and the rig's docstring in `harness.py`) should be updated
    together.
    """
    result = render_cached(RIGS["mh8_reference"])
    section_effects = [effect for effect in result.effects if effect.step_id != "transition"]
    assert section_effects == [], (
        "8-head rig unexpectedly rendered section segments -- P4-F26's role-mapping "
        f"gap may be fixed; got {len(section_effects)} non-transition effects"
    )
    assert result.sections() == [
        "transition_intro_to_chorus",
        "transition_chorus_to_drop",
        "transition_drop_to_breakdown",
    ]


def test_8head_rig_fixture_roles_do_not_match_any_template_role(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """Names the exact mechanism so a future reader does not have to re-derive it.

    `_infer_fixture_role` only maps group sizes 1-4 to spatial names; an 8-fixture
    group falls back to `ALL_0`..`ALL_7`, none of which are `OUTER_LEFT`/`INNER_LEFT`/
    `INNER_RIGHT`/`OUTER_RIGHT` (the roles every plan-fixture template in this suite
    declares), so `resolve_semantic_group`'s role-membership filter matches nothing.
    """
    fixture_group = build_fixture_group(RIGS["mh8_reference"])
    rig_profile = rig_profile_from_fixture_group(fixture_group)
    contexts = build_fixture_contexts(rig_profile, fixture_group)

    roles = {context.role for context in contexts}
    assert roles == {f"ALL_{index}" for index in range(8)}
    assert roles.isdisjoint({"OUTER_LEFT", "INNER_LEFT", "INNER_RIGHT", "OUTER_RIGHT"})
