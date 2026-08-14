"""P4-F26 repaired: an 8-head rig renders its sections.

`_infer_fixture_role` only had spatial role maps for group sizes 1-4; larger groups
got positional names (`ALL_0`..`ALL_7`) matching no role any template declares, and
`compile_template`'s role filter then came back empty for every step of every
section and `continue`d past it. No exception, no surfaced warning: the pipeline
reported a successful render of a show in which only the (separately defective)
transitions emitted anything at all.

Two changes make this rig work, and both are needed:

- roles for rigs of any size are drawn from the spatial vocabulary, spread evenly
  left to right;
- a step's semantic group is resolved against the roles the *rig* has rather than
  the four a template happens to declare, and a group that still matches nothing
  raises `UnsupportedRigShapeError` instead of being skipped.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.golden.harness import RIGS, build_fixture_group
from twinklr.core.curves.registry import CurveRegistry
from twinklr.core.sequencer.models.context import FixtureContext, TemplateCompileContext
from twinklr.core.sequencer.models.enum import TemplateRole
from twinklr.core.sequencer.models.moving_heads.rig import rig_profile_from_fixture_group
from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
    UnsupportedRigShapeError,
    compile_template,
)
from twinklr.core.sequencer.moving_heads.fixture_builder import build_fixture_contexts
from twinklr.core.sequencer.moving_heads.handlers.defaults import create_default_registries
from twinklr.core.sequencer.moving_heads.templates import get_template, load_builtin_templates
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.golden.harness import RenderResult, RigSpec


def test_8head_rig_renders_section_segments(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """Every plan section emits effects, on all eight heads."""
    result = render_cached(RIGS["mh8_reference"])
    section_effects = [effect for effect in result.effects if effect.step_id != "transition"]

    assert section_effects, "8-head rig still renders no section segments"
    assert {effect.fixture_id for effect in section_effects} == {
        f"MH{index + 1}" for index in range(8)
    }
    assert "intro" in result.sections()


def test_8head_rig_fixture_roles_are_spatial(
    render_cached: Callable[[RigSpec], RenderResult],
) -> None:
    """The mechanism, named so a future reader does not have to re-derive it."""
    fixture_group = build_fixture_group(RIGS["mh8_reference"])
    rig_profile = rig_profile_from_fixture_group(fixture_group)
    contexts = build_fixture_contexts(rig_profile, fixture_group)

    roles = [context.role for context in contexts]
    assert roles == [
        TemplateRole.FAR_LEFT,
        TemplateRole.OUTER_LEFT,
        TemplateRole.MID_LEFT,
        TemplateRole.INNER_LEFT,
        TemplateRole.INNER_RIGHT,
        TemplateRole.MID_RIGHT,
        TemplateRole.OUTER_RIGHT,
        TemplateRole.FAR_RIGHT,
    ]


def test_a_group_the_rig_cannot_fill_raises_rather_than_going_dark() -> None:
    """The loud half of the fix.

    `split_lr_sweep_counter` addresses LEFT and RIGHT. A single-fixture rig is
    `CENTER` only and cannot supply either; that is a rig/plan mismatch the operator
    has to see, not a section to skip in silence.
    """
    load_builtin_templates()
    template = get_template("split_lr_sweep_counter").template
    registries = create_default_registries()

    context = TemplateCompileContext(
        section_id="section",
        template_id=template.template_id,
        fixtures=[FixtureContext(fixture_id="MH1", role="CENTER", calibration={})],
        beat_grid=BeatGrid.from_tempo(tempo_bpm=120.0, total_bars=8, beats_per_bar=4),
        start_bar=1,
        duration_bars=4,
        curve_registry=CurveRegistry(),
        geometry_registry=registries["geometry"],
        movement_registry=registries["movement"],
        dimmer_registry=registries["dimmer"],
    )

    with pytest.raises(UnsupportedRigShapeError, match="split_lr_sweep_counter"):
        compile_template(template, context)
