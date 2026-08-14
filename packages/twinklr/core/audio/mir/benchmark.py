"""Offline A/B harness for the pre-committed P2P-T8 MIR adoption gate."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path
import sys
import tempfile
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
import soundfile as sf

from twinklr.core.audio.harmonic.hpss import compute_hpss, compute_onset_env
from twinklr.core.audio.harmonic.key import extract_chroma
from twinklr.core.audio.mir.fixtures import (
    MIRFixture,
    load_fixture_manifest,
    synthesize_fixture,
)
from twinklr.core.audio.mir.metrics import event_f1, section_boundary_hit_rate
from twinklr.core.audio.mir.sources import (
    AllInOneSource,
    BeatThisSource,
    DSPSource,
    MIRInput,
    MissingMIRDependencyError,
    RhythmAnalysis,
)

BEAT_TOLERANCE_S = 0.070
SECTION_TOLERANCE_S = 0.5
SECTION_LOOSE_TOLERANCE_S = 3.0


class FixtureMetrics(BaseModel):
    """A source's measured output on one committed fixture."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fixture_id: str
    beat_f1: float
    downbeat_f1: float
    section_hit_rate_500ms: float
    section_hit_rate_3s: float
    signed_mean_beat_offset_s: float | None


class ComponentSummary(BaseModel):
    """Mean metrics and availability/determinism status for one implementation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    version: str
    available: bool
    deterministic: bool
    fixture_count: int = Field(ge=0)
    mean_beat_f1: float | None
    mean_downbeat_f1: float | None
    mean_section_hit_rate_500ms: float | None
    mean_section_hit_rate_3s: float | None
    worst_fixture_beat_delta: float | None
    fixtures: list[FixtureMetrics] = Field(default_factory=list)
    limitation: str | None = None


class AdoptionDecision(BaseModel):
    """Mechanical outcome of the fixed gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rhythm: Literal["adopt", "reject"]
    structure: Literal["adopt", "reject"]
    rhythm_reason: str
    structure_reason: str


class BenchmarkReport(BaseModel):
    """Machine-readable complete A/B report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fixture_manifest: str
    fixture_count: int
    tolerances_s: dict[str, float]
    dsp: ComponentSummary
    beat_this: ComponentSummary
    allinone: ComponentSummary
    decision: AdoptionDecision


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    return float(np.mean(items)) if items else 0.0


def _signed_mean_offset(reference_s: list[float], estimated_s: list[float]) -> float | None:
    if not reference_s or not estimated_s:
        return None
    reference = np.asarray(reference_s, dtype=np.float64)
    offsets = [
        float(value - reference[np.argmin(np.abs(reference - value))]) for value in estimated_s
    ]
    return float(np.mean(offsets))


def _score(
    fixture: MIRFixture,
    rhythm: RhythmAnalysis,
    structure_boundaries_s: list[float],
) -> FixtureMetrics:
    return FixtureMetrics(
        fixture_id=fixture.id,
        beat_f1=event_f1(
            fixture.beat_times_s,
            rhythm.beats_s,
            tolerance_s=BEAT_TOLERANCE_S,
        ).f1,
        downbeat_f1=event_f1(
            fixture.downbeat_times_s,
            rhythm.downbeats_s,
            tolerance_s=BEAT_TOLERANCE_S,
        ).f1,
        section_hit_rate_500ms=section_boundary_hit_rate(
            fixture.section_boundaries_s,
            structure_boundaries_s,
            tolerance_s=SECTION_TOLERANCE_S,
        ),
        section_hit_rate_3s=section_boundary_hit_rate(
            fixture.section_boundaries_s,
            structure_boundaries_s,
            tolerance_s=SECTION_LOOSE_TOLERANCE_S,
        ),
        signed_mean_beat_offset_s=_signed_mean_offset(fixture.beat_times_s, rhythm.beats_s),
    )


def _same_rhythm(first: RhythmAnalysis, second: RhythmAnalysis) -> bool:
    return (
        first.tempo_bpm == second.tempo_bpm
        and first.beats_s == second.beats_s
        and first.downbeats_s == second.downbeats_s
        and first.beats_per_bar == second.beats_per_bar
    )


def _summary(
    *,
    source: str,
    version: str,
    metrics: list[FixtureMetrics],
    deterministic: bool,
    baseline_by_fixture: dict[str, FixtureMetrics] | None = None,
) -> ComponentSummary:
    deltas = (
        [metric.beat_f1 - baseline_by_fixture[metric.fixture_id].beat_f1 for metric in metrics]
        if baseline_by_fixture is not None
        else []
    )
    return ComponentSummary(
        source=source,
        version=version,
        available=True,
        deterministic=deterministic,
        fixture_count=len(metrics),
        mean_beat_f1=_mean(metric.beat_f1 for metric in metrics),
        mean_downbeat_f1=_mean(metric.downbeat_f1 for metric in metrics),
        mean_section_hit_rate_500ms=_mean(metric.section_hit_rate_500ms for metric in metrics),
        mean_section_hit_rate_3s=_mean(metric.section_hit_rate_3s for metric in metrics),
        worst_fixture_beat_delta=min(deltas) if deltas else None,
        fixtures=metrics,
    )


def _unavailable(source: str, version: str, limitation: str) -> ComponentSummary:
    return ComponentSummary(
        source=source,
        version=version,
        available=False,
        deterministic=False,
        fixture_count=0,
        mean_beat_f1=None,
        mean_downbeat_f1=None,
        mean_section_hit_rate_500ms=None,
        mean_section_hit_rate_3s=None,
        worst_fixture_beat_delta=None,
        limitation=limitation,
    )


def apply_adoption_gate(
    *,
    expected_fixture_ids: tuple[str, ...],
    dsp: ComponentSummary,
    beat_this: ComponentSummary | None,
    allinone: ComponentSummary | None,
) -> AdoptionDecision:
    """Apply the immutable numeric criteria from the accepted task specification."""
    epsilon = 1e-12

    def has_exact_manifest_identity(summary: ComponentSummary) -> bool:
        actual = [metric.fixture_id for metric in summary.fixtures]
        return (
            len(expected_fixture_ids) == 5
            and len(set(expected_fixture_ids)) == 5
            and len(actual) == 5
            and len(set(actual)) == 5
            and set(actual) == set(expected_fixture_ids)
            and summary.fixture_count == len(actual)
        )

    dsp_complete = has_exact_manifest_identity(dsp)
    beat_this_complete = beat_this is not None and has_exact_manifest_identity(beat_this)
    allinone_complete = allinone is not None and has_exact_manifest_identity(allinone)
    rhythm: Literal["adopt", "reject"]
    structure: Literal["adopt", "reject"]

    if not dsp_complete:
        rhythm = "reject"
        rhythm_reason = "DSP result does not match the exact five-fixture identity from manifest"
    elif beat_this is None or not beat_this.available:
        rhythm = "reject"
        rhythm_reason = "beat-this did not produce a complete five-fixture result"
    elif not beat_this_complete:
        rhythm = "reject"
        rhythm_reason = (
            "beat-this result does not match the exact five-fixture identity from manifest"
        )
    elif not beat_this.deterministic:
        rhythm = "reject"
        rhythm_reason = "beat-this failed the identical-two-run requirement"
    else:
        dsp_by_fixture = {metric.fixture_id: metric for metric in dsp.fixtures}
        beat_this_by_fixture = {metric.fixture_id: metric for metric in beat_this.fixtures}
        downbeat_gain = _mean(metric.downbeat_f1 for metric in beat_this.fixtures) - _mean(
            metric.downbeat_f1 for metric in dsp.fixtures
        )
        beat_delta = _mean(metric.beat_f1 for metric in beat_this.fixtures) - _mean(
            metric.beat_f1 for metric in dsp.fixtures
        )
        worst_fixture_beat_delta = min(
            beat_this_by_fixture[fixture_id].beat_f1 - dsp_by_fixture[fixture_id].beat_f1
            for fixture_id in expected_fixture_ids
        )
        single_fixture_ok = worst_fixture_beat_delta >= -0.02 - epsilon
        rhythm_wins = (
            downbeat_gain >= 0.05 - epsilon and beat_delta >= -0.02 - epsilon and single_fixture_ok
        )
        rhythm = "adopt" if rhythm_wins else "reject"
        rhythm_reason = (
            f"downbeat_gain={downbeat_gain:+.6f}; beat_delta={beat_delta:+.6f}; "
            f"worst_fixture_beat_delta={worst_fixture_beat_delta:+.6f}"
        )

    if not dsp_complete:
        structure = "reject"
        structure_reason = "DSP result does not match the exact five-fixture identity from manifest"
    elif allinone is None or not allinone.available:
        structure = "reject"
        structure_reason = "all-in-one-mlx did not produce a complete five-fixture result"
    elif not allinone_complete:
        structure = "reject"
        structure_reason = (
            "all-in-one result does not match the exact five-fixture identity from manifest"
        )
    elif not allinone.deterministic:
        structure = "reject"
        structure_reason = "all-in-one-mlx failed the identical-two-run requirement"
    else:
        gain = _mean(metric.section_hit_rate_500ms for metric in allinone.fixtures) - _mean(
            metric.section_hit_rate_500ms for metric in dsp.fixtures
        )
        structure = "adopt" if gain >= 0.10 - epsilon else "reject"
        structure_reason = f"strict_section_boundary_gain={gain:+.6f}"

    return AdoptionDecision(
        rhythm=rhythm,
        structure=structure,
        rhythm_reason=rhythm_reason,
        structure_reason=structure_reason,
    )


def _prepare_input(
    fixture: MIRFixture, *, sample_rate: int, audio_path: Path, hop_length: int
) -> MIRInput:
    audio = synthesize_fixture(fixture, sample_rate=sample_rate)
    sf.write(audio_path, audio, sample_rate, subtype="FLOAT")
    hpss = compute_hpss(audio)
    onset = compute_onset_env(hpss.percussive, sample_rate, hop_length=hop_length)
    chroma = extract_chroma(audio, sample_rate, hop_length=hop_length)
    return MIRInput(
        audio_path=audio_path,
        audio=audio,
        sample_rate=sample_rate,
        hop_length=hop_length,
        onset_envelope=onset,
        chroma=chroma,
        harmonic_audio=hpss.harmonic,
    )


def run_benchmark(manifest_path: Path, *, hop_length: int = 512) -> BenchmarkReport:
    """Run all available sources twice over every committed fixture."""
    manifest = load_fixture_manifest(manifest_path)
    dsp_source = DSPSource()
    beat_this_source = BeatThisSource()
    allinone_source = AllInOneSource()
    dsp_metrics: list[FixtureMetrics] = []
    beat_this_metrics: list[FixtureMetrics] = []
    allinone_metrics: list[FixtureMetrics] = []
    dsp_deterministic = True
    beat_this_deterministic = True
    allinone_deterministic = True
    beat_this_error: str | None = None
    allinone_error: str | None = None

    with tempfile.TemporaryDirectory(prefix="twinklr-mir-ab-") as temp_dir:
        root = Path(temp_dir)
        for fixture in manifest.fixtures:
            inputs = _prepare_input(
                fixture,
                sample_rate=manifest.sample_rate,
                audio_path=root / f"{fixture.id}.wav",
                hop_length=hop_length,
            )
            dsp_rhythm_first = dsp_source.analyze_rhythm(inputs)
            dsp_rhythm_second = dsp_source.analyze_rhythm(inputs)
            dsp_structure_first = dsp_source.analyze_structure(inputs, dsp_rhythm_first)
            dsp_structure_second = dsp_source.analyze_structure(inputs, dsp_rhythm_second)
            dsp_deterministic &= _same_rhythm(dsp_rhythm_first, dsp_rhythm_second)
            dsp_deterministic &= (
                dsp_structure_first.boundary_times_s == dsp_structure_second.boundary_times_s
                and dsp_structure_first.sections == dsp_structure_second.sections
            )
            dsp_metrics.append(
                _score(fixture, dsp_rhythm_first, dsp_structure_first.boundary_times_s)
            )

            if beat_this_error is None:
                try:
                    first = beat_this_source.analyze_rhythm(inputs)
                    second = beat_this_source.analyze_rhythm(inputs)
                    beat_this_deterministic &= _same_rhythm(first, second)
                    beat_this_metrics.append(
                        _score(fixture, first, dsp_structure_first.boundary_times_s)
                    )
                except (MissingMIRDependencyError, RuntimeError, ValueError) as error:
                    beat_this_error = f"{type(error).__name__}: {error}"
                    beat_this_metrics.clear()

            if allinone_error is None:
                try:
                    first_structure = allinone_source.analyze_structure(inputs, dsp_rhythm_first)
                    second_structure = allinone_source.analyze_structure(inputs, dsp_rhythm_first)
                    allinone_deterministic &= (
                        first_structure.boundary_times_s == second_structure.boundary_times_s
                        and first_structure.sections == second_structure.sections
                    )
                    allinone_metrics.append(
                        _score(fixture, dsp_rhythm_first, first_structure.boundary_times_s)
                    )
                except (MissingMIRDependencyError, RuntimeError, ValueError) as error:
                    allinone_error = f"{type(error).__name__}: {error}"
                    allinone_metrics.clear()

    dsp = _summary(
        source=dsp_source.name,
        version=dsp_source.version,
        metrics=dsp_metrics,
        deterministic=dsp_deterministic,
    )
    baseline_by_fixture = {metric.fixture_id: metric for metric in dsp_metrics}
    beat_this = (
        _unavailable(beat_this_source.name, beat_this_source.version, beat_this_error)
        if beat_this_error is not None
        else _summary(
            source=beat_this_source.name,
            version=beat_this_source.version,
            metrics=beat_this_metrics,
            deterministic=beat_this_deterministic,
            baseline_by_fixture=baseline_by_fixture,
        )
    )
    allinone = (
        _unavailable(allinone_source.name, allinone_source.version, allinone_error)
        if allinone_error is not None
        else _summary(
            source=allinone_source.name,
            version=allinone_source.version,
            metrics=allinone_metrics,
            deterministic=allinone_deterministic,
            baseline_by_fixture=baseline_by_fixture,
        )
    )
    return BenchmarkReport(
        fixture_manifest=str(manifest_path),
        fixture_count=len(manifest.fixtures),
        tolerances_s={
            "beat_f1": BEAT_TOLERANCE_S,
            "downbeat_f1": BEAT_TOLERANCE_S,
            "section_boundary_strict": SECTION_TOLERANCE_S,
            "section_boundary_loose": SECTION_LOOSE_TOLERANCE_S,
        },
        dsp=dsp,
        beat_this=beat_this,
        allinone=allinone,
        decision=apply_adoption_gate(
            expected_fixture_ids=tuple(fixture.id for fixture in manifest.fixtures),
            dsp=dsp,
            beat_this=beat_this,
            allinone=allinone,
        ),
    )


def _default_manifest() -> Path:
    return Path("tests/fixtures/mir/manifest.json")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. No network or paid service is used by the harness itself."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=_default_manifest())
    parser.add_argument("--hop-length", type=int, default=512)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", action="store_true", help="Print the JSON report")
    args = parser.parse_args(argv)

    report = run_benchmark(args.manifest, hop_length=args.hop_length)
    payload = report.model_dump_json(indent=2)
    if args.output is not None:
        args.output.write_text(payload + "\n", encoding="utf-8")
    if args.report or args.output is None:
        sys.stdout.write(payload + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
