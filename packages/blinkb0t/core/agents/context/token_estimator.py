"""Token estimation utilities."""

import json
from typing import Any


class TokenEstimator:
    """Estimates token counts for context data.

    Uses rough heuristics:
    - 1 token ≈ 4 characters (English text)
    - JSON overhead: ~20% more tokens
    """

    @staticmethod
    def estimate(data: dict[str, Any]) -> int:
        """Estimate token count for data.

        Args:
            data: Dictionary to estimate

        Returns:
            Estimated token count
        """
        json_str = json.dumps(data)
        char_count = len(json_str)

        # 1 token ≈ 4 chars, add 20% for JSON overhead
        token_estimate = int((char_count / 4) * 1.2)

        return token_estimate

    @staticmethod
    def estimate_text(text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        # 1 token ≈ 4 chars for English
        return int(len(text) / 4)

    @staticmethod
    def estimate_list(items: list[Any]) -> int:
        """Estimate token count for list.

        Args:
            items: List to estimate

        Returns:
            Estimated token count
        """
        return TokenEstimator.estimate({"items": items})
