from __future__ import annotations

from typing import Any

import pytest

from twinklr.core.agents.providers.base import (
    LLMProvider,
    LLMResponse,
    ResponseMetadata,
)
from twinklr.core.config.models import AgentConfig
from twinklr.core.feature_engineering.normalization.llm_review import LLMReviewPass
from twinklr.core.feature_engineering.normalization.models import (
    AliasClusterGroup,
    AliasReviewResult,
)


def _make_cluster(
    cluster_id: str = "c1",
    members: tuple[str, ...] = ("chase", "chaser"),
    member_counts: tuple[int, ...] = (10, 5),
    centroid_similarity: float = 0.92,
    suggested_canonical: str = "chase",
) -> AliasClusterGroup:
    return AliasClusterGroup(
        cluster_id=cluster_id,
        members=members,
        member_counts=member_counts,
        centroid_similarity=centroid_similarity,
        suggested_canonical=suggested_canonical,
    )


class _FakeProvider(LLMProvider):
    """Fake LLMProvider that returns a pre-built LLMResponse or raises."""

    def __init__(self, content: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self._content = content
        self._error = error
        self.calls: list[dict[str, Any]] = []

    def generate_json(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self.calls.append({"messages": messages, "model": model, "temperature": temperature})
        if self._error is not None:
            raise self._error
        return LLMResponse(content=self._content, metadata=ResponseMetadata())


# ---------------------------------------------------------------------------
# test_valid_cluster_approved
# ---------------------------------------------------------------------------


def test_valid_cluster_approved() -> None:
    """LLM returning approved=true produces an AliasReviewResult with approved=True."""
    response = {
        "approved": True,
        "canonical_label": "chase",
        "confidence": 0.9,
        "rationale": "Same effect",
        "suggested_effect_family": "MOTION",
        "suggested_motion_class": "chase",
    }
    provider = _FakeProvider(content=response)
    reviewer = LLMReviewPass(provider=provider, config=AgentConfig())
    cluster = _make_cluster()

    (result,) = reviewer.review((cluster,))

    assert isinstance(result, AliasReviewResult)
    assert result.approved is True
    assert result.cluster_id == "c1"


# ---------------------------------------------------------------------------
# test_dissimilar_cluster_rejected
# ---------------------------------------------------------------------------


def test_dissimilar_cluster_rejected() -> None:
    """LLM returning approved=false produces an AliasReviewResult with approved=False."""
    response = {
        "approved": False,
        "canonical_label": "chase",
        "confidence": 0.3,
        "rationale": "These are different effects",
        "suggested_effect_family": "MOTION",
        "suggested_motion_class": "unknown",
    }
    provider = _FakeProvider(content=response)
    reviewer = LLMReviewPass(provider=provider, config=AgentConfig())
    cluster = _make_cluster()

    (result,) = reviewer.review((cluster,))

    assert result.approved is False


# ---------------------------------------------------------------------------
# test_llm_response_parsed_into_model
# ---------------------------------------------------------------------------


def test_llm_response_parsed_into_model() -> None:
    """All fields from the LLM JSON response map correctly into AliasReviewResult."""
    response = {
        "approved": True,
        "canonical_label": "sweep",
        "confidence": 0.85,
        "rationale": "Both names describe a sweep motion",
        "suggested_effect_family": "MOTION",
        "suggested_motion_class": "sweep",
    }
    cluster = _make_cluster(
        cluster_id="c42",
        members=("sweep", "sweeper", "sweep_left"),
        member_counts=(20, 8, 3),
        centroid_similarity=0.88,
        suggested_canonical="sweep",
    )
    provider = _FakeProvider(content=response)
    reviewer = LLMReviewPass(provider=provider, config=AgentConfig(model="gpt-4o"))

    (result,) = reviewer.review((cluster,))

    assert result.cluster_id == "c42"
    assert result.approved is True
    assert result.canonical_label == "sweep"
    assert result.confidence == pytest.approx(0.85)
    assert result.rationale == "Both names describe a sweep motion"
    assert result.members == ("sweep", "sweeper", "sweep_left")
    assert result.suggested_effect_family == "MOTION"
    assert result.suggested_motion_class == "sweep"
    assert provider.calls[0]["model"] == "gpt-4o"


# ---------------------------------------------------------------------------
# test_review_single_uses_provider_framework
# ---------------------------------------------------------------------------


def test_review_single_uses_provider_framework() -> None:
    """_review_single() calls provider.generate_json() and reads response.content
    directly with no manual json.loads step in the test's mock path."""
    response = {
        "approved": True,
        "canonical_label": "chase",
        "confidence": 0.9,
        "rationale": "Same effect",
        "suggested_effect_family": "MOTION",
        "suggested_motion_class": "chase",
    }
    provider = _FakeProvider(content=response)
    config = AgentConfig(model="gpt-4o-mini", temperature=0.2)
    reviewer = LLMReviewPass(provider=provider, config=config)
    cluster = _make_cluster()

    reviewer._review_single(cluster)

    assert len(provider.calls) == 1
    call = provider.calls[0]
    assert call["model"] == "gpt-4o-mini"
    assert call["temperature"] == pytest.approx(0.2)
    assert isinstance(call["messages"], list)


# ---------------------------------------------------------------------------
# test_malformed_llm_response_fallback
# ---------------------------------------------------------------------------


def test_malformed_llm_response_fallback() -> None:
    """When the LLM call raises an exception, a fallback result is returned."""
    provider = _FakeProvider(error=RuntimeError("API error"))
    reviewer = LLMReviewPass(provider=provider, config=AgentConfig())
    cluster = _make_cluster(suggested_canonical="chase")

    (result,) = reviewer.review((cluster,))

    assert result.approved is False
    assert result.confidence == pytest.approx(0.0)
    assert result.rationale == "LLM review failed"
    assert result.canonical_label == "chase"
    assert result.cluster_id == "c1"


# ---------------------------------------------------------------------------
# test_build_user_prompt_format
# ---------------------------------------------------------------------------


def test_build_user_prompt_format() -> None:
    """The user prompt contains cluster members, their counts, and metadata."""
    cluster = _make_cluster(
        cluster_id="c99",
        members=("pulse", "pulsing"),
        member_counts=(15, 7),
        centroid_similarity=0.91,
        suggested_canonical="pulse",
    )
    prompt = LLMReviewPass._build_user_prompt(cluster)

    assert "c99" in prompt
    assert "pulse" in prompt
    assert "pulsing" in prompt
    assert "count: 15" in prompt
    assert "count: 7" in prompt
    assert "0.910" in prompt
