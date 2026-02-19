from __future__ import annotations

from twinklr.core.feature_engineering.models import (
    AlignedEffectEvent,
    AlignmentStatus,
    EnergyClass,
    PhraseSource,
)
from twinklr.core.feature_engineering.phrase_encoder import PhraseEncoder


def _aligned(
    effect_event_id: str,
    effect_type: str,
    *,
    duration_ms: int = 1000,
    onset_sync_score: float | None = None,
    energy_at_onset: float | None = None,
) -> AlignedEffectEvent:
    return AlignedEffectEvent(
        schema_version="v1.1.0",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=effect_event_id,
        target_name="Tree",
        layer_index=0,
        effect_type=effect_type,
        start_ms=0,
        end_ms=duration_ms,
        duration_ms=duration_ms,
        start_s=0.0,
        end_s=float(duration_ms) / 1000.0,
        onset_sync_score=onset_sync_score,
        energy_at_onset=energy_at_onset,
        alignment_status=AlignmentStatus.ALIGNED,
    )


def test_phrase_encoder_maps_known_effect_types() -> None:
    encoder = PhraseEncoder()
    phrases = encoder.encode(
        package_id="pkg-1",
        sequence_file_id="seq-1",
        aligned_events=(_aligned("evt-1", "DMX"),),
        enriched_events=[
            {
                "effect_event_id": "evt-1",
                "config_fingerprint": "abc123",
            }
        ],
    )
    assert len(phrases) == 1
    phrase = phrases[0]
    assert phrase.effect_family == "dmx"
    assert phrase.source is PhraseSource.EFFECT_TYPE_MAP
    assert phrase.param_signature


def test_phrase_encoder_maps_canonical_spaced_effect_name() -> None:
    encoder = PhraseEncoder()
    phrase = encoder.encode(
        package_id="pkg-1",
        sequence_file_id="seq-1",
        aligned_events=(_aligned("evt-1", "Color Wash"),),
        enriched_events=[{"effect_event_id": "evt-1", "config_fingerprint": "abc123"}],
    )[0]
    assert phrase.effect_family == "color_wash"
    assert phrase.source is PhraseSource.EFFECT_TYPE_MAP


def test_phrase_encoder_maps_alias_effect_name() -> None:
    encoder = PhraseEncoder()
    phrase = encoder.encode(
        package_id="pkg-1",
        sequence_file_id="seq-1",
        aligned_events=(_aligned("evt-1", "VU"),),
        enriched_events=[{"effect_event_id": "evt-1", "config_fingerprint": "abc123"}],
    )[0]
    assert phrase.effect_family == "vu_meter"
    assert phrase.source is PhraseSource.EFFECT_TYPE_MAP


def test_phrase_encoder_derives_energy_from_audio_features() -> None:
    encoder = PhraseEncoder()
    phrase = encoder.encode(
        package_id="pkg-1",
        sequence_file_id="seq-1",
        aligned_events=(
            _aligned(
                "evt-1",
                "Pinwheel",
                duration_ms=1000,
                onset_sync_score=0.9,
                energy_at_onset=0.91,
            ),
        ),
        enriched_events=[{"effect_event_id": "evt-1", "config_fingerprint": "abc123"}],
    )[0]
    assert phrase.energy_class is EnergyClass.BURST


def test_phrase_encoder_derives_energy_from_timing_without_audio_features() -> None:
    encoder = PhraseEncoder()
    phrase = encoder.encode(
        package_id="pkg-1",
        sequence_file_id="seq-1",
        aligned_events=(_aligned("evt-1", "Pinwheel", duration_ms=3200),),
        enriched_events=[{"effect_event_id": "evt-1", "config_fingerprint": "abc123"}],
    )[0]
    assert phrase.energy_class is EnergyClass.LOW


def test_phrase_encoder_default_map_covers_all_known_xlights_effects() -> None:
    encoder = PhraseEncoder()
    expected_keys = {
        "off",
        "on",
        "adjust",
        "bars",
        "butterfly",
        "candle",
        "circles",
        "colorwash",
        "curtain",
        "dmx",
        "duplicate",
        "faces",
        "fan",
        "fill",
        "fire",
        "fireworks",
        "galaxy",
        "garlands",
        "glediator",
        "guitar",
        "kaleidoscope",
        "life",
        "lightning",
        "lines",
        "liquid",
        "marquee",
        "meteors",
        "morph",
        "movinghead",
        "music",
        "piano",
        "pictures",
        "pinwheel",
        "plasma",
        "ripple",
        "servo",
        "shader",
        "shape",
        "shimmer",
        "shockwave",
        "singlestrand",
        "snowflakes",
        "snowstorm",
        "spirals",
        "spirograph",
        "state",
        "strobe",
        "tendrils",
        "text",
        "tree",
        "twinkle",
        "video",
        "vumeter",
        "warp",
        "wave",
    }

    missing = expected_keys - set(encoder._map)
    assert not missing


def test_param_signature_deterministic_when_param_order_changes() -> None:
    encoder = PhraseEncoder()
    aligned = (_aligned("evt-1", "On"),)
    left = encoder.encode(
        package_id="pkg-1",
        sequence_file_id="seq-1",
        aligned_events=aligned,
        enriched_events=[
            {
                "effect_event_id": "evt-1",
                "effectdb_params": [
                    {
                        "namespace": "E",
                        "param_name_normalized": "speed",
                        "value_type": "int",
                        "value_int": 10,
                    },
                    {
                        "namespace": "E",
                        "param_name_normalized": "width",
                        "value_type": "int",
                        "value_int": 20,
                    },
                ],
            }
        ],
    )[0]
    right = encoder.encode(
        package_id="pkg-1",
        sequence_file_id="seq-1",
        aligned_events=aligned,
        enriched_events=[
            {
                "effect_event_id": "evt-1",
                "effectdb_params": [
                    {
                        "namespace": "E",
                        "param_name_normalized": "width",
                        "value_type": "int",
                        "value_int": 20,
                    },
                    {
                        "namespace": "E",
                        "param_name_normalized": "speed",
                        "value_type": "int",
                        "value_int": 10,
                    },
                ],
            }
        ],
    )[0]

    assert left.param_signature == right.param_signature
