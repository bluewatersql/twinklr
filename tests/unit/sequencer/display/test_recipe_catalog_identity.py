"""Recipe catalogs participate canonically in planner cache identities."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from twinklr.core.agents.sequencer.group_planner.context import SectionPlanningContext
from twinklr.core.agents.sequencer.group_planner.context_shaping import shape_planner_context
from twinklr.core.agents.sequencer.group_planner.orchestrator import GroupPlannerOrchestrator
from twinklr.core.agents.sequencer.group_planner.stage import GroupPlannerStage
from twinklr.core.agents.sequencer.group_planner.timing import BarInfo, TimingContext
from twinklr.core.feature_engineering.loader import FEArtifactBundle
from twinklr.core.feature_engineering.models.propensity import EffectModelAffinity, PropensityIndex
from twinklr.core.feature_engineering.models.style import (
    ColorStyleProfile,
    LayeringStyleProfile,
    StyleFingerprint,
    TimingStyleProfile,
    TransitionStyleProfile,
)
from twinklr.core.feature_engineering.models.vocabulary import VocabularyExtensions
from twinklr.core.sequencer.templates.group.catalog import build_template_catalog_from_store
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog
from twinklr.core.sequencer.templates.group.store import TemplateStore

CATALOG = Path(__file__).resolve().parents[4] / "catalog" / "templates"


def test_equal_catalogs_have_equal_canonical_data_and_fingerprint() -> None:
    recipes = RecipeCatalog.from_store(TemplateStore.from_directory(CATALOG)).recipes
    forward = RecipeCatalog(recipes)
    reverse = RecipeCatalog(list(reversed(recipes)))

    assert forward.to_canonical_data() == reverse.to_canonical_data()
    assert forward.fingerprint == reverse.fingerprint


def test_catalog_content_changes_fingerprint() -> None:
    recipes = RecipeCatalog.from_store(TemplateStore.from_directory(CATALOG)).recipes
    assert RecipeCatalog(recipes).fingerprint != RecipeCatalog(recipes[:-1]).fingerprint


def _section_context(
    catalog: RecipeCatalog, store: TemplateStore, **extra: Any
) -> SectionPlanningContext:
    return SectionPlanningContext(
        section_id="intro_1",
        section_name="intro",
        start_ms=0,
        end_ms=2000,
        energy_target="LOW",
        motion_density="SPARSE",
        choreography_style="ABSTRACT",
        lead_targets=["ARCHES"],
        choreo_graph=ChoreographyGraph(
            graph_id="layout",
            groups=[ChoreoGroup(id="ARCHES", role="ARCHES")],
        ),
        template_catalog=build_template_catalog_from_store(store),
        timing_context=TimingContext(
            song_duration_ms=2000,
            bar_map={1: BarInfo(bar=1, start_ms=0, duration_ms=2000)},
        ),
        recipe_catalog=catalog,
        **extra,
    )


@pytest.mark.asyncio
async def test_prompt_order_and_actual_orchestrator_cache_key_are_canonical() -> None:
    store = TemplateStore.from_directory(CATALOG)
    recipes = RecipeCatalog.from_store(store).recipes
    forward = _section_context(RecipeCatalog(recipes), store)
    reverse = _section_context(RecipeCatalog(list(reversed(recipes))), store)
    changed = _section_context(RecipeCatalog(recipes[:-1]), store)
    orchestrator = GroupPlannerOrchestrator(MagicMock())

    forward_ids = [
        entry["recipe_id"] for entry in shape_planner_context(forward)["recipe_catalog"]["entries"]
    ]
    reverse_ids = [
        entry["recipe_id"] for entry in shape_planner_context(reverse)["recipe_catalog"]["entries"]
    ]
    assert forward_ids == reverse_ids == sorted(forward_ids)
    assert await orchestrator.get_cache_key(forward) == await orchestrator.get_cache_key(reverse)
    assert await orchestrator.get_cache_key(forward) != await orchestrator.get_cache_key(changed)


@pytest.mark.asyncio
async def test_nonempty_fe_reaches_real_stage_prompt_and_cache_identity() -> None:
    store = TemplateStore.from_directory(CATALOG)
    catalog = RecipeCatalog.from_store(store)
    graph = ChoreographyGraph(
        graph_id="layout",
        groups=[ChoreoGroup(id="ARCHES", role="ARCHES")],
    )
    bundle = FEArtifactBundle(
        propensity_index=PropensityIndex(
            affinities=(
                EffectModelAffinity(
                    effect_family="chase",
                    model_type="arch",
                    frequency=0.9,
                    exclusivity=0.8,
                    corpus_support=7,
                ),
            )
        ),
        style_fingerprint=StyleFingerprint(
            creator_id="bright",
            transition_style=TransitionStyleProfile(
                preferred_gap_ms=0,
                overlap_tendency=0.2,
                variety_score=0.8,
            ),
            color_tendencies=ColorStyleProfile(
                palette_complexity=0.7,
                contrast_preference=0.8,
                temperature_preference=0.6,
            ),
            timing_style=TimingStyleProfile(
                beat_alignment_strictness=0.9,
                density_preference=0.5,
                section_change_aggression=0.7,
            ),
            layering_style=LayeringStyleProfile(
                mean_layers=2,
                max_layers=3,
                blend_mode_preference="add",
            ),
            corpus_sequence_count=4,
        ),
        vocabulary_extensions=VocabularyExtensions(total_stack_signatures_analyzed=3),
    )
    stage = GroupPlannerStage(
        choreo_graph=graph,
        template_catalog=build_template_catalog_from_store(store),
        recipe_catalog=catalog,
        fe_bundle=bundle,
    )
    fields = stage._extract_fe_fields(section_id="intro_1")
    enriched = _section_context(catalog, store, **fields)
    absent = _section_context(catalog, store)
    enriched_prompt = shape_planner_context(enriched)
    absent_prompt = shape_planner_context(absent)

    for key in ("propensity_hints", "style_constraints"):
        assert enriched_prompt[key]
        assert absent_prompt[key] is None
    assert enriched.vocabulary_extensions is bundle.vocabulary_extensions
    assert absent.vocabulary_extensions is None
    orchestrator = GroupPlannerOrchestrator(MagicMock())
    assert await orchestrator.get_cache_key(enriched) != await orchestrator.get_cache_key(absent)
