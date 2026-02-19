from __future__ import annotations

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

