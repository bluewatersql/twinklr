from __future__ import annotations

from pathlib import Path

import pytest

from twinklr.core.audio.mir.benchmark import ComponentSummary, FixtureMetrics, apply_adoption_gate
from twinklr.core.audio.mir.benchmark import _prepare_input as prepare_input
from twinklr.core.audio.mir.fixtures import MIRFixture, load_fixture_manifest
from twinklr.core.audio.mir.metrics import event_f1, section_boundary_hit_rate
from twinklr.core.audio.mir.sources import DSPSource, RhythmAnalysis, StructureAnalysis

MANIFEST = Path(__file__).parents[3] / "fixtures" / "mir" / "manifest.json"


@pytest.fixture(scope="module")
def dsp_fixture_result(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[MIRFixture, RhythmAnalysis, StructureAnalysis]:
    manifest = load_fixture_manifest(MANIFEST)
    fixture = manifest.fixtures[0]
    inputs = prepare_input(
        fixture,
        sample_rate=manifest.sample_rate,
        audio_path=tmp_path_factory.mktemp("mir") / "fixture.wav",
        hop_length=512,
    )
    source = DSPSource()
    rhythm = source.analyze_rhythm(inputs)
    return fixture, rhythm, source.analyze_structure(inputs, rhythm)


def test_beat_f1_on_click_track(
    dsp_fixture_result: tuple[MIRFixture, RhythmAnalysis, StructureAnalysis],
) -> None:
    fixture, rhythm, _ = dsp_fixture_result

    assert event_f1(fixture.beat_times_s, rhythm.beats_s, tolerance_s=0.070).f1 == pytest.approx(
        1.0
    )


def test_downbeat_f1_on_annotated_fixture(
    dsp_fixture_result: tuple[MIRFixture, RhythmAnalysis, StructureAnalysis],
) -> None:
    fixture, rhythm, _ = dsp_fixture_result

    assert event_f1(
        fixture.downbeat_times_s, rhythm.downbeats_s, tolerance_s=0.070
    ).f1 == pytest.approx(1.0)


def test_section_boundary_hit_rate_on_annotated_fixture(
    dsp_fixture_result: tuple[MIRFixture, RhythmAnalysis, StructureAnalysis],
) -> None:
    fixture, _, structure = dsp_fixture_result

    # This deliberately pins the current detector's poor strict baseline rather
    # than converting a miss into a structural-only assertion.
    assert section_boundary_hit_rate(
        fixture.section_boundaries_s,
        structure.boundary_times_s,
        tolerance_s=0.5,
    ) == pytest.approx(0.0)


def test_ab_harness_is_deterministic(tmp_path: Path) -> None:
    manifest = load_fixture_manifest(MANIFEST)
    fixture = manifest.fixtures[0]
    inputs = prepare_input(
        fixture,
        sample_rate=manifest.sample_rate,
        audio_path=tmp_path / "fixture.wav",
        hop_length=512,
    )
    source = DSPSource()

    first_rhythm = source.analyze_rhythm(inputs)
    second_rhythm = source.analyze_rhythm(inputs)
    first_structure = source.analyze_structure(inputs, first_rhythm)
    second_structure = source.analyze_structure(inputs, second_rhythm)

    assert first_rhythm == second_rhythm
    assert first_structure == second_structure


EXPECTED_FIXTURE_IDS = ("a", "b", "c", "d", "e")


def _fixture_metric(
    fixture_id: str, *, beat_f1: float, downbeat_f1: float, section_hit_rate: float
) -> FixtureMetrics:
    return FixtureMetrics(
        fixture_id=fixture_id,
        beat_f1=beat_f1,
        downbeat_f1=downbeat_f1,
        section_hit_rate_500ms=section_hit_rate,
        section_hit_rate_3s=section_hit_rate,
        signed_mean_beat_offset_s=0.0,
    )


def _summary(
    *,
    beat_f1: float,
    downbeat_f1: float,
    section_hit_rate: float = 0.0,
    fixture_ids: tuple[str, ...] = EXPECTED_FIXTURE_IDS,
) -> ComponentSummary:
    return ComponentSummary(
        source="test",
        version="1",
        available=True,
        deterministic=True,
        fixture_count=len(fixture_ids),
        mean_beat_f1=beat_f1,
        mean_downbeat_f1=downbeat_f1,
        mean_section_hit_rate_500ms=section_hit_rate,
        mean_section_hit_rate_3s=section_hit_rate,
        worst_fixture_beat_delta=0.0,
        fixtures=[
            _fixture_metric(
                fixture_id,
                beat_f1=beat_f1,
                downbeat_f1=downbeat_f1,
                section_hit_rate=section_hit_rate,
            )
            for fixture_id in fixture_ids
        ],
    )


def test_adoption_gate_requires_precommitted_downbeat_margin() -> None:
    baseline = _summary(beat_f1=0.90, downbeat_f1=0.60)
    candidate = _summary(beat_f1=0.89, downbeat_f1=0.649)

    decision = apply_adoption_gate(
        expected_fixture_ids=EXPECTED_FIXTURE_IDS,
        dsp=baseline,
        beat_this=candidate,
        allinone=None,
    )

    assert decision.rhythm == "reject"


def test_adoption_gate_accepts_only_when_both_rhythm_conditions_hold() -> None:
    baseline = _summary(beat_f1=0.90, downbeat_f1=0.60)
    candidate = _summary(beat_f1=0.88, downbeat_f1=0.65)

    decision = apply_adoption_gate(
        expected_fixture_ids=EXPECTED_FIXTURE_IDS,
        dsp=baseline,
        beat_this=candidate,
        allinone=None,
    )

    assert decision.rhythm == "adopt"


def test_adoption_gate_rejects_nondeterministic_or_unavailable_source() -> None:
    baseline = _summary(beat_f1=0.50, downbeat_f1=0.10, section_hit_rate=0.20)
    candidate = _summary(beat_f1=0.90, downbeat_f1=0.90, section_hit_rate=0.90)
    candidate = candidate.model_copy(update={"deterministic": False})

    decision = apply_adoption_gate(
        expected_fixture_ids=EXPECTED_FIXTURE_IDS,
        dsp=baseline,
        beat_this=candidate,
        allinone=candidate,
    )

    assert decision.rhythm == "reject"
    assert decision.structure == "reject"


def test_structure_gate_uses_absolute_point_one_improvement() -> None:
    baseline = _summary(beat_f1=0.8, downbeat_f1=0.5, section_hit_rate=0.40)
    candidate = _summary(beat_f1=0.0, downbeat_f1=0.0, section_hit_rate=0.50)

    decision = apply_adoption_gate(
        expected_fixture_ids=EXPECTED_FIXTURE_IDS,
        dsp=baseline,
        beat_this=None,
        allinone=candidate,
    )

    assert decision.structure == "adopt"


def test_structure_gate_does_not_add_a_loose_rate_nonregression_rule() -> None:
    baseline = _summary(beat_f1=0.8, downbeat_f1=0.5, section_hit_rate=0.40)
    candidate = _summary(beat_f1=0.0, downbeat_f1=0.0, section_hit_rate=0.50)
    candidate = candidate.model_copy(
        update={
            "fixtures": [
                metric.model_copy(update={"section_hit_rate_3s": 0.0})
                for metric in candidate.fixtures
            ],
            "mean_section_hit_rate_3s": 0.0,
        }
    )

    decision = apply_adoption_gate(
        expected_fixture_ids=EXPECTED_FIXTURE_IDS,
        dsp=baseline,
        beat_this=None,
        allinone=candidate,
    )

    assert decision.structure == "adopt"


def test_rhythm_gate_computes_per_fixture_guard_from_fixture_metrics() -> None:
    baseline = _summary(beat_f1=0.90, downbeat_f1=0.60)
    candidate = _summary(beat_f1=0.88, downbeat_f1=0.65).model_copy(
        update={"worst_fixture_beat_delta": 1.0}
    )
    candidate_metrics = list(candidate.fixtures)
    candidate_metrics[0] = candidate_metrics[0].model_copy(update={"beat_f1": 0.879})
    candidate = candidate.model_copy(update={"fixtures": candidate_metrics})

    decision = apply_adoption_gate(
        expected_fixture_ids=EXPECTED_FIXTURE_IDS,
        dsp=baseline,
        beat_this=candidate,
        allinone=None,
    )

    assert decision.rhythm == "reject"
    assert "worst_fixture_beat_delta=-0.021000" in decision.rhythm_reason


@pytest.mark.parametrize(
    "candidate_ids",
    [
        ("a", "b", "c", "d"),
        ("a", "b", "c", "d", "d"),
        ("a", "b", "c", "d", "other"),
    ],
)
def test_adoption_gate_requires_exact_unique_manifest_identity(
    candidate_ids: tuple[str, ...],
) -> None:
    baseline = _summary(beat_f1=0.80, downbeat_f1=0.50)
    candidate = _summary(
        beat_f1=0.80,
        downbeat_f1=0.90,
        section_hit_rate=0.90,
        fixture_ids=candidate_ids,
    ).model_copy(update={"fixture_count": 5})

    decision = apply_adoption_gate(
        expected_fixture_ids=EXPECTED_FIXTURE_IDS,
        dsp=baseline,
        beat_this=candidate,
        allinone=candidate,
    )

    assert decision.rhythm == "reject"
    assert decision.structure == "reject"
    assert "fixture identity" in decision.rhythm_reason
    assert "fixture identity" in decision.structure_reason


def test_adoption_gate_rejects_when_dsp_fixture_identity_is_not_the_manifest() -> None:
    baseline = _summary(
        beat_f1=0.80,
        downbeat_f1=0.50,
        fixture_ids=("a", "b", "c", "d", "other"),
    )
    candidate = _summary(beat_f1=0.80, downbeat_f1=0.90, section_hit_rate=0.90)

    decision = apply_adoption_gate(
        expected_fixture_ids=EXPECTED_FIXTURE_IDS,
        dsp=baseline,
        beat_this=candidate,
        allinone=candidate,
    )

    assert decision.rhythm == "reject"
    assert decision.structure == "reject"


def test_unavailable_summary_has_no_numeric_metric_means() -> None:
    summary = ComponentSummary(
        source="beat_this",
        version="1.1.0",
        available=False,
        deterministic=False,
        fixture_count=0,
        mean_beat_f1=None,
        mean_downbeat_f1=None,
        mean_section_hit_rate_500ms=None,
        mean_section_hit_rate_3s=None,
        worst_fixture_beat_delta=None,
        limitation="checkpoint unavailable",
    )

    payload = summary.model_dump()
    assert payload["mean_beat_f1"] is None
    assert payload["mean_downbeat_f1"] is None
    assert payload["mean_section_hit_rate_500ms"] is None
    assert payload["mean_section_hit_rate_3s"] is None
