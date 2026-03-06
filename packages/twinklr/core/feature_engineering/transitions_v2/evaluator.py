"""TransitionEvaluator: compare Markov model quality against a TransitionGraph."""

from __future__ import annotations

from twinklr.core.feature_engineering.models.transitions import TransitionEdge, TransitionGraph
from twinklr.core.feature_engineering.transitions_v2.markov import MarkovTransitionModel
from twinklr.core.feature_engineering.transitions_v2.models import TransitionEvalReport


class TransitionEvaluator:
    """Compare Markov model predictions against an existing TransitionGraph.

    Metrics:
    - top_k_recall: For each template, overlap between model's top-k predictions
      and graph's top-k neighbors, averaged across all templates.
    - hit_rate: For held-out transitions, how often the actual target is in
      model's top-k predictions.
    - coverage: Fraction of unique templates that have at least one prediction
      from the model.

    Args:
        k: Number of top predictions to consider for recall and hit-rate.
    """

    def __init__(self, k: int = 5) -> None:
        """Initialise evaluator.

        Args:
            k: Top-k cutoff used for recall and hit-rate computations.
        """
        self._k = k

    def evaluate(
        self,
        model: MarkovTransitionModel,
        graph: TransitionGraph,
        held_out_transitions: tuple[TransitionEdge, ...],
    ) -> TransitionEvalReport:
        """Compute evaluation metrics for the model against the graph.

        Args:
            model: A fitted ``MarkovTransitionModel``.
            graph: The reference ``TransitionGraph`` to evaluate against.
            held_out_transitions: Edges withheld from training, used for
                hit-rate computation.

        Returns:
            ``TransitionEvalReport`` with all computed metrics and counts.
        """
        k = self._k

        # Collect all unique source template ids from graph edges.
        all_source_ids: list[str] = []
        seen_sources: set[str] = set()
        for edge in graph.edges:
            if edge.source_template_id not in seen_sources:
                all_source_ids.append(edge.source_template_id)
                seen_sources.add(edge.source_template_id)

        total_templates = len(all_source_ids)

        # ------------------------------------------------------------------ #
        # top_k_recall
        # ------------------------------------------------------------------ #
        recall_scores: list[float] = []
        for src_id in all_source_ids:
            # Graph's top-k targets for this source (by edge_count descending).
            src_edges = [e for e in graph.edges if e.source_template_id == src_id]
            graph_top_k = {
                e.target_template_id
                for e in sorted(src_edges, key=lambda e: e.edge_count, reverse=True)[:k]
            }

            # Model's top-k predictions.
            predictions = model.predict(src_id, k=k)
            model_top_k = {p.template_id for p in predictions}

            overlap = len(graph_top_k & model_top_k)
            recall_scores.append(overlap / k if k > 0 else 0.0)

        top_k_recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0.0

        # ------------------------------------------------------------------ #
        # hit_rate
        # ------------------------------------------------------------------ #
        held_out_count = len(held_out_transitions)
        if held_out_count == 0:
            hit_rate = 0.0
        else:
            hits = 0
            for edge in held_out_transitions:
                predictions = model.predict(edge.source_template_id, k=k)
                predicted_ids = {p.template_id for p in predictions}
                if edge.target_template_id in predicted_ids:
                    hits += 1
            hit_rate = hits / held_out_count

        # ------------------------------------------------------------------ #
        # coverage
        # ------------------------------------------------------------------ #
        templates_with_predictions = 0
        for src_id in all_source_ids:
            if model.predict(src_id, k=1):
                templates_with_predictions += 1

        coverage = templates_with_predictions / total_templates if total_templates > 0 else 0.0

        return TransitionEvalReport(
            top_k_recall=top_k_recall,
            hit_rate=hit_rate,
            coverage=coverage,
            total_templates=total_templates,
            templates_with_predictions=templates_with_predictions,
            held_out_count=held_out_count,
        )
