"""Provider-specific errors."""


class LLMProviderError(Exception):
    """Base exception for LLM provider errors.

    Raised when provider exhausts retries or encounters unrecoverable errors.
    """

    pass
