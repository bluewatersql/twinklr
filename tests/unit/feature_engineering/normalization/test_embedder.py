"""Tests for normalization embedder implementations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from twinklr.core.feature_engineering.normalization.embedder import (
    EmbedderProtocol,
    OpenAIEmbedder,
    SentenceTransformerEmbedder,
)

# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_protocol_check_sentence_transformer() -> None:
    """SentenceTransformerEmbedder satisfies EmbedderProtocol at runtime."""
    mock_st = MagicMock()
    mock_st.encode.return_value = np.zeros((1, 4))

    with patch.dict(
        "sys.modules",
        {"sentence_transformers": MagicMock(SentenceTransformer=MagicMock(return_value=mock_st))},
    ):
        embedder = SentenceTransformerEmbedder(model_name="all-MiniLM-L6-v2")

    assert isinstance(embedder, EmbedderProtocol)


def test_protocol_check_openai_embedder() -> None:
    """OpenAIEmbedder satisfies EmbedderProtocol at runtime."""
    client = MagicMock()
    embedder = OpenAIEmbedder(client=client)
    assert isinstance(embedder, EmbedderProtocol)


# ---------------------------------------------------------------------------
# SentenceTransformerEmbedder
# ---------------------------------------------------------------------------


def test_sentence_transformer_produces_vectors() -> None:
    """embed() returns a tuple of float-vector tuples with correct shape."""
    fixed_array = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]], dtype=np.float32)
    mock_model = MagicMock()
    mock_model.encode.return_value = fixed_array

    with patch.dict(
        "sys.modules",
        {
            "sentence_transformers": MagicMock(
                SentenceTransformer=MagicMock(return_value=mock_model)
            )
        },
    ):
        embedder = SentenceTransformerEmbedder()
        result = embedder.embed(("hello", "world"))

    assert len(result) == 2
    assert len(result[0]) == 3
    assert all(isinstance(v, float) for v in result[0])
    assert pytest.approx(result[0][0], abs=1e-6) == 0.1
    assert pytest.approx(result[1][2], abs=1e-6) == 0.6


def test_sentence_transformer_empty_input_returns_empty() -> None:
    """embed() returns () for empty input without calling the model."""
    mock_model = MagicMock()

    with patch.dict(
        "sys.modules",
        {
            "sentence_transformers": MagicMock(
                SentenceTransformer=MagicMock(return_value=mock_model)
            )
        },
    ):
        embedder = SentenceTransformerEmbedder()
        result = embedder.embed(())

    assert result == ()
    mock_model.encode.assert_not_called()


def test_sentence_transformer_import_error_raises() -> None:
    """ImportError is raised when sentence_transformers is absent."""
    import sys

    original = sys.modules.pop("sentence_transformers", None)
    try:
        # Force a fresh import attempt by removing the cached module.
        with (
            patch.dict("sys.modules", {"sentence_transformers": None}),  # type: ignore[dict-item]
            pytest.raises(ImportError, match="sentence-transformers is required"),
        ):
            SentenceTransformerEmbedder()
    finally:
        if original is not None:
            sys.modules["sentence_transformers"] = original


# ---------------------------------------------------------------------------
# OpenAIEmbedder
# ---------------------------------------------------------------------------


def _make_openai_response(vectors: list[list[float]]) -> MagicMock:
    """Build a mock OpenAI embeddings response."""
    response = MagicMock()
    response.data = [MagicMock(embedding=vec) for vec in vectors]
    return response


def test_openai_embedder_produces_vectors() -> None:
    """embed() calls the embeddings endpoint and returns correct tuples."""
    vectors = [[0.1, 0.2, 0.3], [0.7, 0.8, 0.9]]
    client = MagicMock()
    client.client.embeddings.create.return_value = _make_openai_response(vectors)

    embedder = OpenAIEmbedder(client=client, model="text-embedding-3-small")
    result = embedder.embed(("foo", "bar"))

    client.client.embeddings.create.assert_called_once_with(
        input=["foo", "bar"],
        model="text-embedding-3-small",
    )
    assert len(result) == 2
    assert len(result[0]) == 3
    assert pytest.approx(result[0][0], abs=1e-6) == 0.1
    assert pytest.approx(result[1][2], abs=1e-6) == 0.9


def test_openai_embedder_empty_input_returns_empty() -> None:
    """embed() returns () for empty input without calling the API."""
    client = MagicMock()
    embedder = OpenAIEmbedder(client=client)
    result = embedder.embed(())

    assert result == ()
    client.client.embeddings.create.assert_not_called()
