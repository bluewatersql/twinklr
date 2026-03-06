"""Embedder implementations for effect name and context embedding."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    pass


@runtime_checkable
class EmbedderProtocol(Protocol):
    """Protocol for embedding effect names and contexts."""

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """Embed a sequence of text strings into float vectors.

        Args:
            texts: Strings to embed.

        Returns:
            Tuple of float-vector tuples, one per input text.
        """
        ...


class SentenceTransformerEmbedder:
    """Embedder using sentence-transformers library (optional dependency).

    Args:
        model_name: HuggingFace model identifier.

    Raises:
        ImportError: If sentence-transformers is not installed.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(model_name)
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is required for SentenceTransformerEmbedder. "
                "Install with: pip install 'twinklr[normalization]'"
            ) from exc

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """Embed texts using the sentence-transformer model.

        Args:
            texts: Strings to embed.

        Returns:
            Tuple of float-vector tuples, one per input text.
        """
        if not texts:
            return ()
        embeddings = self._model.encode(list(texts))
        return tuple(tuple(float(x) for x in row) for row in embeddings)


class OpenAIEmbedder:
    """Embedder using the OpenAI embeddings API via an existing twinklr client.

    Args:
        client: An ``OpenAIClient`` instance whose ``.client`` attribute is
            the raw ``openai.OpenAI`` object.
        model: Embedding model name.
    """

    def __init__(
        self,
        client: Any,
        model: str = "text-embedding-3-small",
    ) -> None:
        self._client = client
        self._model = model

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """Call the OpenAI embeddings endpoint and return float vectors.

        Args:
            texts: Strings to embed.

        Returns:
            Tuple of float-vector tuples, one per input text.
        """
        if not texts:
            return ()
        response = self._client.client.embeddings.create(
            input=list(texts),
            model=self._model,
        )
        return tuple(tuple(float(x) for x in item.embedding) for item in response.data)
