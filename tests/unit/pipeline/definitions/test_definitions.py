"""Tests for pipeline definition factory functions."""

from __future__ import annotations

from pathlib import Path

from twinklr.core.pipeline import ExecutionPattern

MOCK_DISPLAY_GROUPS = [
    {"role_key": "OUTLINE", "model_count": 10, "group_type": "string"},
    {"role_key": "MEGA_TREE", "model_count": 1, "group_type": "tree"},
]


class TestBuildCommonStages:
    """Tests for build_common_stages factory."""

    def test_returns_four_stages(self) -> None:
        """Common stages include audio, profile, lyrics, macro."""
        from twinklr.core.pipeline.definitions.common import build_common_stages

        stages = build_common_stages(display_groups=MOCK_DISPLAY_GROUPS)
        assert len(stages) == 4

    def test_stage_ids_and_order(self) -> None:
        """Stages are in dependency order: audio, profile, lyrics, macro."""
        from twinklr.core.pipeline.definitions.common import build_common_stages

        stages = build_common_stages(display_groups=MOCK_DISPLAY_GROUPS)
        ids = [s.id for s in stages]
        assert ids == ["audio", "profile", "lyrics", "macro"]

    def test_lyrics_is_conditional(self) -> None:
        """Lyrics stage uses CONDITIONAL pattern and is not critical."""
        from twinklr.core.pipeline.definitions.common import build_common_stages

        stages = build_common_stages(display_groups=MOCK_DISPLAY_GROUPS)
        lyrics_stage = next(s for s in stages if s.id == "lyrics")

        assert lyrics_stage.pattern == ExecutionPattern.CONDITIONAL
        assert lyrics_stage.critical is False
        assert lyrics_stage.condition is not None

    def test_macro_depends_on_profile_and_lyrics(self) -> None:
        """Macro stage inputs are profile and lyrics."""
        from twinklr.core.pipeline.definitions.common import build_common_stages

        stages = build_common_stages(display_groups=MOCK_DISPLAY_GROUPS)
        macro_stage = next(s for s in stages if s.id == "macro")

        assert set(macro_stage.inputs) == {"profile", "lyrics"}


class TestBuildMovingHeadsPipeline:
    """Tests for build_moving_heads_pipeline factory."""

    def test_returns_valid_pipeline(self) -> None:
        """Pipeline validates without errors."""
        from twinklr.core.pipeline.definitions.moving_heads import (
            build_moving_heads_pipeline,
        )

        pipeline = build_moving_heads_pipeline(
            display_groups=MOCK_DISPLAY_GROUPS,
            fixture_count=4,
            available_templates=["template_a"],
            xsq_output_path=Path("/tmp/test.xsq"),
        )

        errors = pipeline.validate_pipeline()
        assert errors == [], f"Validation errors: {errors}"

    def test_contains_all_expected_stages(self) -> None:
        """MH pipeline has common stages + moving_heads + render."""
        from twinklr.core.pipeline.definitions.moving_heads import (
            build_moving_heads_pipeline,
        )

        pipeline = build_moving_heads_pipeline(
            display_groups=MOCK_DISPLAY_GROUPS,
            fixture_count=4,
            available_templates=["template_a"],
            xsq_output_path=Path("/tmp/test.xsq"),
        )

        stage_ids = [s.id for s in pipeline.stages]
        assert "audio" in stage_ids
        assert "profile" in stage_ids
        assert "lyrics" in stage_ids
        assert "macro" in stage_ids
        assert "moving_heads" in stage_ids
        assert "render" in stage_ids

    def test_render_depends_on_moving_heads(self) -> None:
        """Render stage inputs include moving_heads."""
        from twinklr.core.pipeline.definitions.moving_heads import (
            build_moving_heads_pipeline,
        )

        pipeline = build_moving_heads_pipeline(
            display_groups=MOCK_DISPLAY_GROUPS,
            fixture_count=4,
            available_templates=["template_a"],
            xsq_output_path=Path("/tmp/test.xsq"),
        )

        render = next(s for s in pipeline.stages if s.id == "render")
        assert "moving_heads" in render.inputs


class TestBuildDisplayPipeline:
    """Tests for build_display_pipeline factory."""

    def test_returns_valid_pipeline(self) -> None:
        """Pipeline validates without errors."""
        from twinklr.core.pipeline.definitions.display import build_display_pipeline
        from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
        from twinklr.core.sequencer.templates.group.models import (
            DisplayGraph,
            DisplayGroup,
        )

        display_graph = DisplayGraph(
            display_id="test",
            display_name="Test",
            groups=[DisplayGroup(group_id="G1", role="OUTLINE", display_name="G1")],
        )
        catalog = TemplateCatalog(entries=[])

        pipeline = build_display_pipeline(
            display_graph=display_graph,
            template_catalog=catalog,
            display_groups=MOCK_DISPLAY_GROUPS,
        )

        errors = pipeline.validate_pipeline()
        assert errors == [], f"Validation errors: {errors}"

    def test_contains_all_expected_stages(self) -> None:
        """Display pipeline has common + groups + aggregate + holistic + asset_resolution + display_render."""
        from twinklr.core.pipeline.definitions.display import build_display_pipeline
        from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
        from twinklr.core.sequencer.templates.group.models import (
            DisplayGraph,
            DisplayGroup,
        )

        display_graph = DisplayGraph(
            display_id="test",
            display_name="Test",
            groups=[DisplayGroup(group_id="G1", role="OUTLINE", display_name="G1")],
        )
        catalog = TemplateCatalog(entries=[])

        pipeline = build_display_pipeline(
            display_graph=display_graph,
            template_catalog=catalog,
            display_groups=MOCK_DISPLAY_GROUPS,
        )

        stage_ids = [s.id for s in pipeline.stages]
        assert "audio" in stage_ids
        assert "groups" in stage_ids
        assert "aggregate" in stage_ids
        assert "holistic" in stage_ids
        assert "asset_resolution" in stage_ids
        assert "display_render" in stage_ids

    def test_groups_is_fan_out(self) -> None:
        """Groups stage uses FAN_OUT pattern."""
        from twinklr.core.pipeline.definitions.display import build_display_pipeline
        from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
        from twinklr.core.sequencer.templates.group.models import (
            DisplayGraph,
            DisplayGroup,
        )

        display_graph = DisplayGraph(
            display_id="test",
            display_name="Test",
            groups=[DisplayGroup(group_id="G1", role="OUTLINE", display_name="G1")],
        )
        catalog = TemplateCatalog(entries=[])

        pipeline = build_display_pipeline(
            display_graph=display_graph,
            template_catalog=catalog,
            display_groups=MOCK_DISPLAY_GROUPS,
        )

        groups = next(s for s in pipeline.stages if s.id == "groups")
        assert groups.pattern == ExecutionPattern.FAN_OUT

    def test_holistic_can_be_disabled(self) -> None:
        """When enable_holistic=False, holistic stage is absent."""
        from twinklr.core.pipeline.definitions.display import build_display_pipeline
        from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
        from twinklr.core.sequencer.templates.group.models import (
            DisplayGraph,
            DisplayGroup,
        )

        display_graph = DisplayGraph(
            display_id="test",
            display_name="Test",
            groups=[DisplayGroup(group_id="G1", role="OUTLINE", display_name="G1")],
        )
        catalog = TemplateCatalog(entries=[])

        pipeline = build_display_pipeline(
            display_graph=display_graph,
            template_catalog=catalog,
            display_groups=MOCK_DISPLAY_GROUPS,
            enable_holistic=False,
        )

        stage_ids = [s.id for s in pipeline.stages]
        assert "holistic" not in stage_ids

        # asset_resolution should chain from aggregate instead
        asset_res = next(s for s in pipeline.stages if s.id == "asset_resolution")
        assert "aggregate" in asset_res.inputs

        errors = pipeline.validate_pipeline()
        assert errors == [], f"Validation errors: {errors}"

    def test_enable_assets_inserts_asset_creation_stage(self) -> None:
        """When enable_assets=True, asset_creation stage is present."""
        from twinklr.core.pipeline.definitions.display import build_display_pipeline
        from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
        from twinklr.core.sequencer.templates.group.models import (
            DisplayGraph,
            DisplayGroup,
        )

        display_graph = DisplayGraph(
            display_id="test",
            display_name="Test",
            groups=[DisplayGroup(group_id="G1", role="OUTLINE", display_name="G1")],
        )
        catalog = TemplateCatalog(entries=[])

        pipeline = build_display_pipeline(
            display_graph=display_graph,
            template_catalog=catalog,
            display_groups=MOCK_DISPLAY_GROUPS,
            enable_assets=True,
        )

        stage_ids = [s.id for s in pipeline.stages]
        assert "asset_creation" in stage_ids

        # asset_resolution should chain from asset_creation
        asset_res = next(s for s in pipeline.stages if s.id == "asset_resolution")
        assert "asset_creation" in asset_res.inputs

        errors = pipeline.validate_pipeline()
        assert errors == [], f"Validation errors: {errors}"

    def test_assets_disabled_by_default(self) -> None:
        """Default pipeline does not include asset_creation."""
        from twinklr.core.pipeline.definitions.display import build_display_pipeline
        from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
        from twinklr.core.sequencer.templates.group.models import (
            DisplayGraph,
            DisplayGroup,
        )

        display_graph = DisplayGraph(
            display_id="test",
            display_name="Test",
            groups=[DisplayGroup(group_id="G1", role="OUTLINE", display_name="G1")],
        )
        catalog = TemplateCatalog(entries=[])

        pipeline = build_display_pipeline(
            display_graph=display_graph,
            template_catalog=catalog,
            display_groups=MOCK_DISPLAY_GROUPS,
        )

        stage_ids = [s.id for s in pipeline.stages]
        assert "asset_creation" not in stage_ids
