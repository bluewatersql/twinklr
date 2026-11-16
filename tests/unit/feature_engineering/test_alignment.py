from __future__ import annotations

import pytest

from twinklr.core.audio.rhythm.tempo import local_tempo_curve
from twinklr.core.feature_engineering.alignment import TemporalAlignmentEngine
from twinklr.core.feature_engineering.models import AlignmentStatus


def test_alignment_maps_event_to_beat_bar_section_context() -> None:
    engine = TemporalAlignmentEngine()
    events = [
        {
            "effect_event_id": "evt-1",
            "target_name": "Tree",
            "layer_index": 0,
            "effect_type": "On",
            "start_ms": 600,
            "end_ms": 1600,
        }
    ]
    features = {
        "duration_s": 10.0,
        "assumptions": {"beats_per_bar": 4},
        "beats_s": [0.0, 0.5, 1.0, 1.5, 2.0],
        "bars_s": [0.0, 2.0],
        "energy": {"times_s": [0.0, 2.0], "rms_norm": [0.2, 0.8]},
        "tempo_analysis": {"tempo_curve": [{"time_s": 0.0, "tempo_bpm": 120.0}]},
        "tension": {"tension_curve": [0.2, 0.4, 0.6, 0.8]},
        "structure": {
            "sections": [
                {"start_s": 0.0, "end_s": 1.0, "label": "intro"},
                {"start_s": 1.0, "end_s": 10.0, "label": "verse"},
            ]
        },
        "harmonic": {
            "chords": {
                "chords": [
                    {"time_s": 0.0, "chord": "C:maj"},
                    {"time_s": 1.0, "chord": "G:maj"},
                ]
            }
        },
    }
    rows = engine.align_events(
        package_id="pkg-1",
        sequence_file_id="seq-1",
        events=events,
        audio_features=features,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.alignment_status is AlignmentStatus.ALIGNED
    assert row.start_beat_index == 1
    assert row.bar_index == 0
    assert row.section_label == "intro"
    assert row.duration_beats is not None and row.duration_beats > 1.0
    assert row.energy_at_onset is not None
    assert row.tension_at_onset is not None
    assert row.chord_at_onset == "C:maj"


def test_alignment_marks_no_audio_when_features_missing() -> None:
    engine = TemporalAlignmentEngine()
    rows = engine.align_events(
        package_id="pkg-1",
        sequence_file_id="seq-1",
        events=[
            {
                "effect_event_id": "evt-1",
                "target_name": "Tree",
                "layer_index": 0,
                "effect_type": "On",
                "start_ms": 0,
                "end_ms": 100,
            }
        ],
        audio_features=None,
    )

    assert len(rows) == 1
    assert rows[0].alignment_status is AlignmentStatus.NO_AUDIO


def test_alignment_beat_counts_follow_a_halved_grid() -> None:
    """Local tempo and beat positions agree when the grid was halved to 78.3 BPM."""
    beat_s = 60.0 / 78.3
    beats = [0.25 + i * beat_s for i in range(150)]
    features = {
        "duration_s": 120.0,
        "assumptions": {"beats_per_bar": 4},
        "beats_s": beats,
        "bars_s": beats[::4],
        "tempo_analysis": local_tempo_curve(beats, duration_s=120.0),
    }
    events = [
        {
            "effect_event_id": "evt-1",
            "target_name": "Tree",
            "layer_index": 0,
            "effect_type": "On",
            "start_ms": round(beats[8] * 1000) + 1,
            "end_ms": round(beats[12] * 1000),
        },
        {
            "effect_event_id": "evt-2",
            "target_name": "Tree",
            "layer_index": 0,
            "effect_type": "On",
            "start_ms": round(beats[14] * 1000) + 1,
            "end_ms": round(beats[16] * 1000),
        },
    ]

    first, second = TemporalAlignmentEngine().align_events(
        package_id="pkg-1",
        sequence_file_id="seq-1",
        events=events,
        audio_features=features,
    )

    assert first.start_beat_index == 8
    assert first.bar_index == 2
    assert first.duration_beats == pytest.approx(4.0, abs=0.01)
    assert second.local_tempo_bpm == pytest.approx(78.3, rel=0.01)
    assert second.silence_before_beats == pytest.approx(2.0, abs=0.02)
