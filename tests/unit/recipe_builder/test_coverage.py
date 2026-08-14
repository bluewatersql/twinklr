"""Tests for the layout-aware catalog coverage report."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from twinklr.cli.catalog_coverage_cmd import run_catalog_coverage_command
from twinklr.cli.main import build_arg_parser
from twinklr.core.profiling.models.enums import ModelCategory, SemanticSize, StartChannelFormat
from twinklr.core.profiling.models.layout import ModelProfile, StartChannelInfo
from twinklr.core.recipe_builder.coverage import (
    build_coverage_report,
    extract_layout_element_types,
)
from twinklr.core.sequencer.templates.group.models.template import TimingHints
from twinklr.core.sequencer.templates.group.recipe import (
    EffectRecipe,
    ModelAffinity,
    PaletteSpec,
    RecipeLayer,
    RecipeProvenance,
    StyleMarkers,
)
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    EnergyTarget,
    GroupTemplateType,
    GroupVisualIntent,
    VisualDepth,
)


def _model(*, name: str, display_as: str, pixel_count: int) -> ModelProfile:
    return ModelProfile(
        name=name,
        display_as=display_as,
        category=ModelCategory.DISPLAY,
        is_active=True,
        string_type="RGB Nodes",
        semantic_tags=(),
        semantic_size=SemanticSize.MINI,
        position={},
        scale={},
        rotation={},
        pixel_count=pixel_count,
        node_count=pixel_count,
        string_count=1,
        channels_per_node=3,
        channel_count=pixel_count * 3,
        light_count=pixel_count,
        layout_group="YARD",
        default_buffer_wxh="1x1",
        est_current_amps=0.0,
        start_channel=StartChannelInfo(raw="1", format=StartChannelFormat.ABSOLUTE),
    )


def _recipe(
    recipe_id: str,
    *,
    role: GroupTemplateType,
    energy: EnergyTarget,
    affinities: list[ModelAffinity] | None = None,
) -> EffectRecipe:
    return EffectRecipe(
        recipe_id=recipe_id,
        name=recipe_id,
        description="coverage test recipe",
        recipe_version="1.0.0",
        template_type=role,
        visual_intent=GroupVisualIntent.ABSTRACT,
        timing=TimingHints(bars_min=1, bars_max=1),
        palette_spec=PaletteSpec(mode=ColorMode.MONOCHROME, palette_roles=["primary"]),
        layers=(
            RecipeLayer(
                layer_index=0,
                layer_name="main",
                layer_depth=VisualDepth.BACKGROUND,
                effect_type="On",
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                density=1.0,
            ),
        ),
        provenance=RecipeProvenance(source="builtin"),
        style_markers=StyleMarkers(complexity=0.0, energy_affinity=energy),
        model_affinities=affinities or [],
    )


def test_element_type_extraction_prefers_display_as_and_reports_unclassified() -> None:
    elements, unclassified = extract_layout_element_types(
        (
            _model(name="not a tree", display_as="Mega Tree", pixel_count=200),
            _model(name="ARCH north", display_as="custom", pixel_count=50),
            _model(name="Megar Tree", display_as="custom", pixel_count=10),
        )
    )

    assert [(element.element_type, element.pixel_count) for element in elements] == [
        ("megatree", 200),
        ("arch", 50),
    ]
    assert [(model.name, model.pixel_count) for model in unclassified] == [("Megar Tree", 10)]


def test_coverage_counts_universal_and_positive_matching_affinity_only() -> None:
    report = build_coverage_report(
        recipes=(
            _recipe("universal", role=GroupTemplateType.BASE, energy=EnergyTarget.LOW),
            _recipe(
                "arch-positive",
                role=GroupTemplateType.BASE,
                energy=EnergyTarget.LOW,
                affinities=[ModelAffinity(model_type="arch", score=0.4)],
            ),
            _recipe(
                "arch-zero",
                role=GroupTemplateType.BASE,
                energy=EnergyTarget.LOW,
                affinities=[ModelAffinity(model_type="arch", score=0.0)],
            ),
            _recipe(
                "tree-only",
                role=GroupTemplateType.BASE,
                energy=EnergyTarget.LOW,
                affinities=[ModelAffinity(model_type="megatree", score=0.9)],
            ),
        ),
        models=(
            _model(name="Arch 1", display_as="Arches", pixel_count=25),
            _model(name="Mega Tree", display_as="Custom", pixel_count=75),
        ),
    )

    counts = {
        cell.element_type: (cell.recipe_count, cell.recipe_ids)
        for cell in report.cells
        if cell.role is GroupTemplateType.BASE and cell.energy is EnergyTarget.LOW
    }
    assert counts == {
        "arch": (2, ("universal", "arch-positive")),
        "megatree": (2, ("universal", "tree-only")),
    }


def test_gap_ranking_uses_prominence_then_role_then_energy() -> None:
    report = build_coverage_report(
        recipes=(),
        models=(
            _model(name="Mega Tree", display_as="Custom", pixel_count=100),
            _model(name="Arch", display_as="Custom", pixel_count=50),
        ),
    )

    assert [(gap.element_type, gap.role, gap.energy) for gap in report.gaps[:8]] == [
        ("megatree", GroupTemplateType.BASE, EnergyTarget.LOW),
        ("megatree", GroupTemplateType.BASE, EnergyTarget.MED),
        ("megatree", GroupTemplateType.BASE, EnergyTarget.HIGH),
        ("megatree", GroupTemplateType.BASE, EnergyTarget.BUILD),
        ("megatree", GroupTemplateType.BASE, EnergyTarget.RELEASE),
        ("megatree", GroupTemplateType.RHYTHM, EnergyTarget.LOW),
        ("megatree", GroupTemplateType.RHYTHM, EnergyTarget.MED),
        ("megatree", GroupTemplateType.RHYTHM, EnergyTarget.HIGH),
    ]
    assert report.gaps[15].element_type == "arch"


def test_catalog_coverage_command_writes_json_without_mutating_catalog(tmp_path: Path) -> None:
    fixture_layout = Path("tests/fixtures/coverage_rgbeffects.xml")
    if not fixture_layout.exists():
        pytest.skip("coverage layout XML fixture has not been committed yet")

    output_path = tmp_path / "coverage.json"
    catalog_path = Path("catalog/templates")
    before = {
        path.relative_to(catalog_path): path.read_bytes()
        for path in catalog_path.rglob("*")
        if path.is_file()
    }
    args = build_arg_parser().parse_args(
        ["catalog-coverage", "--layout", str(fixture_layout), "--out", str(output_path)]
    )

    assert run_catalog_coverage_command(args) == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["summary"] == {
        "total_cells": 15,
        "covered_cells": 2,
        "gap_cells": 13,
        "coverage_ratio": 2 / 15,
        "exit_criterion_met": False,
    }
    assert report["report_header"]["excluded_roles"] == ["TRANSITION", "SPECIAL"]
    after = {
        path.relative_to(catalog_path): path.read_bytes()
        for path in catalog_path.rglob("*")
        if path.is_file()
    }
    assert after == before
