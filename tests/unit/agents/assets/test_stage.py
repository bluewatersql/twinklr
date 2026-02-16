"""Tests for AssetCreationStage pipeline integration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from twinklr.core.agents.assets.models import AssetCatalog, EnrichedPrompt
from twinklr.core.agents.assets.stage import AssetCreationStage
from twinklr.core.agents.assets.text_renderer import TextRenderer
from twinklr.core.agents.result import AgentResult
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.sequencer.planning.group_plan import (
    GroupPlanSet,
    LanePlan,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.planning.models import PaletteRef
from twinklr.core.sequencer.theming import ThemeRef
from twinklr.core.sequencer.vocabulary import GPBlendMode, GPTimingDriver, LaneKind


def _make_plan_set() -> GroupPlanSet:
    section = SectionCoordinationPlan(
        section_id="intro_1",
        theme=ThemeRef(theme_id="theme.holiday.traditional", scope="SECTION"),
        motif_ids=["sparkles"],
        palette=PaletteRef(palette_id="core.christmas_traditional"),
        lane_plans=[
            LanePlan(
                lane=LaneKind.BASE,
                target_roles=["MEGA_TREE"],
                timing_driver=GPTimingDriver.BEATS,
                blend_mode=GPBlendMode.ADD,
            )
        ],
        planning_notes="Traditional Christmas feel",
    )
    return GroupPlanSet(
        plan_set_id="test_plan",
        section_plans=[section],
    )


def _mock_context(tmp_path: Path) -> PipelineContext:
    """Create a mock pipeline context."""
    mock_session = MagicMock()
    mock_session.app_config = MagicMock()
    mock_session.job_config = MagicMock()
    mock_session.llm_provider = MagicMock()
    mock_session.agent_cache = MagicMock()
    mock_session.llm_logger = MagicMock()

    ctx = PipelineContext(
        session=mock_session,
        output_dir=tmp_path,
    )
    return ctx


class TestAssetCreationStage:
    def test_name(self) -> None:
        stage = AssetCreationStage()
        assert stage.name == "asset_creation"

    @pytest.mark.asyncio
    async def test_execute_extracts_and_generates_text(self, tmp_path: Path) -> None:
        """Test that the stage extracts specs and generates text assets
        (skipping image generation which requires real API).
        """
        stage = AssetCreationStage(text_renderer=TextRenderer())
        context = _mock_context(tmp_path)
        plan_set = _make_plan_set()

        # Mock the enricher to avoid real LLM calls
        mock_enriched = EnrichedPrompt(
            prompt="A festive sparkle pattern with bold gold star shapes on a dark background.",
            negative_prompt="text, logos, watermarks, thin lines",
        )

        with (
            patch("twinklr.core.agents.assets.stage.AsyncAgentRunner") as MockRunner,
            patch("twinklr.core.agents.assets.stage._create_openai_client") as mock_create_client,
        ):
            mock_runner_instance = AsyncMock()
            mock_runner_instance.run.return_value = AgentResult(
                success=True, data=mock_enriched, duration_seconds=0.1, tokens_used=50
            )
            MockRunner.return_value = mock_runner_instance

            # Mock AsyncOpenAI client to return valid results
            import base64
            from io import BytesIO

            from PIL import Image

            mock_openai = MagicMock()

            async def fake_api_generate(**kwargs):  # type: ignore[no-untyped-def]
                """Simulate AsyncOpenAI images.generate."""
                img = Image.new("RGB", (256, 256), "red")
                buf = BytesIO()
                img.save(buf, "PNG")
                b64_data = base64.b64encode(buf.getvalue()).decode()

                data_item = MagicMock()
                data_item.b64_json = b64_data
                resp = MagicMock()
                resp.data = [data_item]
                return resp

            mock_openai.images = MagicMock()
            mock_openai.images.generate = AsyncMock(side_effect=fake_api_generate)
            mock_create_client.return_value = mock_openai

            result = await stage.execute(
                {"aggregate": plan_set, "lyrics": None},
                context,
            )

        assert result.success
        # Stage is pass-through: output is the original GroupPlanSet
        assert isinstance(result.output, GroupPlanSet)
        assert result.output.plan_set_id == "test_plan"
        # Catalog stored in context state
        catalog = context.get_state("asset_catalog")
        assert isinstance(catalog, AssetCatalog)
        assert len(catalog.entries) >= 1  # At least the text banner

    @pytest.mark.asyncio
    async def test_execute_with_no_plan_fails(self, tmp_path: Path) -> None:
        stage = AssetCreationStage()
        context = _mock_context(tmp_path)

        result = await stage.execute({}, context)
        assert not result.success

    @pytest.mark.asyncio
    async def test_metrics_tracked(self, tmp_path: Path) -> None:
        """Verify the stage tracks metrics."""
        stage = AssetCreationStage(text_renderer=TextRenderer())
        context = _mock_context(tmp_path)
        plan_set = _make_plan_set()

        mock_enriched = EnrichedPrompt(
            prompt="A festive sparkle pattern with bold gold star shapes on background.",
            negative_prompt="text, logos, watermarks",
        )

        with (
            patch("twinklr.core.agents.assets.stage.AsyncAgentRunner") as MockRunner,
            patch("twinklr.core.agents.assets.stage._create_openai_client") as mock_create_client,
        ):
            mock_runner_instance = AsyncMock()
            mock_runner_instance.run.return_value = AgentResult(
                success=True, data=mock_enriched, duration_seconds=0.1, tokens_used=50
            )
            MockRunner.return_value = mock_runner_instance

            import base64
            from io import BytesIO

            from PIL import Image

            mock_openai = MagicMock()

            async def fake_api_generate(**kwargs):  # type: ignore[no-untyped-def]
                img = Image.new("RGB", (256, 256), "red")
                buf = BytesIO()
                img.save(buf, "PNG")
                b64_data = base64.b64encode(buf.getvalue()).decode()

                data_item = MagicMock()
                data_item.b64_json = b64_data
                resp = MagicMock()
                resp.data = [data_item]
                return resp

            mock_openai.images = MagicMock()
            mock_openai.images.generate = AsyncMock(side_effect=fake_api_generate)
            mock_create_client.return_value = mock_openai

            await stage.execute(
                {"aggregate": plan_set, "lyrics": None},
                context,
            )

        assert "asset_specs_total" in context.metrics
        assert context.metrics["asset_specs_total"] >= 1

    def test_build_image_client_prefers_session_provider(self, tmp_path: Path) -> None:
        """Image client should reuse provider async client when available."""
        stage = AssetCreationStage()
        context = _mock_context(tmp_path)
        provider_async_client = MagicMock()
        context.session.llm_provider = MagicMock(_async_client=provider_async_client)

        with patch("twinklr.core.agents.assets.stage._create_openai_client") as create_client:
            image_client = stage._build_image_client(context)

        assert image_client is not None
        assert image_client._client is provider_async_client
        create_client.assert_not_called()
