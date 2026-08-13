"""Error taxonomy shared by the audio metadata provider clients.

Provider failures reach the user through `MetadataPipeline` warnings. A bare
"provider lookup failed" cannot be told apart from a network fault, a bad
credential, or a broken response contract, which points debugging in the wrong
direction. Every provider error therefore carries a category.
"""

from __future__ import annotations

from enum import StrEnum


class ProviderFailureCategory(StrEnum):
    """Why a provider lookup failed."""

    TRANSPORT = "transport"
    """Network, timeout, or upstream HTTP error — retryable, not our contract."""

    CREDENTIAL = "credential"
    """Authentication or authorization rejected the request."""

    PARSE = "parse"
    """The response could not be decoded, or violated the expected schema."""

    PROVIDER_ERROR = "provider_error"
    """A well-formed response in which the provider reported its own error."""

    UNKNOWN = "unknown"
    """Unclassified failure."""


class ProviderLookupError(RuntimeError):
    """Base class for provider lookup failures.

    Args:
        message: Human-readable description.
        category: Which kind of failure this is.
    """

    def __init__(
        self,
        message: str,
        *,
        category: ProviderFailureCategory = ProviderFailureCategory.UNKNOWN,
    ) -> None:
        super().__init__(message)
        self.category = category


def failure_category(error: BaseException) -> ProviderFailureCategory:
    """Read the category off an exception, defaulting to UNKNOWN."""
    category = getattr(error, "category", None)
    if isinstance(category, ProviderFailureCategory):
        return category
    return ProviderFailureCategory.UNKNOWN
