"""Tests for deterministic asset request extraction from GroupPlanSet.

Covers: motif context collection, category determination, per-category spec
generation, text asset extraction, style tag derivation, builtin matching,
and narrative asset extraction.
"""

from __future__ import annotations

from twinklr.core.agents.assets.models import AssetCategory
from twinklr.core.agents.assets.request_extractor import (
    _build_spec_id,
    _collect_motif_contexts,
    _derive_style_tags,
    _determine_categories,
    _extract_narrative_specs,
    extract_asset_specs,
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
)
from twinklr.core.sequencer.theming import ThemeRef
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    GPBlendMode,
    GPTimingDriver,
    LaneKind,
)
from twinklr.core.sequencer.vocabulary.planning import PlanningTimeRef

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _theme(theme_id: str = "theme.holiday.traditional") -> ThemeRef:
    return ThemeRef(theme_id=theme_id, scope="SECTION")


def _palette(palette_id: str = "core.christmas_traditional") -> PaletteRef:
    return PaletteRef(palette_id=palette_id)


def _lane(
    lane: LaneKind = LaneKind.BASE,
    target_roles: list[str] | None = None,
    placements: list[GroupPlacement] | None = None,
) -> LanePlan:
    coord_plans = []
    if placements:
        coord_plans = [
            CoordinationPlan(
                coordination_mode=CoordinationMode.UNIFIED,
                group_ids=["G1"],
                placements=placements,
            )
        ]
    return LanePlan(
        lane=lane,
        target_roles=target_roles or ["OUTLINE"],
        timing_driver=GPTimingDriver.BEATS,
        blend_mode=GPBlendMode.ADD,
        coordination_plans=coord_plans,
    )


def _placement_with_motif_hint(motif_hints: list[str]) -> GroupPlacement:
    return GroupPlacement(
        placement_id="p1",
        group_id="G1",
        template_id="gtpl_test",
        start=PlanningTimeRef(bar=1, beat=1),
        param_overrides={"motif_hint": motif_hints},
    )


def _section(
    section_id: str = "intro_1",
    motif_ids: list[str] | None = None,
    lanes: list[LanePlan] | None = None,
    theme_id: str = "theme.holiday.traditional",
    palette_id: str | None = "core.christmas_traditional",
    planning_notes: str | None = None,
) -> SectionCoordinationPlan:
    return SectionCoordinationPlan(
        section_id=section_id,
        theme=_theme(theme_id),
        motif_ids=motif_ids if motif_ids is not None else ["sparkles"],
        palette=_palette(palette_id) if palette_id else None,
        lane_plans=lanes or [_lane()],
        planning_notes=planning_notes,
    )


def _plan_set(
    sections: list[SectionCoordinationPlan] | None = None,
) -> GroupPlanSet:
    return GroupPlanSet(
        plan_set_id="test_plan",
        section_plans=sections or [_section()],
    )


# ---------------------------------------------------------------------------
# MotifContext collection
# ---------------------------------------------------------------------------


class TestCollectMotifContexts:
    def test_single_section_single_motif(self) -> None:
        plan = _plan_set([_section(motif_ids=["sparkles"])])
        contexts = _collect_motif_contexts(plan)
        assert "sparkles" in contexts
        ctx = contexts["sparkles"]
        assert ctx.motif_id == "sparkles"
        assert "intro_1" in ctx.section_ids
        assert "theme.holiday.traditional" in ctx.theme_ids

    def test_motif_hint_overrides_collected(self) -> None:
        placement = _placement_with_motif_hint(["radial_rays"])
        lane = _lane(placements=[placement])
        plan = _plan_set([_section(motif_ids=["sparkles"], lanes=[lane])])
        contexts = _collect_motif_contexts(plan)
        assert "sparkles" in contexts
        assert "radial_rays" in contexts

    def test_multiple_sections_same_motif_accumulates(self) -> None:
        s1 = _section(section_id="s1", motif_ids=["sparkles"], theme_id="theme.a")
        s2 = _section(section_id="s2", motif_ids=["sparkles"], theme_id="theme.b")
        plan = _plan_set([s1, s2])
        contexts = _collect_motif_contexts(plan)
        ctx = contexts["sparkles"]
        assert ctx.theme_ids == {"theme.a", "theme.b"}
        assert ctx.section_ids == {"s1", "s2"}

    def test_target_roles_collected_from_lanes(self) -> None:
        lanes = [
            _lane(target_roles=["MEGA_TREE"]),
            _lane(lane=LaneKind.ACCENT, target_roles=["HERO"]),
        ]
        plan = _plan_set([_section(lanes=lanes)])
        ctx = _collect_motif_contexts(plan)["sparkles"]
        assert ctx.target_roles == {"MEGA_TREE", "HERO"}

    def test_planning_notes_collected_as_scene_context(self) -> None:
        s = _section(planning_notes="Rudolph's nose glows red")
        plan = _plan_set([s])
        ctx = _collect_motif_contexts(plan)["sparkles"]
        assert "Rudolph's nose glows red" in ctx.scene_context

    def test_empty_motifs_produces_empty(self) -> None:
        plan = _plan_set([_section(motif_ids=[])])
        contexts = _collect_motif_contexts(plan)
        assert len(contexts) == 0


# ---------------------------------------------------------------------------
# Category determination
# ---------------------------------------------------------------------------


class TestDetermineCategories:
    def test_mega_tree_gets_texture(self) -> None:
        cats = _determine_categories({"MEGA_TREE"})
        assert AssetCategory.IMAGE_TEXTURE in cats

    def test_hero_gets_cutout(self) -> None:
        cats = _determine_categories({"HERO"})
        assert AssetCategory.IMAGE_CUTOUT in cats

    def test_mixed_roles_get_multiple_categories(self) -> None:
        cats = _determine_categories({"MEGA_TREE", "HERO"})
        assert AssetCategory.IMAGE_TEXTURE in cats
        assert AssetCategory.IMAGE_CUTOUT in cats

    def test_unknown_role_gets_cutout_default(self) -> None:
        cats = _determine_categories({"UNKNOWN_ROLE"})
        assert AssetCategory.IMAGE_CUTOUT in cats


# ---------------------------------------------------------------------------
# Spec ID generation
# ---------------------------------------------------------------------------


class TestBuildSpecId:
    def test_image_spec(self) -> None:
        sid = _build_spec_id("sparkles", AssetCategory.IMAGE_TEXTURE)
        assert sid == "asset_image_texture_sparkles"

    def test_text_spec(self) -> None:
        sid = _build_spec_id("song_title", AssetCategory.TEXT_BANNER)
        assert sid == "asset_text_banner_song_title"


# ---------------------------------------------------------------------------
# Style tag derivation
# ---------------------------------------------------------------------------


class TestDeriveStyleTags:
    def test_traditional(self) -> None:
        tags = _derive_style_tags("theme.holiday.traditional")
        assert "holiday_christmas_traditional" in tags
        assert "high_contrast" in tags

    def test_playful(self) -> None:
        tags = _derive_style_tags("theme.holiday.playful")
        assert "holiday_christmas_playful" in tags
        assert "bold_colors" in tags

    def test_elegant(self) -> None:
        tags = _derive_style_tags("theme.holiday.elegant")
        assert "holiday_christmas_elegant" in tags

    def test_unknown_defaults_to_traditional(self) -> None:
        tags = _derive_style_tags("theme.holiday.custom")
        assert "holiday_christmas_traditional" in tags


# ---------------------------------------------------------------------------
# Full extraction
# ---------------------------------------------------------------------------


class TestExtractAssetSpecs:
    def test_basic_extraction(self) -> None:
        lanes = [_lane(target_roles=["MEGA_TREE"])]
        plan = _plan_set([_section(motif_ids=["sparkles"], lanes=lanes)])
        specs = extract_asset_specs(plan)
        assert len(specs) >= 1
        image_specs = [s for s in specs if s.category.is_image()]
        assert len(image_specs) == 1
        assert image_specs[0].motif_id == "sparkles"
        assert image_specs[0].category == AssetCategory.IMAGE_TEXTURE

    def test_motif_spanning_roles_creates_multiple_specs(self) -> None:
        lanes = [
            _lane(target_roles=["MEGA_TREE"]),
            _lane(lane=LaneKind.ACCENT, target_roles=["HERO"]),
        ]
        plan = _plan_set([_section(motif_ids=["sparkles"], lanes=lanes)])
        specs = extract_asset_specs(plan)
        image_specs = [s for s in specs if s.category.is_image()]
        categories = {s.category for s in image_specs}
        assert AssetCategory.IMAGE_TEXTURE in categories
        assert AssetCategory.IMAGE_CUTOUT in categories

    def test_separate_specs_have_correct_roles(self) -> None:
        lanes = [
            _lane(target_roles=["MEGA_TREE"]),
            _lane(lane=LaneKind.ACCENT, target_roles=["HERO"]),
        ]
        plan = _plan_set([_section(motif_ids=["sparkles"], lanes=lanes)])
        specs = extract_asset_specs(plan)
        image_specs = [s for s in specs if s.category.is_image()]
        texture_spec = next(s for s in image_specs if s.category == AssetCategory.IMAGE_TEXTURE)
        cutout_spec = next(s for s in image_specs if s.category == AssetCategory.IMAGE_CUTOUT)
        assert "MEGA_TREE" in texture_spec.target_roles
        assert "HERO" in cutout_spec.target_roles

    def test_song_title_banner_always_created(self) -> None:
        plan = _plan_set([_section()])
        specs = extract_asset_specs(plan)
        banners = [s for s in specs if s.category == AssetCategory.TEXT_BANNER]
        assert len(banners) == 1
        assert banners[0].text_content is not None

    def test_text_banner_uses_plan_set_id(self) -> None:
        plan = _plan_set([_section()])
        specs = extract_asset_specs(plan)
        banner = next(s for s in specs if s.category == AssetCategory.TEXT_BANNER)
        assert "Test Plan" in (banner.text_content or "")

    def test_empty_plan_creates_only_banner(self) -> None:
        plan = _plan_set([_section(motif_ids=[])])
        specs = extract_asset_specs(plan)
        assert len(specs) == 1  # Just the song title banner
        assert specs[0].category == AssetCategory.TEXT_BANNER

    def test_style_tags_applied(self) -> None:
        plan = _plan_set([_section(motif_ids=["sparkles"])])
        specs = extract_asset_specs(plan)
        image_specs = [s for s in specs if s.category.is_image()]
        assert len(image_specs[0].style_tags) > 0

    def test_scene_context_propagated(self) -> None:
        s = _section(
            motif_ids=["sparkles"],
            planning_notes="Rudolph's glowing nose",
        )
        plan = _plan_set([s])
        specs = extract_asset_specs(plan)
        image_specs = [s for s in specs if s.category.is_image()]
        assert "Rudolph's glowing nose" in image_specs[0].scene_context

    def test_deduplication_across_sections(self) -> None:
        """Same motif + same roles across sections → one spec per category."""
        s1 = _section(section_id="s1", motif_ids=["sparkles"])
        s2 = _section(section_id="s2", motif_ids=["sparkles"])
        plan = _plan_set([s1, s2])
        specs = extract_asset_specs(plan)
        image_specs = [s for s in specs if s.category.is_image()]
        sparkle_specs = [s for s in image_specs if s.motif_id == "sparkles"]
        assert len(sparkle_specs) == 1
        # Both section IDs should be present
        assert "s1" in sparkle_specs[0].section_ids
        assert "s2" in sparkle_specs[0].section_ids


# ---------------------------------------------------------------------------
# Narrative asset extraction
# ---------------------------------------------------------------------------


def _narrative_directive(
    directive_id: str = "rudolph_nose",
    subject: str = "Reindeer with glowing red nose",
    category: str = "image_cutout",
    visual_description: str = "Bold silhouette of a reindeer nose with warm red glow",
    story_context: str = "Introduction of Rudolph's distinctive feature",
    emphasis: str = "HIGH",
    section_ids: list[str] | None = None,
) -> NarrativeAssetDirective:
    return NarrativeAssetDirective(
        directive_id=directive_id,
        subject=subject,
        category=category,
        visual_description=visual_description,
        story_context=story_context,
        emphasis=emphasis,
        section_ids=section_ids or ["intro_1"],
    )


def _narrative_plan_set(
    directives: list[NarrativeAssetDirective],
    plan_set_id: str = "02_rudolph_the_red_nosed_reindeer",
    sections: list[SectionCoordinationPlan] | None = None,
) -> GroupPlanSet:
    """Build a GroupPlanSet with narrative directives for testing."""
    return GroupPlanSet(
        plan_set_id=plan_set_id,
        section_plans=sections or [_section()],
        narrative_assets=directives,
    )


class TestExtractNarrativeSpecs:
    def test_empty_directives_returns_empty(self) -> None:
        plan = _narrative_plan_set([])
        specs = _extract_narrative_specs(plan)
        assert specs == []

    def test_single_cutout_directive(self) -> None:
        d = _narrative_directive()
        plan = _narrative_plan_set([d])
        specs = _extract_narrative_specs(plan)
        assert len(specs) == 1
        spec = specs[0]
        assert spec.category == AssetCategory.IMAGE_CUTOUT
        assert spec.narrative_subject == "Reindeer with glowing red nose"
        assert spec.motif_id is None  # Narrative specs don't use motif_id

    def test_texture_directive(self) -> None:
        d = _narrative_directive(
            directive_id="foggy_night",
            category="image_texture",
            subject="Dense swirling fog on a winter night",
            visual_description="Layered wisps of cool blue-grey fog across dark background",
        )
        plan = _narrative_plan_set([d])
        specs = _extract_narrative_specs(plan)
        assert len(specs) == 1
        assert specs[0].category == AssetCategory.IMAGE_TEXTURE

    def test_unknown_category_skipped(self) -> None:
        d = _narrative_directive(category="unknown_type")
        plan = _narrative_plan_set([d])
        specs = _extract_narrative_specs(plan)
        assert len(specs) == 0

    def test_spec_id_uses_directive_id(self) -> None:
        d = _narrative_directive(directive_id="santa_sleigh")
        plan = _narrative_plan_set([d])
        specs = _extract_narrative_specs(plan)
        assert specs[0].spec_id == "asset_image_cutout_santa_sleigh"

    def test_narrative_fields_populated(self) -> None:
        d = NarrativeAssetDirective(
            directive_id="rudolph_nose",
            subject="Reindeer with glowing red nose",
            category="image_cutout",
            visual_description="Bold silhouette of a reindeer nose with warm red glow",
            story_context="Introduction of Rudolph's distinctive feature",
            emphasis="HIGH",
            color_guidance="Warm red-orange",
            mood="triumphant",
            section_ids=["intro_1"],
        )
        plan = _narrative_plan_set([d])
        specs = _extract_narrative_specs(plan)
        spec = specs[0]
        assert spec.narrative_description is not None
        assert spec.color_guidance == "Warm red-orange"
        assert spec.mood == "triumphant"

    def test_section_ids_propagated(self) -> None:
        d = _narrative_directive(section_ids=["verse_1", "chorus_1"])
        plan = _narrative_plan_set(
            [d],
            sections=[
                _section(section_id="verse_1"),
                _section(section_id="chorus_1"),
            ],
        )
        specs = _extract_narrative_specs(plan)
        assert specs[0].section_ids == ["verse_1", "chorus_1"]

    def test_default_size_is_1024(self) -> None:
        d = _narrative_directive()
        plan = _narrative_plan_set([d])
        specs = _extract_narrative_specs(plan)
        assert specs[0].width == 1024
        assert specs[0].height == 1024

    def test_palette_resolved_from_section(self) -> None:
        """Narrative specs get the palette from their section."""
        d = _narrative_directive(section_ids=["intro_1"])
        plan = _narrative_plan_set(
            [d],
            sections=[_section(section_id="intro_1", palette_id="core.christmas_traditional")],
        )
        specs = _extract_narrative_specs(plan)
        spec = specs[0]
        assert spec.palette_id == "core.christmas_traditional"
        assert len(spec.palette_colors) > 0
        hex_values = [c["hex"] for c in spec.palette_colors]
        assert "#E53935" in hex_values  # christmas_red

    def test_song_title_set(self) -> None:
        """Narrative specs get a cleaned song title."""
        d = _narrative_directive()
        plan = _narrative_plan_set([d], plan_set_id="02_rudolph_the_red_nosed_reindeer")
        specs = _extract_narrative_specs(plan)
        assert specs[0].song_title == "Rudolph The Red Nosed Reindeer"


class TestExtractAssetSpecsDualSource:
    """Test that extract_asset_specs produces both effect and narrative specs."""

    def test_narrative_directives_included(self) -> None:
        directives = [
            _narrative_directive(directive_id="nose_glow"),
        ]
        plan = _plan_set([_section(motif_ids=["sparkles"])])
        # Add narrative directives to the plan_set level
        plan_with_narr = plan.model_copy(update={"narrative_assets": directives})
        specs = extract_asset_specs(plan_with_narr)

        # Should have: 1 effect spec (sparkles/cutout) + 1 narrative + 1 banner
        narrative_specs = [s for s in specs if s.narrative_subject is not None]
        effect_specs = [s for s in specs if s.category.is_image() and s.narrative_subject is None]
        text_specs = [s for s in specs if s.category.is_text()]

        assert len(narrative_specs) == 1
        assert len(effect_specs) >= 1
        assert len(text_specs) == 1

    def test_no_narrative_directives_still_works(self) -> None:
        plan = _plan_set([_section(motif_ids=["sparkles"])])
        specs = extract_asset_specs(plan)
        narrative_specs = [s for s in specs if s.narrative_subject is not None]
        assert len(narrative_specs) == 0
