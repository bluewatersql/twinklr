from __future__ import annotations

import pytest

from twinklr.core.audio.mir.metrics import event_f1, section_boundary_hit_rate


def test_beat_f1_uses_one_to_one_70ms_matching() -> None:
    score = event_f1(
        reference_s=[1.0, 2.0, 3.0],
        estimated_s=[0.95, 1.04, 2.20, 3.07],
        tolerance_s=0.070,
    )

    assert score.true_positives == 2
    assert score.false_positives == 2
    assert score.false_negatives == 1
    assert score.f1 == pytest.approx(4 / 7)


def test_downbeat_f1_does_not_double_match_one_reference() -> None:
    score = event_f1(
        reference_s=[1.0],
        estimated_s=[0.96, 1.04],
        tolerance_s=0.070,
    )

    assert score.true_positives == 1
    assert score.false_positives == 1
    assert score.f1 == pytest.approx(2 / 3)


def test_section_boundary_hit_rate_reports_strict_and_loose_windows() -> None:
    reference = [0.0, 5.0, 10.0, 15.0]
    estimated = [0.0, 5.4, 12.0, 15.0]

    strict = section_boundary_hit_rate(reference, estimated, tolerance_s=0.5)
    loose = section_boundary_hit_rate(reference, estimated, tolerance_s=3.0)

    assert strict == pytest.approx(0.75)
    assert loose == pytest.approx(1.0)
