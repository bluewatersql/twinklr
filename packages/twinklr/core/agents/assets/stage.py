"""Asset creation pipeline stage.

Async-first implementation that integrates extraction, enrichment,
generation, and cataloging into a single pipeline stage.
Runs after the aggregate stage.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from twinklr.core.agents._paths import AGENTS_BASE_PATH
from twinklr.core.agents.assets.catalog import (
    check_reuse,
    load_catalog,
    save_catalog,
)
from twinklr.core.agents.assets.generator import generate_asset
from twinklr.core.agents.assets.image_client import OpenAIImageClient
from twinklr.core.agents.assets.models import (
    AssetSpec,
    AssetStatus,
    CatalogEntry,
)
from twinklr.core.agents.assets.prompt_enricher import (
    build_enricher_spec,
    enrich_spec,
)
from twinklr.core.agents.assets.request_extractor import extract_asset_specs
from twinklr.core.agents.assets.text_renderer import TextRenderer
from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.audio.lyrics.models import LyricContextModel
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.pipeline.result import StageResult, failure_result, success_result
from twinklr.core.pipeline.stage import resolve_typed_input
from twinklr.core.sequencer.planning.group_plan import GroupPlanSet
from twinklr.core.sequencer.theming.catalog import MOTIF_REGISTRY

logger = logging.getLogger(__name__)


class AssetCreationStage:
    """Pipeline stage: extract, enrich, generate, and catalog assets.

    This is a pass-through stage: the AssetCatalog is stored in context
    state (``asset_catalog``) and the original GroupPlanSet is returned
    as output so downstream stages receive the plan unchanged.

    Input: GroupPlanSet (or dict with key "aggregate")
    Output: GroupPlanSet (pass-through; catalog in context state)

    Example:
        >>> stage = AssetCreationStage()
        >>> result = await stage.execute(group_plan_set, context)
        >>> if result.success:
        ...     plan = result.output  # GroupPlanSet (unchanged)
        ...     catalog = context.get_state("asset_catalog")
    """

    def __init__(
        self,
        *,
        text_renderer: TextRenderer | None = None,
    ) -> None:
        """Initialize asset creation stage.

        Args:
            text_renderer: Optional custom text renderer. Defaults to TextRenderer().
        """
        self._text_renderer = text_renderer or TextRenderer()

    @property
    def name(self) -> str:
        """Stage name for logging."""
        return "asset_creation"

    async def execute(
        self,
        input: GroupPlanSet | dict[str, Any],
        context: PipelineContext,
    ) -> StageResult[GroupPlanSet]:
        """Execute the full asset creation pipeline.

        The catalog is stored in ``context.state["asset_catalog"]`` and
        the original GroupPlanSet is returned as output (pass-through).

        Args:
            input: GroupPlanSet directly, or dict with "aggregate"
                (GroupPlanSet) and optionally "lyrics".  When a GroupPlanSet
                is passed directly, lyric context is read from
                ``context.state["lyric_context"]``.
            context: Pipeline context with provider, session, output_dir.

        Returns:
            StageResult containing the original GroupPlanSet (pass-through).
        """
        try:
            plan_set, extras = resolve_typed_input(input, GroupPlanSet, "aggregate")
            lyric_context: LyricContextModel | None = extras.get("lyrics") or context.get_state(
                "lyric_context"
            )

            # Determine output paths
            assets_dir = self._resolve_assets_dir(context)
            catalog_path = assets_dir / "asset_catalog.json"

            # Load existing catalog for reuse checking
            catalog = load_catalog(catalog_path)
            source_plan_id = plan_set.plan_set_id

            # Step 1: Extract specs
            specs = extract_asset_specs(plan_set, lyric_context)
            logger.info("Extracted %d asset specs", len(specs))
            context.add_metric("asset_specs_total", len(specs))

            # Step 2: Check reuse, separate cached vs new
            new_specs = []
            cached_entries: list[CatalogEntry] = []

            for spec in specs:
                # Text specs without text_content or image specs without prompt
                # can't be checked for reuse yet (prompt not set)
                if spec.category.is_text() and spec.text_content:
                    existing = check_reuse(catalog, spec)
                    if existing:
                        cached_entry = existing.model_copy(update={"status": AssetStatus.CACHED})
                        cached_entries.append(cached_entry)
                        continue
                new_specs.append(spec)

            logger.info(
                "%d specs to generate, %d cached",
                len(new_specs),
                len(cached_entries),
            )

            # Step 3: Enrich image specs via LLM (concurrent)
            enricher_agent_spec = build_enricher_spec()
            runner = AsyncAgentRunner(
                provider=context.provider,
                prompt_base_path=AGENTS_BASE_PATH,
                llm_logger=context.llm_logger,
            )

            enrichment_sem = asyncio.Semaphore(5)
            image_specs_to_enrich = [s for s in new_specs if s.category.is_image()]
            non_image_specs = [s for s in new_specs if not s.category.is_image()]

            async def _enrich_one(spec: AssetSpec) -> AssetSpec:
                async with enrichment_sem:
                    motif_desc = None
                    motif_notes = None
                    if spec.motif_id:
                        try:
                            motif_def = MOTIF_REGISTRY.get(spec.motif_id)
                            motif_desc = motif_def.description
                            motif_notes = motif_def.usage_notes
                        except Exception:
                            logger.debug("Motif %s not in registry", spec.motif_id)
                    return await enrich_spec(
                        spec,
                        runner,
                        enricher_agent_spec,
                        motif_description=motif_desc,
                        motif_usage_notes=motif_notes,
                    )

            enriched_images = list(
                await asyncio.gather(*[_enrich_one(s) for s in image_specs_to_enrich])
            )

            # Check reuse with enriched prompts
            enriched_specs: list[AssetSpec] = []
            for enriched in enriched_images:
                existing = check_reuse(catalog, enriched)
                if existing:
                    cached_entry = existing.model_copy(update={"status": AssetStatus.CACHED})
                    cached_entries.append(cached_entry)
                else:
                    enriched_specs.append(enriched)
            enriched_specs.extend(non_image_specs)

            # Step 4: Generate assets (concurrent)
            image_client = self._build_image_client(context)
            generation_sem = asyncio.Semaphore(5)

            async def _generate_one(spec: AssetSpec) -> CatalogEntry:
                async with generation_sem:
                    return await generate_asset(
                        spec,
                        assets_dir,
                        image_client=image_client,
                        text_renderer=self._text_renderer,
                        source_plan_id=source_plan_id,
                    )

            new_entries = list(await asyncio.gather(*[_generate_one(s) for s in enriched_specs]))

            # Step 5: Merge into catalog
            all_entries = cached_entries + new_entries
            catalog.merge(all_entries)

            # Step 6: Save catalog
            save_catalog(catalog, catalog_path)

            # Metrics
            created = sum(1 for e in all_entries if e.status == AssetStatus.CREATED)
            cached = sum(1 for e in all_entries if e.status == AssetStatus.CACHED)
            failed = sum(1 for e in all_entries if e.status == AssetStatus.FAILED)
            context.add_metric("assets_created", created)
            context.add_metric("assets_cached", cached)
            context.add_metric("assets_failed", failed)

            logger.info(
                "Asset creation complete: %d created, %d cached, %d failed",
                created,
                cached,
                failed,
            )

            # Store catalog in context state for downstream stages
            context.set_state("asset_catalog", catalog)

            # Pass-through: return the original GroupPlanSet unchanged
            return success_result(plan_set, stage_name=self.name)

        except Exception as e:
            logger.exception("Asset creation failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)

    def _resolve_assets_dir(self, context: PipelineContext) -> Path:
        """Resolve the assets output directory.

        Args:
            context: Pipeline context.

        Returns:
            Path to assets/ directory.
        """
        if context.output_dir:
            return context.output_dir / "assets"
        return Path("assets")

    def _build_image_client(self, context: PipelineContext) -> OpenAIImageClient | None:
        """Build an OpenAI image client from session.

        Args:
            context: Pipeline context with session.

        Returns:
            OpenAIImageClient or None if no OpenAI client available.
        """
        try:
            client = _create_openai_client()
            return OpenAIImageClient(client)
        except Exception:
            logger.warning("Could not create OpenAI image client")
            return None


def _create_openai_client() -> Any:
    """Create an AsyncOpenAI client instance. Separated for testability."""
    from openai import AsyncOpenAI

    return AsyncOpenAI()
