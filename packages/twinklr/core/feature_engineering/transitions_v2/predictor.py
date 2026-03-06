"""Planner-friendly query interface wrapping MarkovTransitionModel."""

from __future__ import annotations

from twinklr.core.feature_engineering.models.transitions import TransitionGraph
from twinklr.core.feature_engineering.transitions_v2.markov import MarkovTransitionModel
from twinklr.core.feature_engineering.transitions_v2.models import TransitionSuggestion


class TransitionPredictor:
    """Planner-friendly query interface wrapping MarkovTransitionModel.

    Falls back to TransitionGraph when model lacks data.
    """

    def __init__(
        self,
        model: MarkovTransitionModel,
        fallback_graph: TransitionGraph | None = None,
    ) -> None:
        """Initialise with a fitted Markov model and optional fallback graph.

        Args:
            model: A fitted ``MarkovTransitionModel``.
            fallback_graph: Optional ``TransitionGraph`` used when the model
                returns no predictions for a given template.
        """
        self._model = model
        self._fallback_graph = fallback_graph

    def suggest_next(
        self,
        current_template_id: str,
        section_duration_ms: int,
        k: int = 5,
        min_confidence: float = 0.1,
    ) -> tuple[TransitionSuggestion, ...]:
        """Suggest the next template to transition to.

        Queries the Markov model first, filtered by ``min_confidence``.  If the
        model returns nothing and a fallback graph was provided, graph edges are
        used instead.

        Args:
            current_template_id: The template currently being displayed.
            section_duration_ms: Duration of the current section in ms; used
                for duration-conditioned model lookup.
            k: Maximum number of suggestions to return.
            min_confidence: Minimum probability threshold; predictions below
                this value are discarded.

        Returns:
            Tuple of up to ``k`` ``TransitionSuggestion`` objects sorted by
            probability descending.
        """
        predictions = self._model.predict(
            current_template_id=current_template_id,
            duration_ms=section_duration_ms,
            k=k,
        )

        # Filter by min_confidence.
        filtered = [p for p in predictions if p.probability >= min_confidence]

        if filtered:
            return tuple(
                TransitionSuggestion(
                    template_id=p.template_id,
                    probability=p.probability,
                    confidence=p.probability,
                    source="markov",
                    rank=rank,
                )
                for rank, p in enumerate(filtered, start=1)
            )

        # Fallback to graph edges.
        if self._fallback_graph is not None:
            matching = [
                edge
                for edge in self._fallback_graph.edges
                if edge.source_template_id == current_template_id
            ]
            # Sort by confidence descending, take top-k.
            matching.sort(key=lambda e: e.confidence, reverse=True)
            return tuple(
                TransitionSuggestion(
                    template_id=edge.target_template_id,
                    probability=edge.confidence,
                    confidence=edge.confidence,
                    source="fallback_graph",
                    rank=rank,
                )
                for rank, edge in enumerate(matching[:k], start=1)
            )

        return ()
