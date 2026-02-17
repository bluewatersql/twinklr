#!/usr/bin/env python3
"""Demo harness for the Asset Creation Pipeline.

Loads an existing GroupPlanSet from artifacts and exercises the full pipeline:
1. Extract asset specs (deterministic)
2. Enrich image specs via LLM (optional — skipped in dry-run mode)
3. Generate assets (image → OpenAI, text → PIL)
4. Catalog results

Usage:
    # Dry-run (no API calls, text rendering only):
    uv run python scripts/demo_asset_pipeline.py

    # Full run with LLM enrichment + image generation:
    uv run --env-file .env -- python scripts/demo_asset_pipeline.py --live

    # Custom plan file:
    uv run --env-file .env -- python scripts/demo_asset_pipeline.py --live \\
        --plan artifacts/02_rudolph_the_red_nosed_reindeer/group_plan_set.json
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from twinklr.core.agents.assets.catalog import (
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
from twinklr.core.agents.audio.lyrics.models import (
    KeyPhrase,
    LyricContextModel,
    StoryBeat,
)
from twinklr.core.sequencer.planning.group_plan import (
    GroupPlanSet,
    LanePlan,
    NarrativeAssetDirective,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.planning.models import PaletteRef
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationPlan,
    GroupPlacement,
    PlanTarget,
)
from twinklr.core.sequencer.theming import ThemeRef
from twinklr.core.sequencer.theming.catalog import MOTIF_REGISTRY
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    GPBlendMode,
    GPTimingDriver,
    LaneKind,
)
from twinklr.core.sequencer.vocabulary.choreography import TargetType
from twinklr.core.sequencer.vocabulary.planning import PlanningTimeRef

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("demo.asset_pipeline")


# ---------------------------------------------------------------------------
# Console helpers
# ---------------------------------------------------------------------------


def print_header(title: str) -> None:
    width = max(len(title) + 4, 60)
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")


def print_section(title: str) -> None:
    print(f"\n--- {title} ---")


def print_spec(spec: AssetSpec, idx: int) -> None:
    is_narrative = spec.narrative_subject is not None
    if is_narrative:
        tag = "[NARR] "
    elif spec.category.is_image():
        tag = "[IMAGE]"
    elif spec.category.is_text():
        tag = "[TEXT] "
    else:
        tag = "[OTHER]"

    source = spec.narrative_subject[:20] if is_narrative else (spec.motif_id or "(none)")
    builtin = f"  builtin: {spec.matched_template_id}" if spec.matched_template_id else ""
    print(
        f"  {idx:>2}. {tag} {spec.spec_id:<45} "
        f"cat={spec.category.value:<15} src={source:<20} "
        f"{spec.width}x{spec.height}{builtin}"
    )
    if is_narrative and spec.narrative_description:
        desc = spec.narrative_description
        print(f"      narrative: {desc[:90]}{'...' if len(desc) > 90 else ''}")
    if spec.scene_context:
        for ctx in spec.scene_context[:2]:
            print(f"      context: {ctx[:80]}{'...' if len(ctx) > 80 else ''}")
    if spec.prompt:
        print(f"      prompt: {spec.prompt[:100]}{'...' if len(spec.prompt) > 100 else ''}")


def print_entry(entry: CatalogEntry) -> None:
    status_icon = {
        AssetStatus.CREATED: "OK",
        AssetStatus.CACHED: "CACHE",
        AssetStatus.FAILED: "FAIL",
    }
    icon = status_icon.get(entry.status, "?")
    size = f"{entry.file_size_bytes:,}B" if entry.file_size_bytes else "0B"
    print(
        f"  [{icon:>5}] {entry.asset_id:<45} "
        f"{entry.width}x{entry.height}  {size:<12} "
        f"model={entry.generation_model}"
    )
    if entry.error:
        print(f"         ERROR: {entry.error}")


# ---------------------------------------------------------------------------
# Synthetic lyric context (for Rudolph demo)
# ---------------------------------------------------------------------------


def build_rudolph_lyric_context() -> LyricContextModel:
    """Build a synthetic LyricContextModel for Rudolph the Red-Nosed Reindeer."""
    return LyricContextModel(
        has_lyrics=True,
        themes=["redemption", "inclusion", "Christmas magic"],
        mood_arc="playful → sympathetic → triumphant",
        genre_markers=["Christmas", "children's", "classic"],
        has_narrative=True,
        characters=["Rudolph", "Santa", "other reindeer"],
        story_beats=[
            StoryBeat(
                section_id="intro_1",
                timestamp_range=(0, 8000),
                beat_type="setup",
                description="Introduction of Rudolph's distinctive feature",
                visual_opportunity="Warm red glow builds from darkness, single spotlight effect",
            ),
            StoryBeat(
                section_id="verse_1",
                timestamp_range=(8000, 24000),
                beat_type="conflict",
                description="The other reindeer laugh and exclude Rudolph",
                visual_opportunity="Cool blues and isolation, scattered sparkles dimming",
            ),
            StoryBeat(
                section_id="bridge_1",
                timestamp_range=(24000, 36000),
                beat_type="setup",
                description="Foggy Christmas Eve, Santa needs help",
                visual_opportunity="Swirling mist/fog effect, building anticipation",
            ),
            StoryBeat(
                section_id="chorus_1",
                timestamp_range=(36000, 52000),
                beat_type="climax",
                description="Rudolph guides Santa's sleigh — triumph and acceptance",
                visual_opportunity="Full brightness explosion, radial rays, warm gold and red",
            ),
        ],
        key_phrases=[
            KeyPhrase(
                text="had a very shiny nose",
                timestamp_ms=4000,
                section_id="intro_1",
                visual_hint="Pulsing red-orange glow, organic warm light",
                emphasis="HIGH",
            ),
            KeyPhrase(
                text="you would even say it glows",
                timestamp_ms=8000,
                section_id="verse_1",
                visual_hint="Radial light burst from center point",
                emphasis="MED",
            ),
            KeyPhrase(
                text="won't you guide my sleigh tonight",
                timestamp_ms=32000,
                section_id="bridge_1",
                visual_hint="Sweeping beam cutting through fog/mist",
                emphasis="HIGH",
            ),
            KeyPhrase(
                text="then how the reindeer loved him",
                timestamp_ms=44000,
                section_id="chorus_1",
                visual_hint="Warm celebration burst, all elements synchronized",
                emphasis="MED",
            ),
            KeyPhrase(
                text="all of the other reindeer",
                timestamp_ms=12000,
                section_id="verse_1",
                visual_hint="Multiple silhouette shapes in cool blue tones",
                emphasis="LOW",
            ),
            KeyPhrase(
                text="used to laugh and call him names",
                timestamp_ms=16000,
                section_id="verse_1",
                visual_hint="Flickering, scattered elements, cold palette",
                emphasis="MED",
            ),
            KeyPhrase(
                text="go down in history",
                timestamp_ms=48000,
                section_id="chorus_1",
                visual_hint="Grand finale, maximum brightness, all channels full",
                emphasis="HIGH",
            ),
        ],
        recommended_visual_themes=[
            "warm red-gold glow (Rudolph's nose)",
            "cold-to-warm color transitions",
            "fog/mist clearing to brilliance",
        ],
        lyric_density="MED",
        vocal_coverage_pct=0.75,
    )


# ---------------------------------------------------------------------------
# Synthetic Rudolph GroupPlanSet (with narrative directives)
# ---------------------------------------------------------------------------


def build_rudolph_plan_set() -> GroupPlanSet:
    """Build a synthetic Rudolph GroupPlanSet with narrative asset directives.

    This exercises the full dual-source extraction path:
    - motif_ids → effect/abstract assets
    - narrative_assets → figurative/story assets
    """

    # -- Per-section narrative directives --
    intro_narratives = [
        NarrativeAssetDirective(
            directive_id="rudolph_glowing_nose",
            subject="Rudolph's glowing red nose — single warm light in darkness",
            category="image_cutout",
            visual_description=(
                "Bold silhouette of a reindeer nose with a bright red-orange glow, "
                "radiating warm concentric circles of light. Simple, iconic shape "
                "suitable for LED projection. High contrast on transparent background."
            ),
            story_context="Introduction of Rudolph's distinctive feature — the glowing red nose",
            emphasis="HIGH",
            color_guidance="Warm red-orange core, soft amber halos",
            mood="warm",
        ),
    ]

    verse_narratives = [
        NarrativeAssetDirective(
            directive_id="reindeer_silhouettes",
            subject="Group of reindeer silhouettes turning away from one figure",
            category="image_cutout",
            visual_description=(
                "Bold black silhouettes of 4-5 reindeer in profile, clustered "
                "together with body language suggesting exclusion. Clean, high-contrast "
                "shapes on transparent background, optimized for LED display."
            ),
            story_context="The other reindeer laugh and exclude Rudolph",
            emphasis="MED",
            color_guidance="Cool blue-grey silhouettes, cold moonlight tones",
            mood="cold",
        ),
        NarrativeAssetDirective(
            directive_id="lonely_rudolph",
            subject="Single small reindeer standing apart from the group",
            category="image_cutout",
            visual_description=(
                "Small reindeer silhouette standing alone, slightly dimmer than "
                "the others, with a faint red glow at the nose. Isolation conveyed "
                "through empty space. Bold shapes, clean edges for LED rendering."
            ),
            story_context="Rudolph is excluded and alone — sympathetic moment",
            emphasis="MED",
            color_guidance="Cool blue isolation, faint red warmth at nose",
            mood="lonely",
        ),
    ]

    bridge_narratives = [
        NarrativeAssetDirective(
            directive_id="foggy_christmas_eve",
            subject="Dense swirling fog on a dark winter night with distant light",
            category="image_texture",
            visual_description=(
                "Layered wisps of cool blue-grey fog swirling across a dark "
                "background. Subtle depth with lighter areas suggesting a distant "
                "glow. Tileable texture for LED matrix, smooth gradients acceptable "
                "for atmosphere."
            ),
            story_context="Foggy Christmas Eve — Santa needs help guiding the sleigh",
            emphasis="HIGH",
            color_guidance="Cool grey-blue fog, subtle distant amber hint",
            mood="mysterious",
        ),
        NarrativeAssetDirective(
            directive_id="santa_sleigh_silhouette",
            subject="Santa's sleigh and reindeer team silhouette against cloudy sky",
            category="image_cutout",
            visual_description=(
                "Bold silhouette of Santa in sleigh pulled by reindeer team, "
                "arcing across the image. Classic Christmas pose. High contrast "
                "on transparent background, clean vector-like edges for LED projection."
            ),
            story_context="Santa prepares for Christmas Eve flight but cannot see through the fog",
            emphasis="MED",
            color_guidance="Dark silhouette, hints of warm gold trim",
            mood="anticipation",
        ),
    ]

    chorus_narratives = [
        NarrativeAssetDirective(
            directive_id="rudolph_leading_sleigh",
            subject="Rudolph at the front of the sleigh team, nose blazing bright",
            category="image_cutout",
            visual_description=(
                "Dynamic silhouette of Rudolph leading Santa's sleigh team, "
                "his nose emitting a brilliant red-gold beam cutting through "
                "darkness. Full team visible behind. Bold, celebratory composition "
                "with radiating light lines from the nose."
            ),
            story_context="Rudolph guides Santa's sleigh — triumph and acceptance",
            emphasis="HIGH",
            color_guidance="Brilliant red-gold from nose, warm amber celebration tones",
            mood="triumphant",
        ),
        NarrativeAssetDirective(
            directive_id="celebration_burst",
            subject="Radiating celebration burst with stars and sparkles",
            category="image_texture",
            visual_description=(
                "Radial explosion of warm gold and red sparkles emanating from "
                "center. Stars and light rays fill the frame. Tileable, high-energy, "
                "maximum brightness celebration pattern for LED matrix."
            ),
            story_context="All the reindeer celebrate — Rudolph is accepted as hero",
            emphasis="HIGH",
            color_guidance="Warm gold, bright red, pure white sparkles",
            mood="triumphant",
        ),
    ]

    # -- Aggregate directives across sections (simulate aggregator) --
    all_directives_by_id: dict[str, NarrativeAssetDirective] = {}
    section_map: dict[str, list[str]] = {}

    for section_id, directives in [
        ("intro_1", intro_narratives),
        ("verse_1", verse_narratives),
        ("bridge_1", bridge_narratives),
        ("chorus_1", chorus_narratives),
    ]:
        for d in directives:
            if d.directive_id not in all_directives_by_id:
                all_directives_by_id[d.directive_id] = d
                section_map[d.directive_id] = []
            section_map[d.directive_id].append(section_id)

    aggregated_directives = [
        d.model_copy(update={"section_ids": section_map[d.directive_id]})
        for d in all_directives_by_id.values()
    ]

    # -- Build sections --
    def _lane(roles: list[str]) -> LanePlan:
        return LanePlan(
            lane=LaneKind.BASE,
            target_roles=roles,
            timing_driver=GPTimingDriver.BEATS,
            blend_mode=GPBlendMode.ADD,
            coordination_plans=[
                CoordinationPlan(
                    coordination_mode=CoordinationMode.UNIFIED,
                    targets=[PlanTarget(type=TargetType.GROUP, id="G1")],
                    placements=[
                        GroupPlacement(
                            placement_id="p1",
                            target=PlanTarget(type=TargetType.GROUP, id="G1"),
                            template_id="gtpl_test",
                            start=PlanningTimeRef(bar=1, beat=1),
                        )
                    ],
                )
            ],
        )

    sections = [
        SectionCoordinationPlan(
            section_id="intro_1",
            theme=ThemeRef(theme_id="theme.holiday.playful", scope="SECTION"),
            motif_ids=["warm_glow", "sparkles"],
            palette=PaletteRef(palette_id="core.christmas_warm"),
            lane_plans=[_lane(["MEGA_TREE", "HERO"])],
            narrative_assets=intro_narratives,
            planning_notes="Rudolph's nose reveal — warm red glow building from darkness",
        ),
        SectionCoordinationPlan(
            section_id="verse_1",
            theme=ThemeRef(theme_id="theme.holiday.playful", scope="SECTION"),
            motif_ids=["ice", "snowfall"],
            palette=PaletteRef(palette_id="core.christmas_cool"),
            lane_plans=[_lane(["OUTLINE", "WINDOWS", "ARCHES"])],
            narrative_assets=verse_narratives,
            planning_notes="Exclusion and loneliness — cool tones, scattered patterns",
        ),
        SectionCoordinationPlan(
            section_id="bridge_1",
            theme=ThemeRef(theme_id="theme.holiday.traditional", scope="SECTION"),
            motif_ids=["swirl", "fog_drift"],
            palette=PaletteRef(palette_id="core.christmas_traditional"),
            lane_plans=[_lane(["MEGA_TREE", "MATRIX"])],
            narrative_assets=bridge_narratives,
            planning_notes="Foggy Christmas Eve — building anticipation, atmospheric swirl",
        ),
        SectionCoordinationPlan(
            section_id="chorus_1",
            theme=ThemeRef(theme_id="theme.holiday.playful", scope="SECTION"),
            motif_ids=["radial_rays", "candy_stripes", "sparkles"],
            palette=PaletteRef(palette_id="core.christmas_warm"),
            lane_plans=[_lane(["HERO", "MEGA_TREE", "OUTLINE", "ARCHES"])],
            narrative_assets=chorus_narratives,
            planning_notes="Triumph! Rudolph leads the sleigh — maximum brightness celebration",
        ),
    ]

    return GroupPlanSet(
        plan_set_id="02_rudolph_the_red_nosed_reindeer",
        section_plans=sections,
        narrative_assets=aggregated_directives,
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


async def run_pipeline(
    plan_path: Path | None,
    output_dir: Path,
    *,
    live: bool = False,
    with_lyrics: bool = True,
    synthetic: bool = False,
) -> None:
    """Execute the asset creation pipeline demo."""

    print_header("Asset Creation Pipeline Demo")
    if synthetic:
        print("  Plan:       SYNTHETIC (Rudolph with narrative directives)")
    else:
        print(f"  Plan:       {plan_path}")
    print(f"  Output:     {output_dir}")
    print(f"  Mode:       {'LIVE (API calls enabled)' if live else 'DRY-RUN (text only, no API)'}")
    print(f"  Lyrics:     {'Synthetic Rudolph context' if with_lyrics else 'None'}")

    # -----------------------------------------------------------------------
    # Load plan
    # -----------------------------------------------------------------------
    print_section("Step 0: Load GroupPlanSet")
    if synthetic:
        plan_set = build_rudolph_plan_set()
        print(f"  Built synthetic plan: {plan_set.plan_set_id}")
    else:
        assert plan_path is not None
        raw = json.loads(plan_path.read_text(encoding="utf-8"))
        plan_set = GroupPlanSet.model_validate(raw)
        print(f"  Loaded plan: {plan_set.plan_set_id}")
    print(f"  Sections: {len(plan_set.section_plans)}")
    for sp in plan_set.section_plans:
        narr_count = len(sp.narrative_assets) if sp.narrative_assets else 0
        print(
            f"    - {sp.section_id}: motifs={sp.motif_ids}, "
            f"theme={sp.theme.theme_id}, narrative_directives={narr_count}"
        )
    if plan_set.narrative_assets:
        print(f"  Aggregated narrative directives: {len(plan_set.narrative_assets)}")
        for nd in plan_set.narrative_assets:
            print(f"    - {nd.directive_id}: {nd.subject[:60]}... [{nd.emphasis}]")

    # -----------------------------------------------------------------------
    # Build lyric context
    # -----------------------------------------------------------------------
    lyric_context: LyricContextModel | None = None
    if with_lyrics:
        print_section("Step 0b: Build Lyric Context")
        lyric_context = build_rudolph_lyric_context()
        print(f"  Themes: {lyric_context.themes}")
        print(f"  Characters: {lyric_context.characters}")
        print(f"  Key phrases: {len(lyric_context.key_phrases)}")
        print(f"  Story beats: {len(lyric_context.story_beats or [])}")

    # -----------------------------------------------------------------------
    # Step 1: Extract
    # -----------------------------------------------------------------------
    print_section("Step 1: Extract Asset Specs")
    specs = extract_asset_specs(plan_set, lyric_context)
    print(f"  Total specs: {len(specs)}")
    image_specs = [s for s in specs if s.category.is_image()]
    text_specs = [s for s in specs if s.category.is_text()]
    effect_specs_list = [s for s in image_specs if s.narrative_subject is None]
    narrative_specs_list = [s for s in image_specs if s.narrative_subject is not None]
    print(f"  Effect (motif) image specs:    {len(effect_specs_list)}")
    print(f"  Narrative (story) image specs: {len(narrative_specs_list)}")
    print(f"  Text specs:                    {len(text_specs)}")
    print()
    for i, spec in enumerate(specs, 1):
        print_spec(spec, i)

    # -----------------------------------------------------------------------
    # Step 2: Load catalog for reuse check
    # -----------------------------------------------------------------------
    assets_dir = output_dir / "assets"
    catalog_path = assets_dir / "asset_catalog.json"
    catalog = load_catalog(catalog_path)
    print_section("Step 2: Check Existing Catalog")
    print(f"  Existing entries: {len(catalog.entries)}")

    # -----------------------------------------------------------------------
    # Step 3: Enrich image specs (LLM) — concurrent with semaphore
    # -----------------------------------------------------------------------
    enriched_specs: list[AssetSpec] = []
    ENRICHMENT_CONCURRENCY = 5

    if live and image_specs:
        print_section(f"Step 3: Enrich Image Specs (LLM, concurrency={ENRICHMENT_CONCURRENCY})")
        try:
            from twinklr.core.agents.async_runner import AsyncAgentRunner
            from twinklr.core.agents.logging import create_llm_logger
            from twinklr.core.agents.providers.openai import OpenAIProvider

            provider = OpenAIProvider()
            llm_logger = create_llm_logger(
                output_dir=output_dir / "llm_calls",
                enabled=True,
            )
            runner = AsyncAgentRunner(
                provider=provider,
                prompt_base_path=Path("packages/twinklr/core/agents"),
                llm_logger=llm_logger,
            )
            enricher_spec = build_enricher_spec()
            semaphore = asyncio.Semaphore(ENRICHMENT_CONCURRENCY)

            async def _enrich_one(spec: AssetSpec) -> AssetSpec:
                async with semaphore:
                    motif_desc = None
                    motif_notes = None
                    if spec.motif_id:
                        try:
                            motif_def = MOTIF_REGISTRY.get(spec.motif_id)
                            motif_desc = motif_def.description
                            motif_notes = motif_def.usage_notes
                        except Exception:
                            logger.debug("Motif %s not found in registry", spec.motif_id)

                    print(f"  Enriching: {spec.spec_id} (motif={spec.motif_id})...")
                    enriched = await enrich_spec(
                        spec,
                        runner,
                        enricher_spec,
                        motif_description=motif_desc,
                        motif_usage_notes=motif_notes,
                    )
                    print(
                        f"    prompt: {enriched.prompt[:100]}..."
                        if enriched.prompt
                        else "    (no prompt)"
                    )
                    return enriched

            enriched_specs = await asyncio.gather(*[_enrich_one(s) for s in image_specs])
            enriched_specs = list(enriched_specs)  # tuple → list

        except ImportError as e:
            logger.warning("LLM enrichment unavailable: %s", e)
            print(f"  SKIPPED: LLM enrichment unavailable ({e})")
            enriched_specs = list(image_specs)
        except Exception as e:
            logger.error("LLM enrichment failed: %s", e)
            print(f"  FAILED: {e}")
            enriched_specs = list(image_specs)
    elif not live:
        print_section("Step 3: Enrich Image Specs (SKIPPED — dry-run mode)")
        print(f"  {len(image_specs)} image specs would be enriched in live mode")
        # Give them synthetic prompts for demonstration
        for spec in image_specs:
            enriched = spec.model_copy(
                update={
                    "prompt": (
                        f"A festive Christmas {spec.motif_id or 'pattern'} design "
                        f"for LED matrix display. Bold shapes, high contrast, "
                        f"holiday warmth. {spec.background.value} background, "
                        f"flat illustration style. [DRY-RUN SYNTHETIC PROMPT]"
                    ),
                    "negative_prompt": "text, logos, watermarks, thin lines, dark, muted",
                }
            )
            enriched_specs.append(enriched)
    else:
        enriched_specs = list(image_specs)

    # -----------------------------------------------------------------------
    # Step 3b: Dump enriched prompts for debugging
    # -----------------------------------------------------------------------
    if enriched_specs:
        prompts_dir = assets_dir / "debug"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        prompts_file = prompts_dir / "enriched_prompts.json"
        prompt_records = []
        for spec in enriched_specs:
            prompt_records.append(
                {
                    "spec_id": spec.spec_id,
                    "motif_id": spec.motif_id,
                    "category": spec.category.value,
                    "theme_id": spec.theme_id,
                    "target_roles": spec.target_roles,
                    "background": spec.background.value,
                    "width": spec.width,
                    "height": spec.height,
                    "style_tags": spec.style_tags,
                    "prompt": spec.prompt,
                    "negative_prompt": spec.negative_prompt,
                }
            )
        prompts_file.write_text(
            json.dumps(prompt_records, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\n  Prompts saved: {prompts_file}")

    # -----------------------------------------------------------------------
    # Step 4: Generate — concurrent with semaphore
    # -----------------------------------------------------------------------
    GENERATION_CONCURRENCY = 5
    print_section(f"Step 4: Generate Assets (concurrency={GENERATION_CONCURRENCY})")

    text_renderer = TextRenderer()
    image_client: OpenAIImageClient | None = None

    if live:
        try:
            from openai import AsyncOpenAI

            image_client = OpenAIImageClient(AsyncOpenAI())
            print("  Image client: AsyncOpenAI gpt-image-1.5")
        except Exception as e:
            print(f"  Image client: UNAVAILABLE ({e})")
    else:
        print("  Image client: DISABLED (dry-run)")

    all_specs = enriched_specs + text_specs
    gen_semaphore = asyncio.Semaphore(GENERATION_CONCURRENCY)

    async def _generate_one(spec: AssetSpec) -> CatalogEntry:
        async with gen_semaphore:
            entry = await generate_asset(
                spec,
                assets_dir,
                image_client=image_client,
                text_renderer=text_renderer,
                source_plan_id=plan_set.plan_set_id,
            )
            print_entry(entry)
            return entry

    new_entries = list(await asyncio.gather(*[_generate_one(s) for s in all_specs]))

    # -----------------------------------------------------------------------
    # Step 5: Update catalog
    # -----------------------------------------------------------------------
    print_section("Step 5: Update Catalog")
    catalog.merge(new_entries)
    save_catalog(catalog, catalog_path)
    print(f"  Catalog saved: {catalog_path}")
    print(f"  Total entries: {len(catalog.entries)}")
    print(f"  Created: {catalog.total_created}")
    print(f"  Cached:  {catalog.total_cached}")
    print(f"  Failed:  {catalog.total_failed}")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print_header("Summary")
    created = [e for e in new_entries if e.status == AssetStatus.CREATED]
    failed = [e for e in new_entries if e.status == AssetStatus.FAILED]

    print(f"  Specs extracted:    {len(specs)}")
    print(f"  Assets generated:   {len(created)}")
    print(f"  Assets failed:      {len(failed)}")
    print(f"  Catalog location:   {catalog_path}")
    print(f"  Assets directory:   {assets_dir}")

    if created:
        print("\n  Generated files:")
        for entry in created:
            print(f"    {entry.file_path}")

    if failed:
        print("\n  Failures:")
        for entry in failed:
            print(f"    {entry.asset_id}: {entry.error}")

    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Demo harness for the Asset Creation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run (text assets only, no API calls):
  uv run python scripts/demo_asset_pipeline.py

  # Full run with LLM enrichment + image generation:
  uv run --env-file .env -- python scripts/demo_asset_pipeline.py --live

  # Custom plan file + output dir:
  uv run --env-file .env -- python scripts/demo_asset_pipeline.py --live \\
      --plan artifacts/my_song/group_plan_set.json \\
      --output artifacts/my_song
        """,
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("artifacts/02_rudolph_the_red_nosed_reindeer/group_plan_set.json"),
        help="Path to GroupPlanSet JSON (default: Rudolph artifact)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: derived from plan path)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Enable live API calls (LLM enrichment + image generation). Requires OPENAI_API_KEY.",
    )
    parser.add_argument(
        "--no-lyrics",
        action="store_true",
        help="Skip synthetic lyric context injection",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    plan_path = args.plan.resolve()
    if not plan_path.exists():
        print(f"ERROR: Plan file not found: {plan_path}")
        sys.exit(1)

    output_dir = args.output or plan_path.parent
    output_dir = output_dir.resolve()

    asyncio.run(
        run_pipeline(
            plan_path,
            output_dir,
            live=args.live,
            with_lyrics=not args.no_lyrics,
        )
    )
