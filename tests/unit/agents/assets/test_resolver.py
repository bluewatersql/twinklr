"""Tests for asset resolution: extract_motif_id and resolve_plan_assets."""

from __future__ import annotations

from twinklr.core.agents.assets.models import (
    AssetCatalog,
    AssetCategory,
    AssetSpec,
    AssetStatus,
    CatalogEntry,
)
from twinklr.core.agents.assets.resolver import (
    ROLE_CATEGORY_PREFERENCE,
    extract_motif_id,
    resolve_plan_assets,
)
from twinklr.core.sequencer.planning.group_plan import (
    GroupPlanSet,
    LanePlan,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationPlan,
    GroupPlacement,
    PlanTarget,
)
from twinklr.core.sequencer.theming import ThemeRef
from twinklr.core.sequencer.theming.enums import ThemeScope
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    EffectDuration,
    IntensityLevel,
    LaneKind,
    PlanningTimeRef,
)
from twinklr.core.sequencer.vocabulary.choreography import TargetType

# ---------------------------------------------------------------------------
# extract_motif_id tests
# ---------------------------------------------------------------------------


class TestExtractMotifId:
    """Tests for extract_motif_id."""

    def test_base_motif_template(self) -> None:
        """Extracts motif from base_motif pattern."""
        assert extract_motif_id("gtpl_base_motif_sparkles_ambient") == "sparkles"

    def test_rhythm_motif_template(self) -> None:
        """Extracts motif from rhythm_motif pattern."""
        assert extract_motif_id("gtpl_rhythm_motif_candy_stripes_drive") == "candy_stripes"

    def test_accent_motif_template(self) -> None:
        """Extracts motif from accent_motif pattern."""
        assert extract_motif_id("gtpl_accent_motif_radial_rays_hit_big") == "radial_rays"

    def test_accent_motif_snowflakes(self) -> None:
        """Extracts motif from accent template with snowflakes."""
        assert extract_motif_id("gtpl_accent_motif_snowflakes_hit_big") == "snowflakes"

    def test_accent_motif_ornaments(self) -> None:
        """Extracts motif from accent template with ornaments."""
        assert extract_motif_id("gtpl_accent_motif_ornaments_hit_small") == "ornaments"

    def test_transition_motif_template(self) -> None:
        """Extracts motif from transition_motif pattern."""
        assert extract_motif_id("gtpl_transition_motif_wave_bands_ripple") == "wave_bands"

    def test_special_motif_template(self) -> None:
        """Extracts motif from special_motif pattern."""
        assert extract_motif_id("gtpl_special_motif_fire_signature") == "fire"

    def test_multi_word_motif(self) -> None:
        """Extracts multi-word motif IDs (underscore-joined)."""
        assert extract_motif_id("gtpl_base_motif_light_trails_ambient") == "light_trails"
        assert extract_motif_id("gtpl_base_motif_wave_bands_ambient") == "wave_bands"

    def test_non_motif_template_returns_none(self) -> None:
        """Non-motif templates return None."""
        assert extract_motif_id("gtpl_base_wash_soft") is None
        assert extract_motif_id("gtpl_accent_burst_big") is None
        assert extract_motif_id("gtpl_rhythm_sparkle_fast") is None

    def test_non_motif_strand_effects(self) -> None:
        """Strand effect templates return None."""
        assert extract_motif_id("gtpl_rhythm_candy_stripe_scroll") is None

    def test_empty_string(self) -> None:
        """Empty string returns None."""
        assert extract_motif_id("") is None

    def test_base_motif_abstract(self) -> None:
        """Extracts abstract motif."""
        assert extract_motif_id("gtpl_base_motif_abstract_ambient") == "abstract"

    def test_base_motif_bokeh(self) -> None:
        """Extracts bokeh motif."""
        assert extract_motif_id("gtpl_base_motif_bokeh_ambient") == "bokeh"


# ---------------------------------------------------------------------------
# Helpers for resolve_plan_assets tests
# ---------------------------------------------------------------------------


def _make_catalog_entry(
    asset_id: str,
    motif_id: str | None = None,
    category: AssetCategory = AssetCategory.IMAGE_CUTOUT,
    target_roles: list[str] | None = None,
    section_ids: list[str] | None = None,
    file_path: str = "/data/assets/images/cutouts/test.png",
) -> CatalogEntry:
    """Create a CatalogEntry for testing."""
    return CatalogEntry(
        asset_id=asset_id,
        spec=AssetSpec(
            spec_id=asset_id,
            category=category,
            motif_id=motif_id,
            theme_id="theme.holiday.traditional",
            section_ids=section_ids or ["s1"],
            target_roles=target_roles or [],
        ),
        file_path=file_path,
        content_hash="abc123",
        status=AssetStatus.CREATED,
        width=1024,
        height=1024,
        has_alpha=True,
        file_size_bytes=50000,
        created_at="2026-02-13T00:00:00Z",
        source_plan_id="test_plan",
        generation_model="gpt-image-1.5",
        prompt_hash="hash123",
    )


def _make_placement(
    placement_id: str = "p1",
    group_id: str = "ARCHES",
    template_id: str = "gtpl_base_motif_sparkles_ambient",
) -> GroupPlacement:
    """Create a GroupPlacement for testing."""
    return GroupPlacement(
        placement_id=placement_id,
        target=PlanTarget(type=TargetType.GROUP, id=group_id),
        template_id=template_id,
        start=PlanningTimeRef(bar=1, beat=1),
        duration=EffectDuration.PHRASE,
        intensity=IntensityLevel.MED,
    )


def _make_plan_set(
    placements: list[GroupPlacement],
    section_id: str = "s1",
) -> GroupPlanSet:
    """Create a GroupPlanSet with a single section and lane."""
    section = SectionCoordinationPlan(
        section_id=section_id,
        theme=ThemeRef(theme_id="theme.holiday.traditional", scope=ThemeScope.SECTION),
        lane_plans=[
            LanePlan(
                lane=LaneKind.BASE,
                target_roles=["ARCHES"],
                coordination_plans=[
                    CoordinationPlan(
                        coordination_mode=CoordinationMode.UNIFIED,
                        targets=[PlanTarget(type=TargetType.GROUP, id="ARCHES")],
                        placements=placements,
                    )
                ],
            )
        ],
        start_ms=0,
        end_ms=10000,
    )
    return GroupPlanSet(
        plan_set_id="test_plan",
        section_plans=[section],
    )


# ---------------------------------------------------------------------------
# resolve_plan_assets tests
# ---------------------------------------------------------------------------


class TestResolvePlanAssets:
    """Tests for resolve_plan_assets."""

    def test_resolves_motif_to_matching_catalog_entry(self) -> None:
        """Placement with motif template resolves to matching catalog entry."""
        placement = _make_placement(
            template_id="gtpl_base_motif_sparkles_ambient",
            group_id="ARCHES",
        )
        plan_set = _make_plan_set([placement])
        catalog = AssetCatalog(
            catalog_id="test",
            entries=[
                _make_catalog_entry(
                    asset_id="asset_image_cutout_sparkles",
                    motif_id="sparkles",
                    category=AssetCategory.IMAGE_CUTOUT,
                )
            ],
        )

        resolved = resolve_plan_assets(plan_set, catalog)

        # Should have resolved_asset_ids populated
        resolved_placement = (
            resolved.section_plans[0].lane_plans[0].coordination_plans[0].placements[0]
        )
        assert resolved_placement.resolved_asset_ids == ["asset_image_cutout_sparkles"]

    def test_non_motif_template_stays_empty(self) -> None:
        """Non-motif template should have empty resolved_asset_ids."""
        placement = _make_placement(
            template_id="gtpl_base_wash_soft",
        )
        plan_set = _make_plan_set([placement])
        catalog = AssetCatalog(
            catalog_id="test",
            entries=[
                _make_catalog_entry(
                    asset_id="asset_image_cutout_sparkles",
                    motif_id="sparkles",
                )
            ],
        )

        resolved = resolve_plan_assets(plan_set, catalog)

        resolved_placement = (
            resolved.section_plans[0].lane_plans[0].coordination_plans[0].placements[0]
        )
        assert resolved_placement.resolved_asset_ids == []

    def test_no_catalog_match_stays_empty(self) -> None:
        """Motif template with no matching catalog entry stays empty."""
        placement = _make_placement(
            template_id="gtpl_base_motif_abstract_ambient",
        )
        plan_set = _make_plan_set([placement])
        catalog = AssetCatalog(
            catalog_id="test",
            entries=[
                _make_catalog_entry(
                    asset_id="asset_image_cutout_sparkles",
                    motif_id="sparkles",
                )
            ],
        )

        resolved = resolve_plan_assets(plan_set, catalog)

        resolved_placement = (
            resolved.section_plans[0].lane_plans[0].coordination_plans[0].placements[0]
        )
        assert resolved_placement.resolved_asset_ids == []

    def test_prefers_category_by_role(self) -> None:
        """Resolver picks the preferred category for the group's role."""
        placement = _make_placement(
            template_id="gtpl_base_motif_sparkles_ambient",
            group_id="MEGA_TREE",
        )
        plan_set = _make_plan_set([placement])
        catalog = AssetCatalog(
            catalog_id="test",
            entries=[
                _make_catalog_entry(
                    asset_id="asset_image_cutout_sparkles",
                    motif_id="sparkles",
                    category=AssetCategory.IMAGE_CUTOUT,
                ),
                _make_catalog_entry(
                    asset_id="asset_image_texture_sparkles",
                    motif_id="sparkles",
                    category=AssetCategory.IMAGE_TEXTURE,
                    file_path="/data/assets/images/textures/sparkles.png",
                ),
            ],
        )

        resolved = resolve_plan_assets(plan_set, catalog)

        resolved_placement = (
            resolved.section_plans[0].lane_plans[0].coordination_plans[0].placements[0]
        )
        # MEGA_TREE prefers IMAGE_TEXTURE
        assert "asset_image_texture_sparkles" in resolved_placement.resolved_asset_ids

    def test_cross_category_fallback(self) -> None:
        """Falls back to other category when preferred is not available."""
        placement = _make_placement(
            template_id="gtpl_base_motif_sparkles_ambient",
            group_id="MEGA_TREE",  # prefers TEXTURE
        )
        plan_set = _make_plan_set([placement])
        # Only a cutout exists — no texture
        catalog = AssetCatalog(
            catalog_id="test",
            entries=[
                _make_catalog_entry(
                    asset_id="asset_image_cutout_sparkles",
                    motif_id="sparkles",
                    category=AssetCategory.IMAGE_CUTOUT,
                )
            ],
        )

        resolved = resolve_plan_assets(plan_set, catalog)

        resolved_placement = (
            resolved.section_plans[0].lane_plans[0].coordination_plans[0].placements[0]
        )
        # Should fall back to cutout since no texture exists
        assert resolved_placement.resolved_asset_ids == ["asset_image_cutout_sparkles"]

    def test_failed_entries_excluded(self) -> None:
        """FAILED catalog entries are not resolved."""
        placement = _make_placement(
            template_id="gtpl_base_motif_sparkles_ambient",
        )
        plan_set = _make_plan_set([placement])
        catalog = AssetCatalog(
            catalog_id="test",
            entries=[
                _make_catalog_entry(
                    asset_id="asset_image_cutout_sparkles",
                    motif_id="sparkles",
                ).model_copy(update={"status": AssetStatus.FAILED})
            ],
        )

        resolved = resolve_plan_assets(plan_set, catalog)

        resolved_placement = (
            resolved.section_plans[0].lane_plans[0].coordination_plans[0].placements[0]
        )
        assert resolved_placement.resolved_asset_ids == []

    def test_original_plan_not_mutated(self) -> None:
        """resolve_plan_assets returns a new plan; original is unchanged."""
        placement = _make_placement(
            template_id="gtpl_base_motif_sparkles_ambient",
        )
        plan_set = _make_plan_set([placement])
        catalog = AssetCatalog(
            catalog_id="test",
            entries=[
                _make_catalog_entry(
                    asset_id="asset_image_cutout_sparkles",
                    motif_id="sparkles",
                )
            ],
        )

        resolved = resolve_plan_assets(plan_set, catalog)

        # Original should be untouched
        original_placement = (
            plan_set.section_plans[0].lane_plans[0].coordination_plans[0].placements[0]
        )
        assert original_placement.resolved_asset_ids == []
        # Resolved should have IDs
        resolved_placement = (
            resolved.section_plans[0].lane_plans[0].coordination_plans[0].placements[0]
        )
        assert len(resolved_placement.resolved_asset_ids) > 0

    def test_empty_catalog_no_resolution(self) -> None:
        """Empty catalog produces no resolutions."""
        placement = _make_placement(
            template_id="gtpl_base_motif_sparkles_ambient",
        )
        plan_set = _make_plan_set([placement])
        catalog = AssetCatalog(catalog_id="test")

        resolved = resolve_plan_assets(plan_set, catalog)

        resolved_placement = (
            resolved.section_plans[0].lane_plans[0].coordination_plans[0].placements[0]
        )
        assert resolved_placement.resolved_asset_ids == []

    def test_multiple_placements_resolved_independently(self) -> None:
        """Each placement resolves independently."""
        p1 = _make_placement(
            placement_id="p1",
            template_id="gtpl_base_motif_sparkles_ambient",
        )
        p2 = _make_placement(
            placement_id="p2",
            template_id="gtpl_base_motif_bokeh_ambient",
        )
        plan_set = _make_plan_set([p1, p2])
        catalog = AssetCatalog(
            catalog_id="test",
            entries=[
                _make_catalog_entry(
                    asset_id="asset_image_cutout_sparkles",
                    motif_id="sparkles",
                ),
                _make_catalog_entry(
                    asset_id="asset_image_cutout_bokeh",
                    motif_id="bokeh",
                    file_path="/data/assets/images/cutouts/bokeh.png",
                ),
            ],
        )

        resolved = resolve_plan_assets(plan_set, catalog)

        placements = resolved.section_plans[0].lane_plans[0].coordination_plans[0].placements
        assert placements[0].resolved_asset_ids == ["asset_image_cutout_sparkles"]
        assert placements[1].resolved_asset_ids == ["asset_image_cutout_bokeh"]


class TestRoleCategoryPreference:
    """Tests for the role → category preference matrix."""

    def test_mega_tree_prefers_texture(self) -> None:
        assert ROLE_CATEGORY_PREFERENCE["MEGA_TREE"] == AssetCategory.IMAGE_TEXTURE

    def test_matrix_prefers_texture(self) -> None:
        assert ROLE_CATEGORY_PREFERENCE["MATRIX"] == AssetCategory.IMAGE_TEXTURE

    def test_arches_prefers_cutout(self) -> None:
        assert ROLE_CATEGORY_PREFERENCE["ARCHES"] == AssetCategory.IMAGE_CUTOUT

    def test_windows_prefers_cutout(self) -> None:
        assert ROLE_CATEGORY_PREFERENCE["WINDOWS"] == AssetCategory.IMAGE_CUTOUT

    def test_hero_prefers_cutout(self) -> None:
        assert ROLE_CATEGORY_PREFERENCE["HERO"] == AssetCategory.IMAGE_CUTOUT

    def test_outline_prefers_cutout(self) -> None:
        assert ROLE_CATEGORY_PREFERENCE["OUTLINE"] == AssetCategory.IMAGE_CUTOUT
