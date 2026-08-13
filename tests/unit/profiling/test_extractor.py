"""Unit tests for effect extraction."""

from __future__ import annotations

from twinklr.core.formats.xlights.sequence.models.xsq import (
    Effect,
    EffectDB,
    EffectLayer,
    ElementEffects,
    SequenceHead,
    XSequence,
)
from twinklr.core.profiling.effects.extractor import extract_effect_events
from twinklr.core.profiling.models.enums import EffectDbParseStatus


def _sequence_with_effects() -> XSequence:
    return XSequence(
        head=SequenceHead(
            version="2025.1",
            media_file="song.mp3",
            sequence_duration_ms=10_000,
        ),
        effect_db=EffectDB(entries=["E_TEXTCTRL_Eff_speed=10,E_CHECKBOX_Eff_Invert=0"]),
        element_effects=[
            ElementEffects(
                element_name="Arch 1",
                layers=[
                    EffectLayer(
                        index=0,
                        name="Main",
                        effects=[
                            Effect(
                                effect_type="Bars",
                                start_time_ms=100,
                                end_time_ms=200,
                                ref=0,
                                palette="#FF0000",
                                protected=False,
                                parameters={"Speed": "10"},
                            ),
                            Effect(
                                effect_type="Bars",
                                start_time_ms=300,
                                end_time_ms=500,
                                palette="#00FF00",
                                protected=True,
                                parameters={"Speed": "20"},
                            ),
                        ],
                    )
                ],
            ),
            ElementEffects(
                element_name="Tree",
                layers=[
                    EffectLayer(
                        index=1,
                        name="Accent",
                        effects=[
                            Effect(
                                effect_type="On",
                                start_time_ms=150,
                                end_time_ms=250,
                                palette="#0000FF",
                                protected=False,
                            )
                        ],
                    )
                ],
            ),
        ],
    )


def test_extract_effect_events_empty_sequence() -> None:
    sequence = XSequence(
        head=SequenceHead(version="2025.1", media_file="song.mp3", sequence_duration_ms=10_000)
    )
    result = extract_effect_events(sequence, "pkg", "seq", "sha")
    assert result.package_id == "pkg"
    assert result.sequence_file_id == "seq"
    assert len(result.events) == 0


def test_extract_effect_events_fields_and_sorting() -> None:
    result = extract_effect_events(_sequence_with_effects(), "pkg", "seq", "sha")
    assert len(result.events) == 3
    assert result.events[0].start_ms == 100
    assert result.events[1].start_ms == 150
    assert result.events[2].start_ms == 300
    assert result.events[0].target_name == "Arch 1"
    assert result.events[1].target_name == "Tree"


def test_extract_effect_events_effectdb_resolution() -> None:
    result = extract_effect_events(_sequence_with_effects(), "pkg", "seq", "sha")
    first = result.events[0]
    assert first.effectdb_ref == 0
    assert first.effectdb_settings_raw is not None
    assert "E_TEXTCTRL_Eff_speed=10" in first.effectdb_settings_raw
    assert first.effectdb_parse_status is EffectDbParseStatus.PARSED
    assert any(param.param_name_normalized == "eff_speed" for param in first.effectdb_params)


# ---------------------------------------------------------------------------
# Content-hash identity (P1K-T1)
# ---------------------------------------------------------------------------


def _sequence_with_identical_effects() -> XSequence:
    """Two effects sharing start/end/layer/target/type/config in one layer."""
    duplicate = Effect(
        effect_type="Bars",
        start_time_ms=100,
        end_time_ms=200,
        palette="#FF0000",
        protected=False,
        parameters={"Speed": "10"},
    )
    return XSequence(
        head=SequenceHead(
            version="2025.1",
            media_file="song.mp3",
            sequence_duration_ms=10_000,
        ),
        element_effects=[
            ElementEffects(
                element_name="Arch 1",
                layers=[
                    EffectLayer(
                        index=0,
                        name="Main",
                        effects=[duplicate, duplicate.model_copy()],
                    )
                ],
            )
        ],
    )


def test_effect_event_id_is_deterministic() -> None:
    sequence = _sequence_with_effects()

    first = extract_effect_events(sequence, "pkg", "seq", "sha")
    second = extract_effect_events(sequence, "pkg", "seq", "sha")

    ids = tuple(event.effect_event_id for event in first.events)
    assert ids == tuple(event.effect_event_id for event in second.events)
    assert len(set(ids)) == len(ids)


def test_effect_event_id_depends_on_package_identity() -> None:
    sequence = _sequence_with_effects()

    first = extract_effect_events(sequence, "pkg-a", "seq", "sha")
    second = extract_effect_events(sequence, "pkg-b", "seq", "sha")

    assert all(
        a.effect_event_id != b.effect_event_id
        for a, b in zip(first.events, second.events, strict=True)
    )


def test_duplicate_effect_signature_gets_distinct_ids() -> None:
    result = extract_effect_events(_sequence_with_identical_effects(), "pkg", "seq", "sha")

    ids = [event.effect_event_id for event in result.events]
    assert len(ids) == 2
    assert len(set(ids)) == 2

    # Still deterministic across runs despite the dup_index disambiguator.
    repeat = extract_effect_events(_sequence_with_identical_effects(), "pkg", "seq", "sha")
    assert sorted(ids) == sorted(event.effect_event_id for event in repeat.events)
