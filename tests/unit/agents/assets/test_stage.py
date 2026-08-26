"""Public-seam tests for the guarded AssetCreationStage."""

from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image
import pytest

from twinklr.core.agents.assets.models import (
    AssetCatalog,
    AssetCategory,
    AssetRunSummary,
    AssetSpec,
    AssetStatus,
    CatalogEntry,
    EnrichedPrompt,
)
from twinklr.core.agents.assets.stage import AssetCreationStage
from twinklr.core.agents.providers.base import (
    ImageGenerationResponse,
    ProviderType,
)
from twinklr.core.agents.providers.base import (
    ImageGenerationUsage as ProviderImageUsage,
)
from twinklr.core.agents.result import AgentResult
from twinklr.core.config.models import AgentOrchestrationConfig, AssetGenerationConfig, JobConfig
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.sequencer.planning.group_plan import (
    GroupPlanSet,
    LanePlan,
    NarrativeAssetDirective,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.planning.models import PaletteRef
from twinklr.core.sequencer.theming import ThemeRef
from twinklr.core.sequencer.vocabulary import (
    BackgroundMode,
    GPBlendMode,
    GPTimingDriver,
    LaneKind,
)


def _plan() -> GroupPlanSet:
    return GroupPlanSet(
        plan_set_id="song-a",
        section_plans=[
            SectionCoordinationPlan(
                section_id="intro",
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
            )
        ],
    )


def _narrative_plan() -> GroupPlanSet:
    directives = [
        NarrativeAssetDirective(
            directive_id=f"scene_{index}",
            subject=f"holiday scene {index}",
            category="image_texture",
            visual_description=f"A bold high-contrast holiday scene number {index}",
            story_context="A specific narrative moment in the song",
            section_ids=["intro"],
        )
        for index in range(4)
    ]
    base = _plan()
    return base.model_copy(
        update={
            "section_plans": [base.section_plans[0].model_copy(update={"motif_ids": []})],
            "narrative_assets": directives,
        }
    )


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", (1024, 1024), "red").save(buffer, "PNG")
    return buffer.getvalue()


def _context(tmp_path: Path, *, image_support: bool = True) -> PipelineContext:
    provider = MagicMock()
    provider.supports_image_generation = image_support
    provider.provider_type = ProviderType.OPENAI if image_support else ProviderType.ANTHROPIC
    provider.generate_image_async = AsyncMock(
        return_value=ImageGenerationResponse(image_bytes=_png_bytes(), model="gpt-image-2")
    )
    session = MagicMock()
    session.app_config = MagicMock()
    session.job_config = JobConfig(agent=AgentOrchestrationConfig())
    session.llm_provider = provider
    session.agent_cache = MagicMock()
    session.llm_logger = MagicMock()
    return PipelineContext(session=session, output_dir=tmp_path / "song-a")


def _runner_result() -> AgentResult:
    return AgentResult(
        success=True,
        data=EnrichedPrompt(
            prompt="A bold field of large golden sparkles for an LED display.",
            negative_prompt="text, logos, watermarks",
        ),
        duration_seconds=0.1,
        tokens_used=20,
    )


def test_job_image_model_changes_asset_client_request_owner(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context.session.job_config = JobConfig(
        agent=AgentOrchestrationConfig(image_model="configured-image-model")
    )

    client = AssetCreationStage(AssetGenerationConfig())._build_image_client(context)

    assert client.model == "configured-image-model"


def test_name() -> None:
    assert AssetCreationStage().name == "asset_creation"


@pytest.mark.asyncio
async def test_disabled_stage_fails_closed(tmp_path: Path) -> None:
    result = await AssetCreationStage().execute(_plan(), _context(tmp_path))
    assert not result.success
    assert "assets.enabled=true" in (result.error or "")


@pytest.mark.asyncio
async def test_dry_run_reports_without_provider_calls(tmp_path: Path) -> None:
    context = _context(tmp_path)
    stage = AssetCreationStage(AssetGenerationConfig(enabled=True, dry_run=True))
    result = await stage.execute(_plan(), context)
    assert result.success
    summary = context.get_state("asset_run_summary")
    assert isinstance(summary, AssetRunSummary)
    assert summary.dry_run
    assert summary.estimated_image_usd == pytest.approx(0.20)
    assert len(summary.would_generate) == 2
    assert summary.request_budget.requested_requests == 1
    assert summary.request_budget.authorized_requests == 1
    assert summary.request_budget.reserved_usd == pytest.approx(0.20)
    assert summary.request_budget.actual_image_usd is None
    context.provider.generate_image_async.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("config_path", "payload"),
    (
        ("job.assets", {"enabled": True, "dry_run": True}),
        ("job.assets.enabled", {"enabled": True, "dry_run": True}),
        ("job.assets.dry_run", {"enabled": True, "dry_run": True}),
        (
            "job.assets.asset_base_path",
            {"enabled": True, "dry_run": True, "asset_base_path": "custom-assets"},
        ),
    ),
    ids=(
        "job.assets",
        "job.assets.enabled",
        "job.assets.dry_run",
        "job.assets.asset_base_path",
    ),
)
async def test_asset_config_field_changes_asset_creation_stage_behavior(
    tmp_path: Path, config_path: str, payload: dict[str, object]
) -> None:
    """Each configurable asset path changes the production stage result or output root."""
    context = _context(tmp_path)
    config = AssetGenerationConfig.model_validate(payload)
    result = await AssetCreationStage(config).execute(_plan(), context)

    assert result.success, config_path
    summary = context.get_state("asset_run_summary")
    assert isinstance(summary, AssetRunSummary)
    assert summary.dry_run
    if config_path == "job.assets.asset_base_path":
        assert Path(context.get_state("asset_base_path")).name == "custom-assets"


@pytest.mark.asyncio
async def test_execute_persists_generated_and_text_assets(tmp_path: Path) -> None:
    context = _context(tmp_path)
    stage = AssetCreationStage(AssetGenerationConfig(enabled=True))
    with patch("twinklr.core.agents.assets.stage.AsyncAgentRunner") as runner_type:
        runner_type.return_value.run = AsyncMock(return_value=_runner_result())
        result = await stage.execute(_plan(), context)
    assert result.success
    catalog = context.get_state("asset_catalog")
    summary = context.get_state("asset_run_summary")
    assert isinstance(catalog, AssetCatalog)
    assert isinstance(summary, AssetRunSummary)
    assert summary.created == 2
    assert all(not Path(entry.file_path).is_absolute() for entry in catalog.entries)
    assert (tmp_path / "shared" / "assets" / "asset_catalog.json").is_file()


@pytest.mark.asyncio
async def test_non_openai_provider_fails_before_enrichment(tmp_path: Path) -> None:
    context = _context(tmp_path, image_support=False)
    stage = AssetCreationStage(AssetGenerationConfig(enabled=True))
    with patch("twinklr.core.agents.assets.stage.AsyncAgentRunner") as runner_type:
        result = await stage.execute(_plan(), context)
    assert not result.success
    assert "requires the OpenAI provider" in (result.error or "")
    runner_type.assert_not_called()


@pytest.mark.asyncio
async def test_unexpected_motif_registry_failure_is_not_swallowed(tmp_path: Path) -> None:
    context = _context(tmp_path)
    stage = AssetCreationStage(AssetGenerationConfig(enabled=True))
    with (
        patch("twinklr.core.agents.assets.stage.AsyncAgentRunner") as runner_type,
        patch(
            "twinklr.core.agents.assets.stage.MOTIF_REGISTRY.get",
            side_effect=RuntimeError("registry invariant broken"),
        ),
    ):
        runner_type.return_value.run = AsyncMock(return_value=_runner_result())
        result = await stage.execute(_plan(), context)

    assert not result.success
    assert "registry invariant broken" in (result.error or "")
    context.provider.generate_image_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_one_request_exposure_limits_provider_awaits(tmp_path: Path) -> None:
    context = _context(tmp_path)
    stage = AssetCreationStage(AssetGenerationConfig(enabled=True))
    with patch("twinklr.core.agents.assets.stage.AsyncAgentRunner") as runner_type:
        runner_type.return_value.run = AsyncMock(return_value=_runner_result())
        result = await stage.execute(_narrative_plan(), context)
    assert result.success
    summary = context.get_state("asset_run_summary")
    assert isinstance(summary, AssetRunSummary)
    assert summary.created == 2  # one conservatively reserved image plus deterministic title
    assert summary.skipped == 3
    assert summary.request_budget.requested_requests == 4
    assert summary.request_budget.authorized_requests == 1
    assert summary.request_budget.reservation_usd_per_request == pytest.approx(0.20)
    assert summary.request_budget.reserved_usd == pytest.approx(0.20)
    assert summary.request_budget.actual_image_usd is None
    assert summary.request_budget.actual_cost_status == "unavailable"
    assert summary.request_budget.estimate_exceeded is None
    assert context.provider.generate_image_async.await_count == 1


@pytest.mark.asyncio
async def test_trustworthy_reported_usage_populates_actual_cost(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context.provider.generate_image_async.return_value = ImageGenerationResponse(
        image_bytes=_png_bytes(),
        model="gpt-image-2",
        usage=ProviderImageUsage(
            input_tokens=100,
            input_text_tokens=100,
            input_image_tokens=0,
            output_tokens=196,
            output_text_tokens=0,
            output_image_tokens=196,
            total_tokens=296,
        ),
    )
    stage = AssetCreationStage(AssetGenerationConfig(enabled=True))
    with patch("twinklr.core.agents.assets.stage.AsyncAgentRunner") as runner_type:
        runner_type.return_value.run = AsyncMock(return_value=_runner_result())
        result = await stage.execute(_plan(), context)

    assert result.success
    summary = context.get_state("asset_run_summary")
    catalog = context.get_state("asset_catalog")
    assert isinstance(summary, AssetRunSummary)
    assert isinstance(catalog, AssetCatalog)
    assert summary.request_budget.actual_image_usd == pytest.approx(0.00638)
    assert summary.request_budget.actual_cost_status == "reported_within_estimate"
    assert summary.request_budget.estimate_exceeded is False
    image_entry = next(entry for entry in catalog.entries if entry.spec.category.is_image())
    assert image_entry.image_cost is not None
    assert image_entry.image_cost.pricing_as_of == "2026-08-26"


@pytest.mark.asyncio
async def test_reported_cost_over_estimate_is_surfaced_without_compliance_claim(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    context.provider.generate_image_async.return_value = ImageGenerationResponse(
        image_bytes=_png_bytes(),
        model="gpt-image-2",
        usage=ProviderImageUsage(
            input_tokens=100,
            input_text_tokens=100,
            input_image_tokens=0,
            output_tokens=10_000,
            output_text_tokens=0,
            output_image_tokens=10_000,
            total_tokens=10_100,
        ),
    )
    stage = AssetCreationStage(AssetGenerationConfig(enabled=True))
    with patch("twinklr.core.agents.assets.stage.AsyncAgentRunner") as runner_type:
        runner_type.return_value.run = AsyncMock(return_value=_runner_result())
        result = await stage.execute(_plan(), context)

    assert result.success
    summary = context.get_state("asset_run_summary")
    assert isinstance(summary, AssetRunSummary)
    assert summary.request_budget.actual_image_usd == pytest.approx(0.3005)
    assert summary.request_budget.actual_cost_status == "reported_exceeds_estimate"
    assert summary.request_budget.estimate_exceeded is True
    assert summary.request_budget.reserved_usd == pytest.approx(0.20)


@pytest.mark.asyncio
async def test_identical_prompts_are_song_scoped_and_same_song_replays_cache(
    tmp_path: Path,
) -> None:
    stage = AssetCreationStage(AssetGenerationConfig(enabled=True))
    song_a = _plan()
    song_b = song_a.model_copy(update={"plan_set_id": "song-b"})
    context_a = _context(tmp_path)
    context_b = _context(tmp_path)
    context_b.output_dir = tmp_path / "song-b"

    with patch("twinklr.core.agents.assets.stage.AsyncAgentRunner") as runner_type:
        runner_type.return_value.run = AsyncMock(return_value=_runner_result())
        first = await stage.execute(song_a, context_a)
        second = await stage.execute(song_b, context_b)

    assert first.success and second.success
    catalog = context_b.get_state("asset_catalog")
    assert isinstance(catalog, AssetCatalog)
    image_entries = [entry for entry in catalog.entries if entry.spec.category.is_image()]
    assert {entry.source_plan_id for entry in image_entries} == {"song-a", "song-b"}
    assert len({entry.asset_id for entry in image_entries}) == 2
    assert len({entry.file_path for entry in image_entries}) == 2
    assert context_a.provider.generate_image_async.await_count == 1
    assert context_b.provider.generate_image_async.await_count == 1

    replay_context = _context(tmp_path)
    replay_context.output_dir = tmp_path / "song-b-replay"
    with patch("twinklr.core.agents.assets.stage.AsyncAgentRunner") as runner_type:
        runner_type.return_value.run = AsyncMock()
        replay = await stage.execute(song_b, replay_context)
    assert replay.success
    replay_context.provider.generate_image_async.assert_not_awaited()
    runner_type.return_value.run.assert_not_awaited()
    replay_summary = replay_context.get_state("asset_run_summary")
    replay_catalog = replay_context.get_state("asset_catalog")
    assert isinstance(replay_summary, AssetRunSummary)
    assert isinstance(replay_catalog, AssetCatalog)
    assert replay_summary.created == 0
    assert replay_summary.cached == 2
    assert all(
        entry.status == AssetStatus.CREATED
        for entry in replay_catalog.entries
        if entry.source_plan_id == "song-b"
    )


@pytest.mark.asyncio
async def test_corrupt_cached_image_fails_before_provider_or_enrichment(tmp_path: Path) -> None:
    stage = AssetCreationStage(AssetGenerationConfig(enabled=True))
    first_context = _context(tmp_path)
    with patch("twinklr.core.agents.assets.stage.AsyncAgentRunner") as runner_type:
        runner_type.return_value.run = AsyncMock(return_value=_runner_result())
        first = await stage.execute(_plan(), first_context)
    assert first.success
    catalog = first_context.get_state("asset_catalog")
    assert isinstance(catalog, AssetCatalog)
    image_entry = next(entry for entry in catalog.entries if entry.spec.category.is_image())
    (tmp_path / "shared" / "assets" / image_entry.file_path).write_bytes(b"corrupt")

    replay_context = _context(tmp_path)
    with patch("twinklr.core.agents.assets.stage.AsyncAgentRunner") as runner_type:
        replay = await stage.execute(_plan(), replay_context)

    assert not replay.success
    assert "Cached image validation failed" in (replay.error or "")
    replay_context.provider.generate_image_async.assert_not_awaited()
    runner_type.assert_not_called()


@pytest.mark.asyncio
async def test_enrichment_failure_preserves_deterministic_text_sibling(tmp_path: Path) -> None:
    context = _context(tmp_path)
    stage = AssetCreationStage(AssetGenerationConfig(enabled=True))
    failed = AgentResult(
        success=False,
        error_message="one bad enrichment",
        duration_seconds=0.1,
        tokens_used=5,
    )
    with patch("twinklr.core.agents.assets.stage.AsyncAgentRunner") as runner_type:
        runner_type.return_value.run = AsyncMock(return_value=failed)
        result = await stage.execute(_narrative_plan(), context)
    assert result.success
    summary = context.get_state("asset_run_summary")
    catalog = context.get_state("asset_catalog")
    assert isinstance(summary, AssetRunSummary)
    assert isinstance(catalog, AssetCatalog)
    assert summary.created == 1  # deterministic title survives the one authorized image failure
    assert summary.failed == 1
    assert summary.skipped == 3
    context.provider.generate_image_async.assert_not_awaited()
    assert len(catalog.entries) == 2


@pytest.mark.asyncio
async def test_unexpected_nth_generation_failure_keeps_first_n_minus_one_durable(
    tmp_path: Path,
) -> None:
    """A four-task barrier proves three saves precede the fourth task's failure."""
    context = _context(tmp_path)
    stage = AssetCreationStage(AssetGenerationConfig(enabled=True))
    specs = [
        AssetSpec(
            spec_id=f"song-a:text:{index}",
            category=AssetCategory.TEXT_BANNER,
            theme_id="theme.holiday.traditional",
            section_ids=["intro"],
            background=BackgroundMode.TRANSPARENT,
            text_content=f"Title {index}",
            width=512,
            height=128,
        )
        for index in range(4)
    ]
    barrier = asyncio.Barrier(4)
    catalog_path = tmp_path / "shared" / "assets" / "asset_catalog.json"
    calls = 0
    durable_before_failure = 0

    async def controlled_generation(
        spec: AssetSpec, assets_dir: Path, **kwargs: object
    ) -> CatalogEntry:
        nonlocal calls, durable_before_failure
        calls += 1
        call_number = calls
        await barrier.wait()
        if call_number < 4:
            return CatalogEntry(
                asset_id=spec.spec_id,
                spec=spec,
                file_path=f"text/banners/completed-{call_number}.png",
                content_hash="abc",
                status=AssetStatus.CREATED,
                width=spec.width,
                height=spec.height,
                file_size_bytes=3,
                created_at="2026-08-26T00:00:00Z",
                source_plan_id="song-a",
                generation_model="pil",
                prompt_hash="hash",
            )
        while durable_before_failure < 3:
            if catalog_path.is_file():
                durable_before_failure = len(
                    AssetCatalog.model_validate_json(catalog_path.read_text()).entries
                )
            await asyncio.sleep(0)
        raise RuntimeError("unexpected fourth generation failure")

    with (
        patch("twinklr.core.agents.assets.stage.AsyncAgentRunner") as runner_type,
        patch("twinklr.core.agents.assets.stage.extract_asset_specs", return_value=specs),
        patch(
            "twinklr.core.agents.assets.stage.generate_asset",
            side_effect=controlled_generation,
        ),
    ):
        runner_type.return_value.run = AsyncMock(return_value=_runner_result())
        result = await stage.execute(_plan(), context)

    assert result.success
    catalog = context.get_state("asset_catalog")
    assert isinstance(catalog, AssetCatalog)
    assert calls == 4
    assert durable_before_failure == 3
    assert sum(entry.status == AssetStatus.CREATED for entry in catalog.entries) == 3
    assert sum(entry.status == AssetStatus.FAILED for entry in catalog.entries) == 1
    persisted = AssetCatalog.model_validate_json(
        (tmp_path / "shared" / "assets" / "asset_catalog.json").read_text()
    )
    assert len(persisted.entries) == 4
    assert [entry.status for entry in persisted.entries].count(AssetStatus.CREATED) == 3
    assert [entry.status for entry in persisted.entries].count(AssetStatus.FAILED) == 1
