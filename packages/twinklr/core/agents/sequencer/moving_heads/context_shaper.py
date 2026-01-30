"""Moving head context shaper for token-efficient prompts."""

from __future__ import annotations

import logging
from typing import Any

from twinklr.core.agents.context import BaseContextShaper, ShapedContext

logger = logging.getLogger(__name__)


class MovingHeadContextShaper(BaseContextShaper):
    """Context shaper for moving head choreography domain.

    Reduces context size while preserving critical information:
    - Song structure (always preserved)
    - Fixture configuration (always preserved)
    - Beat grid (always preserved)
    - Summarizes audio features
    - Truncates template lists
    - Removes verbose metadata
    """

    def __init__(
        self,
        max_tokens: int = 4000,
        preserve_keys: list[str] | None = None,
    ):
        """Initialize moving head context shaper.

        Args:
            max_tokens: Maximum tokens for filtered context
            preserve_keys: Keys to always preserve (adds to defaults)
        """
        super().__init__()

        self.max_tokens = max_tokens

        # Default critical keys for moving head domain
        default_preserve = [
            "song_structure",
            "fixtures",
            "beat_grid",
            "feedback",
            "available_templates",
        ]

        if preserve_keys:
            # Merge with defaults
            self.preserve_keys = list(set(default_preserve + preserve_keys))
        else:
            self.preserve_keys = default_preserve

    def shape(
        self, agent: Any = None, context: dict[str, Any] | None = None, budget: int | None = None
    ) -> ShapedContext:
        """Shape context for moving head agents.

        Strategy:
        1. Always preserve critical keys
        2. Summarize audio features
        3. Truncate template lists
        4. Remove verbose metadata
        5. Truncate nested structures if needed

        Args:
            agent: Agent spec (unused for now)
            context: Full context dictionary
            budget: Optional budget override

        Returns:
            ShapedContext with reduced size
        """
        if context is None:
            context = {}

        # Use budget if provided, otherwise use max_tokens
        max_tokens = budget if budget is not None else self.max_tokens

        original_tokens = self.estimator.estimate(context)

        # If under budget, return as-is
        if original_tokens <= max_tokens:
            return ShapedContext(
                data=context,
                stats={
                    "original_estimate": original_tokens,
                    "shaped_estimate": original_tokens,
                    "reduction_pct": 0.0,
                    "preserved_keys": list(context.keys()),
                    "removed_keys": [],
                    "notes": [],
                },
            )

        # Start with preserved keys
        filtered = {}
        for key in self.preserve_keys:
            if key in context:
                filtered[key] = context[key]

        # Add other keys with reduction strategies
        for key, value in context.items():
            if key in self.preserve_keys:
                continue  # Already added

            # Apply domain-specific reductions
            if key == "audio_features":
                filtered[key] = self._summarize_audio_features(value)
            elif key == "template_library":
                filtered[key] = self._truncate_template_library(value)
            elif key in ["metadata", "debug_info", "raw_audio"]:
                # Skip verbose metadata
                continue
            else:
                # Include other keys if budget allows
                test_context = {**filtered, key: value}
                if self.estimator.estimate(test_context) <= max_tokens:
                    filtered[key] = value

        # Calculate final metrics
        orig_tokens, shaped_tokens, reduction_pct = self._calculate_reduction(context, filtered)

        preserved = list(filtered.keys())
        removed = [k for k in context.keys() if k not in filtered]

        # Log if agent name available
        if agent and hasattr(agent, "name"):
            self._log_shaping(agent.name, orig_tokens, shaped_tokens, reduction_pct)

        return ShapedContext(
            data=filtered,
            stats={
                "original_estimate": orig_tokens,
                "shaped_estimate": shaped_tokens,
                "reduction_pct": reduction_pct,
                "preserved_keys": preserved,
                "removed_keys": removed,
                "notes": [f"Preserved {len(preserved)} keys, removed {len(removed)} keys"],
            },
        )

    def _summarize_audio_features(self, features: Any) -> dict[str, Any]:
        """Summarize audio features to reduce size.

        Args:
            features: Audio features dict

        Returns:
            Summarized features
        """
        if not isinstance(features, dict):
            return {}

        summarized: dict[str, Any] = {}

        for key, value in features.items():
            if isinstance(value, list):
                # Summarize arrays (keep first 10, last 10, and stats)
                if len(value) > 20:
                    summarized[key] = {
                        "first": value[:10],
                        "last": value[-10:],
                        "length": len(value),
                        "summary": "truncated",
                    }
                else:
                    summarized[key] = value
            elif isinstance(value, dict):
                # Recursively summarize nested dicts
                summarized[key] = self._summarize_audio_features(value)
            else:
                summarized[key] = value

        return summarized

    def _truncate_template_list(self, templates: Any) -> list[Any]:
        """Truncate template list to reduce size.

        Args:
            templates: List of templates

        Returns:
            Truncated list
        """
        if not isinstance(templates, list):
            return []

        # Keep first 50 templates (most common/relevant)
        max_templates = 50
        if len(templates) > max_templates:
            return templates[:max_templates]

        return templates

    def _truncate_template_library(self, library: Any) -> dict[str, Any]:
        """Truncate template library details.

        Args:
            library: Template library dict

        Returns:
            Truncated library
        """
        if not isinstance(library, dict):
            return {}

        # Keep only template names, not full definitions
        if "templates" in library:
            templates = library["templates"]
            if isinstance(templates, dict):
                library["templates"] = {
                    name: {"name": name, "summary": "truncated"}
                    for name in list(templates.keys())[:50]
                }

        return library
