"""Guarded asset creation pipeline stage."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import logging
from pathlib import Path
from typing import Any

from twinklr.core.agents._paths import AGENTS_BASE_PATH
from twinklr.core.agents.assets.catalog import (
    check_reuse,
    check_reuse_by_spec_id,
    compute_prompt_hash,
    load_catalog,
    save_catalog,
)
from twinklr.core.agents.assets.generator import build_output_path, generate_asset
from twinklr.core.agents.assets.image_client import OpenAIImageClient
from twinklr.core.agents.assets.models import (
    AssetCatalog,
    AssetRunSummary,
    AssetSpec,
    AssetStatus,
    CatalogEntry,
    ImageRequestBudgetPolicy,
)
from twinklr.core.agents.assets.prompt_enricher import build_enricher_spec, enrich_spec
from twinklr.core.agents.assets.request_extractor import extract_asset_specs
from twinklr.core.agents.assets.text_renderer import TextRenderer
from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.audio.lyrics.models import LyricContextModel
from twinklr.core.config.models import AssetGenerationConfig
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.pipeline.result import StageResult, failure_result, success_result
from twinklr.core.pipeline.stage import resolve_typed_input
from twinklr.core.sequencer.planning.group_plan import GroupPlanSet
from twinklr.core.sequencer.theming.catalog import MOTIF_REGISTRY, ItemNotFoundError

logger = logging.getLogger(__name__)


class AssetCreationStage:
    """Extract, enrich, generate, and durably catalog opt-in display assets."""

    def __init__(
        self,
        config: AssetGenerationConfig | None = None,
        *,
        text_renderer: TextRenderer | None = None,
    ) -> None:
        self._config = config or AssetGenerationConfig()
        self._text_renderer = text_renderer or TextRenderer()

    @property
    def name(self) -> str:
        return "asset_creation"

    async def execute(
        self,
        input: GroupPlanSet | dict[str, Any],
        context: PipelineContext,
    ) -> StageResult[GroupPlanSet]:
        """Run one capped batch; retain every completed sibling in the catalog."""
        try:
            if not self._config.enabled:
                raise ValueError("Asset generation is disabled; set assets.enabled=true")
            plan_set, extras = resolve_typed_input(input, GroupPlanSet, "aggregate")
            lyric_context: LyricContextModel | None = extras.get("lyrics") or context.get_state(
                "lyric_context"
            )
            assets_dir = self._resolve_assets_dir(context)
            catalog_path = assets_dir / "asset_catalog.json"
            catalog = load_catalog(catalog_path)
            context.set_state("asset_base_path", assets_dir)

            specs = extract_asset_specs(plan_set, lyric_context)
            context.add_metric("asset_specs_total", len(specs))
            new_specs: list[AssetSpec] = []
            cached_entries: list[CatalogEntry] = []
            for spec in specs:
                existing = (
                    check_reuse(
                        catalog,
                        spec,
                        assets_dir=assets_dir,
                        source_plan_id=plan_set.plan_set_id,
                    )
                    if spec.category.is_text() and spec.text_content
                    else (
                        check_reuse_by_spec_id(
                            catalog,
                            spec,
                            assets_dir=assets_dir,
                            source_plan_id=plan_set.plan_set_id,
                        )
                        if spec.category.is_image()
                        else None
                    )
                )
                if existing is None:
                    build_output_path(spec, assets_dir)
                    new_specs.append(spec)
                else:
                    cached_entries.append(
                        existing.model_copy(update={"status": AssetStatus.CACHED})
                    )

            pending_images = [spec for spec in new_specs if spec.category.is_image()]
            pending_other = [spec for spec in new_specs if not spec.category.is_image()]
            budget = ImageRequestBudgetPolicy(
                max_requests=self._config.max_image_requests_per_run,
                estimated_usd_per_request=self._config.estimated_image_usd_per_request,
            )
            request_budget = budget.authorize(len(pending_images))
            allowed_images = pending_images[: request_budget.authorized_requests]
            skipped_specs = pending_images[request_budget.authorized_requests :]
            estimated_usd = request_budget.reserved_usd

            if self._config.dry_run:
                summary = AssetRunSummary(
                    cached=len(cached_entries),
                    skipped=len(skipped_specs),
                    dry_run=True,
                    estimated_image_usd=estimated_usd,
                    would_generate=[spec.spec_id for spec in [*allowed_images, *pending_other]],
                    request_budget=request_budget,
                )
                self._publish(context, summary, catalog)
                return success_result(plan_set, stage_name=self.name)

            image_client: OpenAIImageClient | None = None
            if allowed_images:
                image_client = self._build_image_client(context)

            enricher_spec = build_enricher_spec(
                config=context.job_config.agent.asset_enricher_agent
            )
            runner = AsyncAgentRunner(
                provider=context.provider,
                prompt_base_path=AGENTS_BASE_PATH,
                llm_logger=context.llm_logger,
            )
            enrichment_sem = asyncio.Semaphore(5)

            motif_contexts: list[tuple[str | None, str | None]] = []
            for spec in allowed_images:
                motif_description = None
                motif_notes = None
                if spec.motif_id:
                    try:
                        motif = MOTIF_REGISTRY.get(spec.motif_id)
                        motif_description = motif.description
                        motif_notes = motif.usage_notes
                    except ItemNotFoundError:
                        logger.debug("Motif %s not in registry", spec.motif_id)
                motif_contexts.append((motif_description, motif_notes))

            async def enrich_one(
                spec: AssetSpec,
                motif_description: str | None,
                motif_notes: str | None,
            ) -> AssetSpec:
                async with enrichment_sem:
                    return await enrich_spec(
                        spec,
                        runner,
                        enricher_spec,
                        motif_description=motif_description,
                        motif_usage_notes=motif_notes,
                    )

            enrichment_results = await asyncio.gather(
                *(
                    enrich_one(spec, motif_description, motif_notes)
                    for spec, (motif_description, motif_notes) in zip(
                        allowed_images, motif_contexts, strict=True
                    )
                ),
                return_exceptions=True,
            )
            ready: list[AssetSpec] = list(pending_other)
            enrichment_failures: list[CatalogEntry] = []
            for original, result in zip(allowed_images, enrichment_results, strict=True):
                if isinstance(result, BaseException):
                    enrichment_failures.append(
                        self._failed_entry(
                            original,
                            assets_dir,
                            plan_set.plan_set_id,
                            f"Prompt enrichment failed: {result}",
                        )
                    )
                else:
                    existing = check_reuse(
                        catalog,
                        result,
                        assets_dir=assets_dir,
                        source_plan_id=plan_set.plan_set_id,
                    )
                    if existing is None:
                        ready.append(result)
                    else:
                        cached_entries.append(
                            existing.model_copy(update={"status": AssetStatus.CACHED})
                        )

            for entry in enrichment_failures:
                catalog.merge([entry])
                save_catalog(catalog, catalog_path)

            persistence_lock = asyncio.Lock()

            async def generate_and_persist(spec: AssetSpec) -> CatalogEntry:
                entry = await generate_asset(
                    spec,
                    assets_dir,
                    image_client=image_client,
                    text_renderer=self._text_renderer,
                    source_plan_id=plan_set.plan_set_id,
                )
                async with persistence_lock:
                    catalog.merge([entry])
                    save_catalog(catalog, catalog_path)
                return entry

            generation_results = await asyncio.gather(
                *(generate_and_persist(spec) for spec in ready), return_exceptions=True
            )
            generated: list[CatalogEntry] = []
            for spec, generation_result in zip(ready, generation_results, strict=True):
                if isinstance(generation_result, BaseException):
                    entry = self._failed_entry(
                        spec,
                        assets_dir,
                        plan_set.plan_set_id,
                        f"Generation failed: {generation_result}",
                    )
                    catalog.merge([entry])
                    save_catalog(catalog, catalog_path)
                    generated.append(entry)
                else:
                    generated.append(generation_result)

            all_run_entries = [*cached_entries, *enrichment_failures, *generated]
            generated_images = [entry for entry in generated if entry.spec.category.is_image()]
            usage_reported_requests = sum(
                entry.image_usage is not None for entry in generated_images
            )
            priced_images = [
                entry.image_cost.actual_image_usd
                for entry in generated_images
                if entry.image_cost is not None
            ]
            actual_image_usd = (
                sum(priced_images)
                if len(priced_images) == request_budget.authorized_requests
                and request_budget.authorized_requests > 0
                else None
            )
            summary = AssetRunSummary(
                created=sum(e.status == AssetStatus.CREATED for e in all_run_entries),
                cached=sum(e.status == AssetStatus.CACHED for e in all_run_entries),
                failed=sum(e.status == AssetStatus.FAILED for e in all_run_entries),
                skipped=len(skipped_specs),
                estimated_image_usd=estimated_usd,
                request_budget=request_budget.with_actual_cost(
                    actual_image_usd,
                    usage_reported_requests=usage_reported_requests,
                ),
            )
            self._publish(context, summary, catalog)
            return success_result(plan_set, stage_name=self.name)
        except Exception as error:
            logger.exception("Asset creation failed", exc_info=error)
            return failure_result(str(error), stage_name=self.name)

    @staticmethod
    def _publish(context: PipelineContext, summary: AssetRunSummary, catalog: AssetCatalog) -> None:
        context.set_state("asset_catalog", catalog)
        context.set_state("asset_run_summary", summary)
        context.add_metric("assets_created", summary.created)
        context.add_metric("assets_cached", summary.cached)
        context.add_metric("assets_failed", summary.failed)
        context.add_metric("assets_skipped", summary.skipped)
        context.add_metric("assets_estimated_image_usd", summary.estimated_image_usd)

    def _resolve_assets_dir(self, context: PipelineContext) -> Path:
        configured = self._config.asset_base_path
        if configured:
            path = Path(configured)
            if not path.is_absolute():
                config_dir = context.get_state("job_config_dir")
                path = Path(config_dir) / path if config_dir else path
            return path.resolve()
        if context.output_dir:
            return context.output_dir.parent / "shared" / "assets"
        return Path("assets").resolve()

    def _build_image_client(self, context: PipelineContext) -> OpenAIImageClient:
        provider = context.provider
        if not provider.supports_image_generation:
            raise ValueError(
                "Asset image generation requires the OpenAI provider; "
                f"configured provider is {provider.provider_type.value}"
            )
        return OpenAIImageClient(
            provider,
            model=context.job_config.agent.image_model,
            quality=self._config.image_quality,
        )

    @staticmethod
    def _failed_entry(
        spec: AssetSpec,
        assets_dir: Path,
        source_plan_id: str,
        error: str,
    ) -> CatalogEntry:
        output = build_output_path(spec, assets_dir)
        return CatalogEntry(
            asset_id=spec.spec_id,
            spec=spec,
            file_path=output.relative_to(assets_dir).as_posix(),
            content_hash="",
            status=AssetStatus.FAILED,
            width=spec.width,
            height=spec.height,
            file_size_bytes=0,
            created_at=datetime.now(UTC).isoformat(),
            source_plan_id=source_plan_id,
            generation_model="none",
            prompt_hash=compute_prompt_hash(spec),
            error=error,
        )
