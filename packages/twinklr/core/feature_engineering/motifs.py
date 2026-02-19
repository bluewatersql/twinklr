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
            rows = signatures[signature]
            if len(rows) < self._options.min_support_count:
                continue

            occurrences = [row[0] for row in rows]
            template_ids = sorted({item for row in rows for item in row[1]})
            taxonomy_labels = sorted({item for row in rows for item in row[2]})
            distinct_packs = {(row.package_id) for row in occurrences}
            distinct_sequences = {
                (row.package_id, row.sequence_file_id) for row in occurrences
            }
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
                    template_ids=tuple(template_ids),
                    taxonomy_labels=tuple(taxonomy_labels),
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
