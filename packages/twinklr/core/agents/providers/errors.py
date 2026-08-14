"""Provider-specific errors."""

from __future__ import annotations

from typing import Literal

from twinklr.core.agents.providers.base import TokenUsage


class LLMProviderError(Exception):
    """Base exception for LLM provider errors.

    Raised when provider exhausts retries or encounters unrecoverable errors.
    """


RecoverableResponseReason = Literal[
    "json_decode",
    "refusal",
    "truncation",
    "content_filter",
    "empty_response",
]


class RecoverableLLMProviderError(LLMProviderError):
    """A completed provider call whose response can be retried safely.

    Transport/rate-limit retries stay inside the provider.  This exception is
    reserved for response-level outcomes where another logical model call is
    appropriate: refusal, truncation, content filtering, empty output, or a
    malformed JSON payload on the compatibility fallback path.
    """

    def __init__(
        self,
        *,
        reason: RecoverableResponseReason,
        message: str,
        token_usage: TokenUsage | None = None,
    ):
        super().__init__(message)
        self.reason = reason
        self.token_usage = token_usage or TokenUsage()
