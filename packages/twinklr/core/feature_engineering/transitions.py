"""Deterministic transition modeling (V1.6)."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from twinklr.core.feature_engineering.models import EffectPhrase, TemplateCatalog
from twinklr.core.feature_engineering.models.transitions import (
    TransitionAnomaly,
    TransitionEdge,
    TransitionGraph,
    TransitionRecord,
    TransitionType,
)


@dataclass(frozen=True)
class TransitionModelerOptions:
    schema_version: str = "v1.6.0"
    graph_version: str = "transition_graph_v1"


class TransitionModeler:
    """Build transition records and graph edges from template assignments."""

    def __init__(self, options: TransitionModelerOptions | None = None) -> None:
        self._options = options or TransitionModelerOptions()

    def build_graph(
        self,
        *,
        phrases: tuple[EffectPhrase, ...],
        orchestration_catalog: TemplateCatalog,
    ) -> TransitionGraph:
        assignment = {
            row.phrase_id: row.template_id for row in orchestration_catalog.assignments
        }
        by_sequence: dict[tuple[str, str], list[EffectPhrase]] = defaultdict(list)
        for phrase in phrases:
            if phrase.phrase_id in assignment:
                by_sequence[(phrase.package_id, phrase.sequence_file_id)].append(phrase)

        transitions: list[TransitionRecord] = []
        edges: dict[tuple[str, str], list[TransitionRecord]] = defaultdict(list)

        for (package_id, sequence_file_id), seq_rows in sorted(by_sequence.items()):
            ordered = sorted(
                seq_rows,
                key=lambda row: (
                    row.start_ms,
                    row.layer_index,
                    row.phrase_id,
                ),
            )
            for left, right in zip(ordered, ordered[1:], strict=False):
                from_template = assignment[left.phrase_id]
                to_template = assignment[right.phrase_id]
                if from_template == to_template:
                    continue
                gap_ms = right.start_ms - left.end_ms
                record = TransitionRecord(
                    package_id=package_id,
                    sequence_file_id=sequence_file_id,
                    from_phrase_id=left.phrase_id,
                    to_phrase_id=right.phrase_id,
                    from_template_id=from_template,
                    to_template_id=to_template,
                    from_end_ms=left.end_ms,
                    to_start_ms=right.start_ms,
                    gap_ms=gap_ms,
                    transition_type=self._classify(abs(right.layer_index - left.layer_index), gap_ms),
                )
                transitions.append(record)
                edges[(from_template, to_template)].append(record)

        edge_rows: list[TransitionEdge] = []
        for key in sorted(edges.keys()):
            rows = edges[key]
            distribution = Counter(row.transition_type for row in rows)
            edge_rows.append(
                TransitionEdge(
                    source_template_id=key[0],
                    target_template_id=key[1],
                    edge_count=len(rows),
                    confidence=round(min(1.0, len(rows) / 10.0), 6),
                    mean_gap_ms=round(sum(row.gap_ms for row in rows) / len(rows), 6),
                    transition_type_distribution={
                        transition_type: distribution[transition_type]
                        for transition_type in sorted(distribution.keys(), key=lambda item: item.value)
                    },
                )
            )

        anomalies = self._anomalies(orchestration_catalog, edge_rows)
        return TransitionGraph(
            schema_version=self._options.schema_version,
            graph_version=self._options.graph_version,
            total_transitions=len(transitions),
            total_nodes=len(orchestration_catalog.templates),
            total_edges=len(edge_rows),
            edges=tuple(edge_rows),
            transitions=tuple(transitions),
            anomalies=anomalies,
        )

    @staticmethod
    def _classify(layer_delta: int, gap_ms: int) -> TransitionType:
        if gap_ms < 0:
            return TransitionType.OVERLAP_BLEND
        if gap_ms == 0 and layer_delta == 0:
            return TransitionType.HARD_CUT
        if 0 <= gap_ms <= 250:
            return TransitionType.CROSSFADE
        return TransitionType.TIMED_GAP

    @staticmethod
    def _anomalies(
        catalog: TemplateCatalog,
        edges: list[TransitionEdge],
    ) -> tuple[TransitionAnomaly, ...]:
        nodes = {row.template_id for row in catalog.templates}
        active_nodes = {row.source_template_id for row in edges} | {row.target_template_id for row in edges}
        orphan_nodes = sorted(nodes - active_nodes)

        rows: list[TransitionAnomaly] = []
        if orphan_nodes:
            rows.append(
                TransitionAnomaly(
                    code="orphan_template_nodes",
                    severity="warning",
                    message=f"{len(orphan_nodes)} template nodes have no transition edges",
                )
            )

        self_loops = sum(1 for row in edges if row.source_template_id == row.target_template_id)
        if self_loops > 0:
            rows.append(
                TransitionAnomaly(
                    code="self_loop_edges",
                    severity="info",
                    message=f"{self_loops} self-loop transition edges detected",
                )
            )

        return tuple(rows)
