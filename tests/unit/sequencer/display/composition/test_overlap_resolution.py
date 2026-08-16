"""Regression tests for P3-T1 running-list TRIM resolution."""

from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.display.models.render_event import RenderEvent, RenderEventSource
from twinklr.core.sequencer.vocabulary import LaneKind

from .p3_t1_fixtures import make_engine


def _event(event_id: str, start_ms: int, end_ms: int) -> RenderEvent:
    return RenderEvent(
        event_id=event_id,
        start_ms=start_ms,
        end_ms=end_ms,
        effect_type="On",
        palette=ResolvedPalette(colors=["#FFFFFF"], active_slots=[1]),
        value_curves={"brightness": "Active=TRUE|Value=50"},
        source=RenderEventSource(
            section_id="section",
            lane=LaneKind.BASE,
            group_id="G0",
            template_id="fixture",
        ),
    )


def test_short_neighbour_does_not_delete_tail() -> None:
    resolved = make_engine()._resolve_overlaps(
        [_event("A", 0, 100), _event("B", 10, 20), _event("C", 50, 200)]
    )

    assert [(event.start_ms, event.end_ms) for event in resolved] == [
        (0, 10),
        (10, 20),
        (20, 50),
        (50, 200),
    ]
    assert all(event.value_curves for event in resolved)
    assert len({event.event_id for event in resolved}) == len(resolved)


def test_full_eclipse_still_drops() -> None:
    resolved = make_engine()._resolve_overlaps([_event("A", 0, 20), _event("B", 0, 100)])

    assert [(event.event_id, event.start_ms, event.end_ms) for event in resolved] == [("B", 0, 100)]


def test_generated_tail_id_cannot_collide_with_source_id() -> None:
    resolved = make_engine()._resolve_overlaps(
        [
            _event("A", 0, 100),
            _event("B", 10, 20),
            _event("A__trim_tail_B", 200, 220),
            _event("A__trim_tail_B_2", 240, 260),
        ]
    )

    ids = [event.event_id for event in resolved]
    assert len(ids) == len(set(ids))
    assert "A__trim_tail_B" in ids
    assert "A__trim_tail_B_2" in ids
    assert "A__trim_tail_B_3" in ids
