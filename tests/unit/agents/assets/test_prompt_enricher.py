"""Tests for LLM prompt enricher."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from twinklr.core.agents.assets.models import AssetCategory, AssetSpec, EnrichedPrompt
from twinklr.core.agents.assets.prompt_enricher import (
    build_enricher_spec,
    build_enrichment_variables,
    enrich_spec,
)
from twinklr.core.agents.result import AgentResult
from twinklr.core.agents.spec import AgentMode
from twinklr.core.sequencer.vocabulary import BackgroundMode


def _success_result(data: object) -> AgentResult:
    """Wrap data in a successful AgentResult."""
    return AgentResult(success=True, data=data, duration_seconds=0.1, tokens_used=50)


def _failure_result(error: str) -> AgentResult:
    """Create a failed AgentResult."""
    return AgentResult(success=False, error_message=error, duration_seconds=0.0, tokens_used=0)


def _make_image_spec() -> AssetSpec:
    return AssetSpec(
        spec_id="asset_image_texture_sparkles",
        category=AssetCategory.IMAGE_TEXTURE,
        motif_id="sparkles",
        theme_id="theme.holiday.traditional",
        section_ids=["intro_1"],
        target_roles=["MEGA_TREE"],
        background=BackgroundMode.OPAQUE,
        style_tags=["holiday_christmas_traditional"],
        content_tags=["sparkles"],
        scene_context=["Traditional Christmas feel"],
    )


class TestBuildEnricherSpec:
    def test_defaults(self) -> None:
        spec = build_enricher_spec()
        assert spec.name == "asset_prompt_enricher"
        assert spec.mode == AgentMode.ONESHOT
        assert spec.temperature == 0.6
        assert spec.response_model == EnrichedPrompt

    def test_custom_model(self) -> None:
        spec = build_enricher_spec(model="gpt-5.2", temperature=0.3)
        assert spec.model == "gpt-5.2"
        assert spec.temperature == 0.3


class TestBuildEnrichmentVariables:
    def test_basic_variables(self) -> None:
        spec = _make_image_spec()
        variables = build_enrichment_variables(spec)
        assert variables["motif_id"] == "sparkles"
        assert variables["category"] == "image_texture"
        assert variables["theme_id"] == "theme.holiday.traditional"
        assert variables["width"] == 1024
        assert variables["height"] == 1024

    def test_with_motif_description(self) -> None:
        spec = _make_image_spec()
        variables = build_enrichment_variables(
            spec,
            motif_description="Small bright glint shapes",
            motif_usage_notes="Use large forms",
        )
        assert variables["motif_description"] == "Small bright glint shapes"
        assert variables["motif_usage_notes"] == "Use large forms"

    def test_with_builtin_prompt(self) -> None:
        spec = _make_image_spec()
        variables = build_enrichment_variables(spec, builtin_prompt="Create a sparkle overlay...")
        assert variables["builtin_prompt"] == "Create a sparkle overlay..."

    def test_scene_context_passed(self) -> None:
        spec = _make_image_spec()
        variables = build_enrichment_variables(spec)
        assert variables["scene_context"] == ["Traditional Christmas feel"]

    def test_narrative_spec_uses_subject_path(self) -> None:
        """Narrative specs should populate narrative_subject instead of motif_id."""
        spec = AssetSpec(
            spec_id="asset_image_cutout_nose_glow",
            category=AssetCategory.IMAGE_CUTOUT,
            theme_id="theme.narrative",
            section_ids=["intro_1"],
            scene_context=["Rudolph's nose reveal"],
            narrative_subject="Reindeer with glowing red nose",
            narrative_description="Bold silhouette with warm red glow",
            color_guidance="Warm red-orange",
            mood="warm",
        )
        variables = build_enrichment_variables(spec)
        # Should use narrative path
        assert variables["narrative_subject"] == "Reindeer with glowing red nose"
        assert variables["narrative_description"] == "Bold silhouette with warm red glow"
        assert variables["color_guidance"] == "Warm red-orange"
        assert variables["mood"] == "warm"
        assert "motif_id" not in variables  # No motif in narrative path

    def test_effect_spec_uses_motif_path(self) -> None:
        """Effect specs should have narrative_subject=None and motif_id populated."""
        spec = _make_image_spec()
        variables = build_enrichment_variables(spec)
        assert variables.get("narrative_subject") is None
        assert variables["motif_id"] == "sparkles"


class TestEnrichSpec:
    @pytest.mark.asyncio
    async def test_successful_enrichment(self) -> None:
        spec = _make_image_spec()
        enricher_spec = build_enricher_spec()

        enriched = EnrichedPrompt(
            prompt="A festive Christmas sparkle pattern with bold star shapes in gold and white.",
            negative_prompt="text, logos, watermarks, thin lines",
        )
        mock_runner = AsyncMock()
        mock_runner.run.return_value = _success_result(enriched)

        result = await enrich_spec(spec, mock_runner, enricher_spec, motif_description="Sparkles")

        assert result.prompt is not None
        assert "sparkle" in result.prompt.lower()
        assert result.negative_prompt is not None
        assert result.spec_id == spec.spec_id  # Same identity
        mock_runner.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_enrichment_preserves_spec_fields(self) -> None:
        spec = _make_image_spec()
        enricher_spec = build_enricher_spec()

        enriched = EnrichedPrompt(
            prompt="A festive Christmas sparkle pattern with bold star shapes in gold.",
            negative_prompt="text, logos, watermarks",
        )
        mock_runner = AsyncMock()
        mock_runner.run.return_value = _success_result(enriched)

        result = await enrich_spec(spec, mock_runner, enricher_spec)

        assert result.motif_id == "sparkles"
        assert result.category == AssetCategory.IMAGE_TEXTURE
        assert result.theme_id == "theme.holiday.traditional"

    @pytest.mark.asyncio
    async def test_bad_return_type_raises(self) -> None:
        spec = _make_image_spec()
        enricher_spec = build_enricher_spec()

        mock_runner = AsyncMock()
        mock_runner.run.return_value = _success_result({"prompt": "bad type"})

        with pytest.raises(RuntimeError, match="unexpected type"):
            await enrich_spec(spec, mock_runner, enricher_spec)

    @pytest.mark.asyncio
    async def test_failed_agent_result_raises(self) -> None:
        spec = _make_image_spec()
        enricher_spec = build_enricher_spec()

        mock_runner = AsyncMock()
        mock_runner.run.return_value = _failure_result("LLM call timed out")

        with pytest.raises(RuntimeError, match="Enricher failed"):
            await enrich_spec(spec, mock_runner, enricher_spec)
