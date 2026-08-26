"""P3-T6 contract tests for the renderer-neutral xLights emission seam."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from twinklr.core.formats.xlights.sequence.emission import (
    EmissionRequest,
    EmissionSession,
)
from twinklr.core.formats.xlights.sequence.exporter import XSQExporter
from twinklr.core.formats.xlights.sequence.fresh import SEQUENCE_TIMING, build_fresh_sequence
from twinklr.core.formats.xlights.sequence.models.xsq import Effect
from twinklr.core.formats.xlights.sequence.parser import XSQParser
from twinklr.core.formats.xlights.sequence.trace import DisplayEmissionTrace


def _request(
    *,
    target: str = "Mega Tree",
    settings: str = "E_SLIDER_Speed=50",
    start_ms: int = 11,
    end_ms: int = 29,
    logical_layer: int = 0,
) -> EmissionRequest:
    return EmissionRequest(
        target=target,
        effect="Color Wash",
        settings=settings,
        palette="C_BUTTON_Palette1=#FF0000",
        start_ms=start_ms,
        end_ms=end_ms,
        logical_layer=logical_layer,
        trace=DisplayEmissionTrace(
            backend="display",
            event_id="event-1",
            section_id="chorus",
            lane="BASE",
            group_id="TREE",
            template_id="wash",
        ),
    )


def test_session_seeds_deduplicates_quantizes_and_places_above_occupied_layers() -> None:
    sequence = build_fresh_sequence(media_file="song.wav", duration_ms=1_000)
    sequence.effect_db.entries = ["", "EXISTING"]
    sequence.add_effect(
        "Mega Tree",
        Effect(effect_type="On", start_time_ms=0, end_time_ms=100, ref=1, palette="0"),
        layer_index=2,
    )
    original = sequence.get_element("Mega Tree").model_copy(deep=True)  # type: ignore[union-attr]

    session = EmissionSession(sequence)
    first = session.emit(_request())
    second = session.emit(_request(start_ms=31, end_ms=51))

    assert sequence.effect_db.entries[:2] == ["", "EXISTING"]
    assert first.ref == second.ref == 2
    assert first.file_layer == second.file_layer == 3
    assert first.live_layer == second.live_layer == 99
    assert (first.start_ms, first.end_ms) == (20, 40)
    assert (second.start_ms, second.end_ms) == (40, 60)
    assert sequence.get_element("Mega Tree").layers[:3] == original.layers  # type: ignore[union-attr]
    assert sequence.head.sequence_timing == SEQUENCE_TIMING == "20 ms"


def test_short_positive_duration_remains_positive_and_palette_zero_is_explicit(tmp_path) -> None:
    sequence = build_fresh_sequence(media_file="song.wav", duration_ms=1_000)
    record = EmissionSession(sequence).emit(_request(start_ms=20, end_ms=21))
    assert record.end_ms - record.start_ms == 20
    assert record.palette_ref == 0

    path = tmp_path / "palette-zero.xsq"
    XSQExporter().export(sequence, path)
    effect = ET.parse(path).getroot().find("ElementEffects/Element/EffectLayer/Effect")
    assert effect is not None
    assert effect.get("palette") == "0"


def test_trace_v2_carries_renderer_provenance_and_physical_topology() -> None:
    sequence = build_fresh_sequence(media_file="song.wav", duration_ms=1_000)
    record = EmissionSession(sequence).emit(_request())

    assert sequence.emission_trace_entries == [record.trace]
    assert record.trace["backend"] == "display"
    assert record.trace["event_id"] == "event-1"
    assert record.trace["logical_layer"] == 0
    assert record.trace["file_layer"] == 0
    assert record.trace["live_layer"] == 99
    assert record.live_payload == {
        "target": "Mega Tree",
        "effect": "Color Wash",
        "settings": sequence.effect_db.entries[record.ref],
        "palette": sequence.color_palettes[record.palette_ref].settings,  # type: ignore[index]
        "layer": 99,
        "start_ms": 20,
        "end_ms": 40,
    }


def test_quantized_batch_preserves_adjacent_order_without_overlap() -> None:
    sequence = build_fresh_sequence(media_file="song.wav", duration_ms=1_000)
    records = EmissionSession(sequence).emit_batch(
        (
            _request(start_ms=1, end_ms=29),
            _request(start_ms=31, end_ms=59),
        )
    )
    assert [(row.start_ms, row.end_ms) for row in records] == [(0, 20), (40, 60)]


def test_subgrid_batch_fails_closed_when_positive_repairs_would_overlap() -> None:
    sequence = build_fresh_sequence(media_file="song.wav", duration_ms=1_000)
    with pytest.raises(ValueError, match="quantization creates an overlap"):
        EmissionSession(sequence).emit_batch(
            (
                _request(start_ms=0, end_ms=1),
                _request(start_ms=1, end_ms=2),
            )
        )
    assert sequence.element_effects == []


def test_overlapping_transition_is_allowed_on_a_distinct_logical_layer() -> None:
    sequence = build_fresh_sequence(media_file="song.wav", duration_ms=1_000)
    records = EmissionSession(sequence).emit_batch(
        (
            _request(start_ms=0, end_ms=100, logical_layer=0),
            _request(start_ms=40, end_ms=60, logical_layer=1),
        )
    )
    assert [row.file_layer for row in records] == [0, 1]


def test_parsed_user_sequence_is_rejected_by_fresh_only_emission(tmp_path) -> None:
    path = tmp_path / "user.xsq"
    XSQExporter().export(build_fresh_sequence(media_file="song.wav", duration_ms=1_000), path)
    parsed = XSQParser().parse(path)
    with pytest.raises(ValueError, match="fresh-only"):
        EmissionSession(parsed)


def test_emission_rejects_noncanonical_timing_header() -> None:
    sequence = build_fresh_sequence(media_file="song.wav", duration_ms=1_000)
    sequence.head.sequence_timing = "50 ms"
    with pytest.raises(ValueError, match="20 ms"):
        EmissionSession(sequence)


def test_fresh_builder_has_no_timing_override() -> None:
    with pytest.raises(TypeError, match="sequence_timing"):
        build_fresh_sequence(  # type: ignore[call-arg]
            media_file="song.wav",
            duration_ms=1_000,
            sequence_timing="50 ms",
        )


def test_seeded_nonempty_effectdb_zero_fails_without_shifting() -> None:
    sequence = build_fresh_sequence(media_file="song.wav", duration_ms=1_000)
    sequence.effect_db.entries = ["USER_SETTINGS"]
    before = sequence.model_copy(deep=True)
    with pytest.raises(ValueError, match="EffectDB index 0"):
        EmissionSession(sequence)
    assert sequence == before
