"""Deterministic motif mining over phrase windows (V2.0 baseline)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass

from twinklr.core.feature_engineering.models.motifs import (
    MinedMotif,
    MotifCatalog,
    MotifOccurrence,
)
from twinklr.core.feature_engineering.models.phrases import EffectPhrase
from twinklr.core.feature_engineering.models.taxonomy import PhraseTaxonomyRecord
from twinklr.core.feature_engineering.models.templates import TemplateCatalog
from twinklr.core.feature_engineering.models.temporal_motifs import (
    TemporalMotif,
    TemporalMotifCatalog,
    TemporalMotifStep,
)


@dataclass(frozen=True)
class MotifMinerOptions:
    schema_version: str = "v2.0.0"
    miner_version: str = "motif_miner_v1"
    min_support_count: int = 2
    min_distinct_pack_count: int = 1
    min_distinct_sequence_count: int = 2
    max_occurrences_per_motif: int = 50


class MotifMiner:
    """Mine recurring phrase motifs in 1-8 bar windows."""

    def __init__(self, options: MotifMinerOptions | None = None) -> None:
        self._options = options or MotifMinerOptions()

    def mine(
        self,
        *,
        phrases: tuple[EffectPhrase, ...],
        taxonomy_rows: tuple[PhraseTaxonomyRecord, ...],
        content_catalog: TemplateCatalog,
        orchestration_catalog: TemplateCatalog,
    ) -> MotifCatalog:
        taxonomy_by_phrase = {row.phrase_id: row for row in taxonomy_rows}
        template_by_phrase: dict[str, str] = {}
        for assignment in content_catalog.assignments:
            template_by_phrase[assignment.phrase_id] = assignment.template_id
        for assignment in orchestration_catalog.assignments:
            template_by_phrase[assignment.phrase_id] = assignment.template_id

        by_sequence: dict[tuple[str, str], list[EffectPhrase]] = defaultdict(list)
        for phrase in phrases:
            by_sequence[(phrase.package_id, phrase.sequence_file_id)].append(phrase)

        signatures: dict[str, list[tuple[MotifOccurrence, set[str], set[str]]]] = defaultdict(list)
        for (package_id, sequence_file_id), rows in by_sequence.items():
            ordered = sorted(rows, key=lambda row: (row.start_ms, row.end_ms, row.phrase_id))
            if not ordered:
                continue

            bar_by_phrase: dict[str, int] = {}
            for phrase in ordered:
                if phrase.start_beat_index is not None and phrase.start_beat_index >= 0:
                    bar_index = phrase.start_beat_index // 4
                else:
                    bar_index = phrase.start_ms // 2000
                bar_by_phrase[phrase.phrase_id] = bar_index

            min_bar = min(bar_by_phrase.values())
            max_bar = max(bar_by_phrase.values())

            for bar_start in range(min_bar, max_bar + 1):
                for span in range(1, 9):
                    bar_end = bar_start + span
                    window = [
                        phrase
                        for phrase in ordered
                        if bar_start <= bar_by_phrase[phrase.phrase_id] < bar_end
                    ]
                    if len(window) < 2:
                        continue

                    signature, template_ids, labels = self._build_signature(
                        window=window,
                        span=span,
                        taxonomy_by_phrase=taxonomy_by_phrase,
                        template_by_phrase=template_by_phrase,
                    )
                    occurrence = MotifOccurrence(
                        package_id=package_id,
                        sequence_file_id=sequence_file_id,
                        start_bar_index=bar_start,
                        end_bar_index=bar_end,
                        start_ms=min(row.start_ms for row in window),
                        end_ms=max(row.end_ms for row in window),
                        phrase_count=len(window),
                    )
                    signatures[signature].append((occurrence, template_ids, labels))

        motifs: list[MinedMotif] = []
        for signature in sorted(signatures):
            sig_rows = signatures[signature]
            if len(sig_rows) < self._options.min_support_count:
                continue

            occurrences = [row[0] for row in sig_rows]
            motif_template_ids: list[str] = sorted({item for row in sig_rows for item in row[1]})
            motif_taxonomy_labels: list[str] = sorted({item for row in sig_rows for item in row[2]})
            distinct_packs = {(row.package_id) for row in occurrences}
            distinct_sequences = {(row.package_id, row.sequence_file_id) for row in occurrences}
            if len(distinct_packs) < self._options.min_distinct_pack_count:
                continue
            if len(distinct_sequences) < self._options.min_distinct_sequence_count:
                continue

            motif_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    f"{self._options.miner_version}:{signature}",
                )
            )
            bar_span = int(signature.split("|", 1)[0].replace("span=", ""))
            motifs.append(
                MinedMotif(
                    motif_id=motif_id,
                    motif_signature=signature,
                    bar_span=bar_span,
                    support_count=len(occurrences),
                    distinct_pack_count=len(distinct_packs),
                    distinct_sequence_count=len(distinct_sequences),
                    template_ids=tuple(motif_template_ids),
                    taxonomy_labels=tuple(motif_taxonomy_labels),
                    occurrences=tuple(
                        sorted(
                            occurrences,
                            key=lambda row: (
                                row.package_id,
                                row.sequence_file_id,
                                row.start_bar_index,
                                row.start_ms,
                            ),
                        )[: self._options.max_occurrences_per_motif]
                    ),
                )
            )

        motifs.sort(key=lambda row: row.motif_id)
        return MotifCatalog(
            schema_version=self._options.schema_version,
            miner_version=self._options.miner_version,
            total_sequences=len(by_sequence),
            total_motifs=len(motifs),
            min_support_count=self._options.min_support_count,
            min_distinct_pack_count=self._options.min_distinct_pack_count,
            min_distinct_sequence_count=self._options.min_distinct_sequence_count,
            motifs=tuple(motifs),
        )

    @staticmethod
    def _build_signature(
        *,
        window: list[EffectPhrase],
        span: int,
        taxonomy_by_phrase: dict[str, PhraseTaxonomyRecord],
        template_by_phrase: dict[str, str],
    ) -> tuple[str, set[str], set[str]]:
        token_rows = sorted(
            window,
            key=lambda row: (row.start_ms, row.layer_index, row.target_name, row.phrase_id),
        )
        tokens: list[str] = []
        template_ids: set[str] = set()
        taxonomy_labels: set[str] = set()

        for row in token_rows[:12]:
            tokens.append(
                ":".join(
                    (
                        row.effect_family,
                        row.motion_class.value,
                        row.energy_class.value,
                        row.continuity_class.value,
                    )
                )
            )
            template_id = template_by_phrase.get(row.phrase_id)
            if template_id is not None:
                template_ids.add(template_id)

            taxonomy = taxonomy_by_phrase.get(row.phrase_id)
            if taxonomy is not None:
                taxonomy_labels.update(label.value for label in taxonomy.labels)

        signature = "|".join((f"span={span}", ",".join(tokens)))
        return signature, template_ids, taxonomy_labels

    # ------------------------------------------------------------------
    # Temporal (ordered) motif mining — Spec 03
    # ------------------------------------------------------------------

    def mine_temporal(
        self,
        *,
        phrases: tuple[EffectPhrase, ...],
        content_catalog: TemplateCatalog,
        orchestration_catalog: TemplateCatalog,
    ) -> TemporalMotifCatalog:
        """Mine ordered n-gram motifs from per-target template streams."""
        template_by_phrase: dict[str, str] = {}
        for assignment in content_catalog.assignments:
            template_by_phrase[assignment.phrase_id] = assignment.template_id
        for assignment in orchestration_catalog.assignments:
            template_by_phrase[assignment.phrase_id] = assignment.template_id

        # Step 1: build per-target template streams keyed by
        # (package_id, sequence_file_id, target_name).
        stream_key = tuple[str, str, str]
        by_stream: dict[stream_key, list[EffectPhrase]] = defaultdict(list)
        for phrase in phrases:
            key: stream_key = (
                phrase.package_id,
                phrase.sequence_file_id,
                phrase.target_name,
            )
            by_stream[key].append(phrase)

        # Deduplicate sequences for counting.
        all_sequences: set[tuple[str, str]] = {
            (phrase.package_id, phrase.sequence_file_id) for phrase in phrases
        }

        # Step 2-3: extract n-grams and build temporal signatures.
        _SigData = tuple[
            MotifOccurrence,
            tuple[TemporalMotifStep, ...],
        ]
        signatures: dict[str, list[_SigData]] = defaultdict(list)

        for (pkg, seq, _target), stream_phrases in by_stream.items():
            ordered = sorted(
                stream_phrases,
                key=lambda p: (p.start_ms, p.phrase_id),
            )
            if len(ordered) < 2:
                continue

            for n in range(2, min(len(ordered) + 1, 6)):  # n=2..5
                for i in range(len(ordered) - n + 1):
                    window = ordered[i : i + n]
                    sig, steps = self._build_temporal_signature(
                        window=window,
                        template_by_phrase=template_by_phrase,
                    )
                    occ = MotifOccurrence(
                        package_id=pkg,
                        sequence_file_id=seq,
                        start_bar_index=0,
                        end_bar_index=0,
                        start_ms=window[0].start_ms,
                        end_ms=window[-1].end_ms,
                        phrase_count=len(window),
                    )
                    signatures[sig].append((occ, steps))

        # Step 4: count support and filter.
        motifs: list[TemporalMotif] = []
        for sig in sorted(signatures):
            sig_rows = signatures[sig]
            if len(sig_rows) < self._options.min_support_count:
                continue

            occurrences = [row[0] for row in sig_rows]
            distinct_packs = {occ.package_id for occ in occurrences}
            distinct_seqs = {(occ.package_id, occ.sequence_file_id) for occ in occurrences}
            if len(distinct_packs) < self._options.min_distinct_pack_count:
                continue
            if len(distinct_seqs) < self._options.min_distinct_sequence_count:
                continue

            steps = sig_rows[0][1]
            energy_seq = [s.energy_class for s in steps]
            pattern_name = self._classify_energy_pattern(energy_seq)

            motif_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    f"temporal_motif_v1:{sig}",
                )
            )
            sorted_occs = sorted(
                occurrences,
                key=lambda o: (
                    o.package_id,
                    o.sequence_file_id,
                    o.start_ms,
                ),
            )[: self._options.max_occurrences_per_motif]

            motifs.append(
                TemporalMotif(
                    motif_id=motif_id,
                    temporal_signature=sig,
                    pattern_name=pattern_name,
                    sequence_length=len(steps),
                    steps=steps,
                    support_count=len(occurrences),
                    distinct_pack_count=len(distinct_packs),
                    distinct_sequence_count=len(distinct_seqs),
                    occurrences=tuple(sorted_occs),
                )
            )

        motifs.sort(key=lambda m: m.motif_id)
        return TemporalMotifCatalog(
            total_sequences=len(all_sequences),
            total_temporal_motifs=len(motifs),
            motifs=tuple(motifs),
        )

    @staticmethod
    def _gap_bucket(gap_ms: int) -> str:
        """Classify inter-phrase gap into a named bucket."""
        if gap_ms < 100:
            return "immediate"
        if gap_ms < 500:
            return "short"
        if gap_ms <= 2000:
            return "medium"
        return "long"

    @classmethod
    def _build_temporal_signature(
        cls,
        *,
        window: list[EffectPhrase],
        template_by_phrase: dict[str, str],
    ) -> tuple[str, tuple[TemporalMotifStep, ...]]:
        """Build an ordered temporal signature and steps for an n-gram."""
        parts: list[str] = []
        steps: list[TemporalMotifStep] = []

        for idx, phrase in enumerate(window):
            family = phrase.effect_family
            energy = phrase.energy_class.value
            motion = phrase.motion_class.value

            token = f"{family}:{energy}"
            if idx == 0:
                gap_ms: int | None = None
                parts.append(token)
            else:
                prev = window[idx - 1]
                raw_gap = phrase.start_ms - prev.end_ms
                gap_ms = max(raw_gap, 0)
                bucket = cls._gap_bucket(gap_ms)
                parts.append(f"{bucket}")
                parts.append(token)

            steps.append(
                TemporalMotifStep(
                    position=idx,
                    effect_family=family,
                    energy_class=energy,
                    motion_class=motion,
                    gap_from_previous_ms=gap_ms,
                )
            )

        sig = "ordered|" + "\u2192".join(parts)
        return sig, tuple(steps)

    @staticmethod
    def _classify_energy_pattern(energy_seq: list[str]) -> str:
        """Name a pattern based on energy trajectory."""
        _ORDER = {"low": 0, "mid": 1, "high": 2, "burst": 3, "unknown": 1}

        if len(energy_seq) < 2:
            return "other"

        vals = [_ORDER.get(e, 1) for e in energy_seq]

        # Check strictly increasing -> build
        if all(vals[i] < vals[i + 1] for i in range(len(vals) - 1)):
            return "build"

        # Check strictly decreasing -> drop
        if all(vals[i] > vals[i + 1] for i in range(len(vals) - 1)):
            return "drop"

        # Check all same -> repetition
        if all(e == energy_seq[0] for e in energy_seq):
            return "repetition"

        # high -> low -> high = dip (length 3+)
        if len(vals) >= 3:
            if vals[0] > vals[1] and vals[-1] >= vals[0]:
                return "dip"

        # burst -> non-burst -> burst = call_and_response
        if len(energy_seq) >= 3:
            if (
                energy_seq[0] == "burst"
                and energy_seq[-1] == "burst"
                and any(e != "burst" for e in energy_seq[1:-1])
            ):
                return "call_and_response"

        # sweep motion followed by burst energy = build_and_burst
        # (checked at caller level via motion, but simplified here)
        if len(energy_seq) >= 2 and vals[-1] > vals[-2] and energy_seq[-1] == "burst":
            return "build_and_burst"

        return "other"
