"""Deterministic layering feature extraction (V1.7)."""

from __future__ import annotations

from collections import defaultdict

from twinklr.core.feature_engineering.models import EffectPhrase
from twinklr.core.feature_engineering.models.layering import LayeringFeatureRow, TargetLayerProfile


class LayeringFeatureExtractor:
    """Compute sequence-level layering/concurrency/collision metrics."""

    def extract(self, phrases: tuple[EffectPhrase, ...]) -> tuple[LayeringFeatureRow, ...]:
        grouped: dict[tuple[str, str], list[EffectPhrase]] = defaultdict(list)
        for phrase in phrases:
            grouped[(phrase.package_id, phrase.sequence_file_id)].append(phrase)

        rows: list[LayeringFeatureRow] = []
        for (package_id, sequence_file_id), seq_rows in sorted(grouped.items()):
            ordered = sorted(seq_rows, key=lambda row: (row.start_ms, row.end_ms, row.phrase_id))
            max_concurrency, mean_concurrency = self._concurrency(ordered)
            hierarchy_transitions = self._hierarchy_transitions(ordered)
            overlap_pairs, same_target_overlap_pairs = self._overlap_pairs(ordered)
            collision_score = (
                round(same_target_overlap_pairs / overlap_pairs, 6) if overlap_pairs > 0 else 0.0
            )
            target_profiles = self._target_layer_profiles(ordered)
            rows.append(
                LayeringFeatureRow(
                    schema_version="v1.8.0",
                    package_id=package_id,
                    sequence_file_id=sequence_file_id,
                    phrase_count=len(ordered),
                    max_concurrent_layers=max_concurrency,
                    mean_concurrent_layers=mean_concurrency,
                    hierarchy_transitions=hierarchy_transitions,
                    overlap_pairs=overlap_pairs,
                    same_target_overlap_pairs=same_target_overlap_pairs,
                    collision_score=collision_score,
                    target_layer_profiles=target_profiles,
                )
            )
        return tuple(rows)

    @staticmethod
    def _concurrency(rows: list[EffectPhrase]) -> tuple[int, float]:
        if not rows:
            return 0, 0.0
        points: list[tuple[int, int]] = []
        for row in rows:
            points.append((row.start_ms, 1))
            points.append((row.end_ms, -1))
        points.sort(key=lambda item: (item[0], item[1]))

        active = 0
        max_active = 0
        sampled: list[int] = []
        for _, delta in points:
            active += delta
            max_active = max(max_active, active)
            sampled.append(max(active, 0))
        mean_active = round(sum(sampled) / len(sampled), 6)
        return max_active, mean_active

    @staticmethod
    def _hierarchy_transitions(rows: list[EffectPhrase]) -> int:
        if not rows:
            return 0
        transitions = 0
        previous = rows[0].layer_index
        for row in rows[1:]:
            if row.layer_index != previous:
                transitions += 1
            previous = row.layer_index
        return transitions

    def _target_layer_profiles(self, rows: list[EffectPhrase]) -> tuple[TargetLayerProfile, ...]:
        """Compute per-target layering profiles."""
        by_target: dict[str, list[EffectPhrase]] = defaultdict(list)
        for row in rows:
            by_target[row.target_name].append(row)

        profiles: list[TargetLayerProfile] = []
        for target_name in sorted(by_target):
            target_rows = sorted(by_target[target_name], key=lambda r: (r.start_ms, r.end_ms))
            max_c, mean_c = self._concurrency(target_rows)

            layer_counts: dict[int, int] = defaultdict(int)
            for row in target_rows:
                layer_counts[row.layer_index] += 1
            distinct_layers = len(layer_counts)
            dominant_count = max(distinct_layers, 1)

            profiles.append(
                TargetLayerProfile(
                    target_name=target_name,
                    phrase_count=len(target_rows),
                    max_concurrent_layers=max_c,
                    mean_concurrent_layers=mean_c,
                    dominant_layer_count=dominant_count,
                )
            )
        return tuple(profiles)

    @staticmethod
    def _overlap_pairs(rows: list[EffectPhrase]) -> tuple[int, int]:
        overlap_pairs = 0
        same_target_pairs = 0
        for idx, left in enumerate(rows):
            for right in rows[idx + 1 :]:
                if right.start_ms >= left.end_ms:
                    break
                if left.start_ms < right.end_ms and right.start_ms < left.end_ms:
                    overlap_pairs += 1
                    if left.target_name == right.target_name:
                        same_target_pairs += 1
        return overlap_pairs, same_target_pairs
