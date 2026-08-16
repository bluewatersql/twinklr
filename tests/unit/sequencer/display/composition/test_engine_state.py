"""Per-run state isolation tests for the composition engine."""

from twinklr.core.sequencer.display.models.render_plan import RenderPlan
from twinklr.core.sequencer.vocabulary import GPBlendMode

from .p3_t1_fixtures import make_authored_plan, make_engine


def _without_render_id(plan: RenderPlan) -> dict[str, object]:
    return plan.model_dump(exclude={"render_id"})


def test_compose_resets_layer_blend_modes() -> None:
    reused = make_engine()
    reused.compose(make_authored_plan(placement_id="first", blend_mode=GPBlendMode.ADD))
    second_reused = reused.compose(
        make_authored_plan(placement_id="second", blend_mode=GPBlendMode.MAX)
    )
    second_fresh = make_engine().compose(
        make_authored_plan(placement_id="second", blend_mode=GPBlendMode.MAX)
    )

    assert _without_render_id(second_reused) == _without_render_id(second_fresh)
    assert second_reused.groups[0].layers[0].blend_mode == "Max"
