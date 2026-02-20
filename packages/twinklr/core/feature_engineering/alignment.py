"""Temporal alignment engine for V1.1."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from typing import Any

import numpy as np

from twinklr.core.feature_engineering.constants import ALIGNED_EVENTS_SCHEMA_VERSION
from twinklr.core.feature_engineering.models import AlignedEffectEvent, AlignmentStatus


@dataclass(frozen=True)
class TemporalAlignmentOptions:
    """Runtime options for alignment computation."""

    beats_per_bar_default: int = 4


class TemporalAlignmentEngine:
    """Align profiling events to audio timing and context."""

    def __init__(self, options: TemporalAlignmentOptions | None = None) -> None:
        self._options = options or TemporalAlignmentOptions()

    def align_events(
        self,
        *,
        package_id: str,
        sequence_file_id: str,
        events: list[dict[str, Any]],
        audio_features: dict[str, Any] | None,
    ) -> tuple[AlignedEffectEvent, ...]:
        sorted_events = sorted(
            events,
            key=lambda e: (
                int(e.get("start_ms", 0)),
                int(e.get("end_ms", 0)),
                str(e.get("effect_event_id")),
            ),
        )

        if audio_features is None:
            return tuple(
                self._build_no_audio_row(package_id, sequence_file_id, event)
                for event in sorted_events
            )

        beats = np.asarray(audio_features.get("beats_s", []), dtype=float)
        assumptions = audio_features.get("assumptions", {})
        beats_per_bar = int(assumptions.get("beats_per_bar", self._options.beats_per_bar_default))

        energy = audio_features.get("energy", {})
        energy_times = np.asarray(energy.get("times_s", []), dtype=float)
        energy_values = np.asarray(energy.get("rms_norm", []), dtype=float)

        duration_s = float(audio_features.get("duration_s", 0.0))
        tension_curve = np.asarray(
            audio_features.get("tension", {}).get("tension_curve", []), dtype=float
        )
        tension_times = (
            np.linspace(0.0, duration_s, num=len(tension_curve), endpoint=False)
            if len(tension_curve) > 0 and duration_s > 0
            else np.asarray([], dtype=float)
        )

        sections = list(audio_features.get("structure", {}).get("sections", []))
        chords = self._extract_chords(audio_features)
        tempo_curve = list(audio_features.get("tempo_analysis", {}).get("tempo_curve", []))

        aligned: list[AlignedEffectEvent] = []
        prev_end_s = 0.0
        for event in sorted_events:
            start_ms = int(event.get("start_ms", 0))
            end_ms = int(event.get("end_ms", 0))
            start_s = max(0.0, start_ms / 1000.0)
            end_s = max(start_s, end_ms / 1000.0)

            if beats.size == 0:
                aligned.append(
                    self._build_row_no_beats(
                        package_id=package_id,
                        sequence_file_id=sequence_file_id,
                        event=event,
                        start_s=start_s,
                        end_s=end_s,
                    )
                )
                prev_end_s = max(prev_end_s, end_s)
                continue

            start_pos = self._beat_position(start_s, beats)
            end_pos = self._beat_position(end_s, beats)

            start_beat_index = int(np.floor(start_pos))
            end_beat_index = int(np.floor(end_pos))
            beat_phase = float(start_pos - np.floor(start_pos))
            bar_pos = start_pos / max(beats_per_bar, 1)
            bar_index = int(np.floor(bar_pos))
            bar_phase = float(bar_pos - np.floor(bar_pos))
            duration_beats = max(0.0, float(end_pos - start_pos))

            nearest_dist = self._nearest_beat_distance(start_s, beats)
            median_beat = float(np.median(np.diff(beats))) if beats.size >= 2 else 0.5
            onset_sync_score = float(np.exp(-nearest_dist / max(median_beat, 1e-6)))

            section_index, section_label = self._section_at_time(start_s, sections)
            local_tempo = self._tempo_at_time(start_s, tempo_curve)
            silence_before_s = max(0.0, start_s - prev_end_s)
            silence_before_beats = (
                silence_before_s * (local_tempo / 60.0) if local_tempo > 0.0 else 0.0
            )

            aligned.append(
                AlignedEffectEvent(
                    schema_version=ALIGNED_EVENTS_SCHEMA_VERSION,
                    package_id=package_id,
                    sequence_file_id=sequence_file_id,
                    effect_event_id=str(event.get("effect_event_id")),
                    target_name=str(event.get("target_name", "")),
                    layer_index=int(event.get("layer_index", 0)),
                    effect_type=str(event.get("effect_type", "")),
                    start_ms=start_ms,
                    end_ms=end_ms,
                    duration_ms=max(0, end_ms - start_ms),
                    start_s=start_s,
                    end_s=end_s,
                    start_beat_index=start_beat_index,
                    end_beat_index=end_beat_index,
                    beat_phase=min(max(beat_phase, 0.0), 1.0),
                    bar_index=bar_index,
                    bar_phase=min(max(bar_phase, 0.0), 1.0),
                    duration_beats=duration_beats,
                    section_index=section_index,
                    section_label=section_label,
                    local_tempo_bpm=local_tempo if local_tempo > 0.0 else None,
                    onset_sync_score=min(max(onset_sync_score, 0.0), 1.0),
                    silence_before_beats=silence_before_beats,
                    energy_at_onset=self._interp_at(start_s, energy_times, energy_values),
                    tension_at_onset=self._interp_at(start_s, tension_times, tension_curve),
                    chord_at_onset=self._chord_at_time(start_s, chords),
                    alignment_status=AlignmentStatus.ALIGNED,
                )
            )
            prev_end_s = max(prev_end_s, end_s)

        return tuple(aligned)

    @staticmethod
    def _extract_chords(features: dict[str, Any]) -> list[dict[str, Any]]:
        harmonic = features.get("harmonic", {})
        chords_obj = harmonic.get("chords", {})
        if isinstance(chords_obj, dict):
            return [c for c in chords_obj.get("chords", []) if isinstance(c, dict)]
        return (
            [c for c in chords_obj if isinstance(c, dict)] if isinstance(chords_obj, list) else []
        )

    @staticmethod
    def _tempo_at_time(time_s: float, tempo_curve: list[dict[str, Any]]) -> float:
        if not tempo_curve:
            return 0.0
        times = [float(row.get("time_s", 0.0)) for row in tempo_curve]
        idx = max(0, bisect_right(times, time_s) - 1)
        return float(tempo_curve[idx].get("tempo_bpm", 0.0))

    @staticmethod
    def _nearest_beat_distance(time_s: float, beats: np.ndarray) -> float:
        idx = int(np.searchsorted(beats, time_s, side="left"))
        if idx <= 0:
            return abs(float(beats[0] - time_s))
        if idx >= len(beats):
            return abs(float(time_s - beats[-1]))
        return min(abs(float(time_s - beats[idx - 1])), abs(float(beats[idx] - time_s)))

    @staticmethod
    def _beat_position(time_s: float, beats: np.ndarray) -> float:
        if beats.size == 0:
            return 0.0
        if time_s <= float(beats[0]):
            lead = max(float(beats[1] - beats[0]), 1e-6) if beats.size > 1 else 0.5
            return (time_s - float(beats[0])) / lead
        idx = int(np.searchsorted(beats, time_s, side="right")) - 1
        idx = min(max(idx, 0), len(beats) - 1)
        if idx >= len(beats) - 1:
            tail = max(float(beats[-1] - beats[-2]), 1e-6) if len(beats) > 1 else 0.5
            return float(len(beats) - 1) + (time_s - float(beats[-1])) / tail
        left = float(beats[idx])
        right = float(beats[idx + 1])
        frac = (time_s - left) / max(right - left, 1e-6)
        return float(idx) + float(frac)

    @staticmethod
    def _section_at_time(
        time_s: float, sections: list[dict[str, Any]]
    ) -> tuple[int | None, str | None]:
        for idx, section in enumerate(sections):
            start_s = float(section.get("start_s", 0.0))
            end_s = float(section.get("end_s", start_s))
            if start_s <= time_s < end_s:
                label = section.get("label")
                return idx, str(label) if label is not None else None
        return None, None

    @staticmethod
    def _interp_at(time_s: float, times: np.ndarray, values: np.ndarray) -> float | None:
        if times.size == 0 or values.size == 0 or times.size != values.size:
            return None
        if time_s <= float(times[0]):
            return float(values[0])
        if time_s >= float(times[-1]):
            return float(values[-1])
        return float(np.interp(time_s, times, values))

    @staticmethod
    def _chord_at_time(time_s: float, chords: list[dict[str, Any]]) -> str | None:
        if not chords:
            return None
        chord_time_pairs = sorted(
            ((float(ch.get("time_s", 0.0)), str(ch.get("chord", ""))) for ch in chords),
            key=lambda x: x[0],
        )
        idx = bisect_right([pair[0] for pair in chord_time_pairs], time_s) - 1
        if idx < 0:
            return chord_time_pairs[0][1] or None
        return chord_time_pairs[idx][1] or None

    @staticmethod
    def _build_no_audio_row(
        package_id: str, sequence_file_id: str, event: dict[str, Any]
    ) -> AlignedEffectEvent:
        start_ms = int(event.get("start_ms", 0))
        end_ms = int(event.get("end_ms", 0))
        return AlignedEffectEvent(
            schema_version=ALIGNED_EVENTS_SCHEMA_VERSION,
            package_id=package_id,
            sequence_file_id=sequence_file_id,
            effect_event_id=str(event.get("effect_event_id")),
            target_name=str(event.get("target_name", "")),
            layer_index=int(event.get("layer_index", 0)),
            effect_type=str(event.get("effect_type", "")),
            start_ms=start_ms,
            end_ms=end_ms,
            duration_ms=max(0, end_ms - start_ms),
            start_s=max(0.0, start_ms / 1000.0),
            end_s=max(0.0, end_ms / 1000.0),
            alignment_status=AlignmentStatus.NO_AUDIO,
        )

    def _build_row_no_beats(
        self,
        *,
        package_id: str,
        sequence_file_id: str,
        event: dict[str, Any],
        start_s: float,
        end_s: float,
    ) -> AlignedEffectEvent:
        start_ms = int(event.get("start_ms", 0))
        end_ms = int(event.get("end_ms", 0))
        return AlignedEffectEvent(
            schema_version=ALIGNED_EVENTS_SCHEMA_VERSION,
            package_id=package_id,
            sequence_file_id=sequence_file_id,
            effect_event_id=str(event.get("effect_event_id")),
            target_name=str(event.get("target_name", "")),
            layer_index=int(event.get("layer_index", 0)),
            effect_type=str(event.get("effect_type", "")),
            start_ms=start_ms,
            end_ms=end_ms,
            duration_ms=max(0, end_ms - start_ms),
            start_s=start_s,
            end_s=end_s,
            alignment_status=AlignmentStatus.NO_BEATS,
        )
