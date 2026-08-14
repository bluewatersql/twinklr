"""Layout-aware coverage reporting for the tracked recipe catalog."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from twinklr.core.feature_engineering.element_types import extract_model_type
from twinklr.core.profiling.models.enums import ModelCategory
from twinklr.core.profiling.models.layout import ModelProfile
from twinklr.core.recipe_builder.evidence import DEFAULT_TEMPLATES_DIR, load_catalog
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe
from twinklr.core.sequencer.vocabulary import EnergyTarget, GroupTemplateType

# This phase's exit criterion is deliberately narrower than the complete enum:
# PEAK, TRANSITION, and SPECIAL are not part of the BASE/RHYTHM/ACCENT coverage grid.
COVERAGE_ROLES: tuple[GroupTemplateType, ...] = (
    GroupTemplateType.BASE,
    GroupTemplateType.RHYTHM,
    GroupTemplateType.ACCENT,
)
COVERAGE_ENERGIES: tuple[EnergyTarget, ...] = (
    EnergyTarget.LOW,
    EnergyTarget.MED,
    EnergyTarget.HIGH,
    EnergyTarget.BUILD,
    EnergyTarget.RELEASE,
)


@dataclass(frozen=True)
class ElementTypeSummary:
    """A classified display element type and its layout prominence."""

    element_type: str
    pixel_count: int
    prominence_share: float


@dataclass(frozen=True)
class UnclassifiedModel:
    """A display model that no shared element-type pattern identifies."""

    name: str
    display_as: str
    pixel_count: int


@dataclass(frozen=True)
class CoverageCell:
    """One element-type, role, and energy coverage result."""

    element_type: str
    role: GroupTemplateType
    energy: EnergyTarget
    recipe_count: int
    recipe_ids: tuple[str, ...]
    is_gap: bool


@dataclass(frozen=True)
class CoverageSummary:
    """Phase-exit coverage summary, excluding unclassified display models."""

    total_cells: int
    covered_cells: int
    gap_cells: int
    coverage_ratio: float
    exit_criterion_met: bool


@dataclass(frozen=True)
class CoverageReport:
    """Machine-readable coverage report plus ordered curation gaps."""

    element_types: tuple[ElementTypeSummary, ...]
    unclassified: tuple[UnclassifiedModel, ...]
    cells: tuple[CoverageCell, ...]
    gaps: tuple[CoverageCell, ...]
    summary: CoverageSummary

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable form with vocabulary values as strings."""
        return {
            "report_header": {
                "roles": [role.value for role in COVERAGE_ROLES],
                "energies": [energy.value for energy in COVERAGE_ENERGIES],
                "excluded_roles": [
                    GroupTemplateType.TRANSITION.value,
                    GroupTemplateType.SPECIAL.value,
                ],
                "excluded_role_reason": (
                    "TRANSITION and SPECIAL are excluded because the Phase 2K exit "
                    "criterion covers BASE, RHYTHM, and ACCENT only."
                ),
                "excluded_energy_values": [EnergyTarget.PEAK.value],
                "excluded_energy_reason": (
                    "PEAK is outside the five-energy-range Phase 2K coverage axis."
                ),
            },
            "element_types": [asdict(element) for element in self.element_types],
            "unclassified": [asdict(model) for model in self.unclassified],
            "cells": [
                {
                    **asdict(cell),
                    "role": cell.role.value,
                    "energy": cell.energy.value,
                    "recipe_ids": list(cell.recipe_ids),
                }
                for cell in self.cells
            ],
            "gaps": [
                {
                    **asdict(cell),
                    "role": cell.role.value,
                    "energy": cell.energy.value,
                    "recipe_ids": list(cell.recipe_ids),
                }
                for cell in self.gaps
            ],
            "summary": asdict(self.summary),
        }


def extract_layout_element_types(
    models: Iterable[ModelProfile],
) -> tuple[tuple[ElementTypeSummary, ...], tuple[UnclassifiedModel, ...]]:
    """Classify display models and aggregate their type prominence.

    ``display_as`` is intentionally checked before the model name because it is
    xLights' semantic identity. The shared extractor keeps this identity in
    lock-step with the propensity mining pipeline.
    """
    display_models = [model for model in models if model.category is ModelCategory.DISPLAY]
    total_pixels = sum(model.pixel_count for model in display_models)
    pixels_by_type: dict[str, int] = {}
    unclassified: list[UnclassifiedModel] = []

    for model in display_models:
        element_type = extract_model_type(model.display_as) or extract_model_type(model.name)
        if element_type is None:
            unclassified.append(
                UnclassifiedModel(
                    name=model.name,
                    display_as=model.display_as,
                    pixel_count=model.pixel_count,
                )
            )
            continue
        pixels_by_type[element_type] = pixels_by_type.get(element_type, 0) + model.pixel_count

    element_types = tuple(
        ElementTypeSummary(
            element_type=element_type,
            pixel_count=pixel_count,
            prominence_share=pixel_count / total_pixels if total_pixels else 0.0,
        )
        for element_type, pixel_count in sorted(
            pixels_by_type.items(), key=lambda item: (-item[1], item[0])
        )
    )
    return element_types, tuple(unclassified)


def _recipe_applies_to_element_type(recipe: EffectRecipe, element_type: str) -> bool:
    if not recipe.model_affinities:
        return True
    return any(
        affinity.model_type == element_type and affinity.score > 0.0
        for affinity in recipe.model_affinities
    )


def build_coverage_report(
    *,
    recipes: Iterable[EffectRecipe],
    models: Iterable[ModelProfile],
) -> CoverageReport:
    """Build the Phase 2K coverage matrix for one profiled layout."""
    element_types, unclassified = extract_layout_element_types(models)
    recipe_list = tuple(recipes)
    cells: list[CoverageCell] = []

    for element in element_types:
        for role in COVERAGE_ROLES:
            for energy in COVERAGE_ENERGIES:
                recipe_ids = tuple(
                    recipe.recipe_id
                    for recipe in recipe_list
                    if recipe.template_type is role
                    and recipe.style_markers.energy_affinity is energy
                    and _recipe_applies_to_element_type(recipe, element.element_type)
                )
                cells.append(
                    CoverageCell(
                        element_type=element.element_type,
                        role=role,
                        energy=energy,
                        recipe_count=len(recipe_ids),
                        recipe_ids=recipe_ids,
                        is_gap=not recipe_ids,
                    )
                )

    prominence = {element.element_type: element.prominence_share for element in element_types}
    role_order = {role: index for index, role in enumerate(COVERAGE_ROLES)}
    energy_order = {energy: index for index, energy in enumerate(COVERAGE_ENERGIES)}
    gaps = tuple(
        sorted(
            (cell for cell in cells if cell.is_gap),
            key=lambda cell: (
                -prominence[cell.element_type],
                role_order[cell.role],
                energy_order[cell.energy],
                cell.element_type,
            ),
        )
    )
    covered_cells = sum(not cell.is_gap for cell in cells)
    total_cells = len(cells)
    gap_cells = len(gaps)
    summary = CoverageSummary(
        total_cells=total_cells,
        covered_cells=covered_cells,
        gap_cells=gap_cells,
        coverage_ratio=covered_cells / total_cells if total_cells else 1.0,
        exit_criterion_met=gap_cells == 0,
    )
    return CoverageReport(
        element_types=element_types,
        unclassified=unclassified,
        cells=tuple(cells),
        gaps=gaps,
        summary=summary,
    )


def build_catalog_coverage_report(
    *,
    layout_path: Path,
    catalog_dir: Path | None = None,
) -> CoverageReport:
    """Load the tracked catalog and a layout XML, then calculate coverage."""
    from twinklr.core.profiling.layout.profiler import LayoutProfiler

    recipes = load_catalog(catalog_dir or DEFAULT_TEMPLATES_DIR)
    layout = LayoutProfiler().profile(layout_path)
    return build_coverage_report(recipes=recipes, models=layout.models)


def format_coverage_table(report: CoverageReport) -> str:
    """Format the report as a prominence-ordered curation worklist."""
    lines = [
        "Catalog coverage: BASE, RHYTHM, and ACCENT only; TRANSITION and SPECIAL are excluded.",
        "Energy axis: LOW, MED, HIGH, BUILD, RELEASE (PEAK is outside this phase's axis).",
        "",
        "Element type coverage (prominence-ranked)",
    ]
    cells_by_type: dict[str, list[CoverageCell]] = {}
    for cell in report.cells:
        cells_by_type.setdefault(cell.element_type, []).append(cell)
    for element in report.element_types:
        lines.append(
            f"{element.element_type}: {element.pixel_count} pixels "
            f"({element.prominence_share:.1%} of display pixels)"
        )
        for cell in cells_by_type[element.element_type]:
            status = "GAP" if cell.is_gap else f"{cell.recipe_count} recipe(s)"
            ids = f" [{', '.join(cell.recipe_ids)}]" if cell.recipe_ids else ""
            lines.append(f"  {cell.role.value:<7} {cell.energy.value:<7} {status}{ids}")
    if report.unclassified:
        lines.extend(["", "Unclassified display models (action required):"])
        lines.extend(
            f"  {model.name} (DisplayAs={model.display_as!r}, {model.pixel_count} pixels)"
            for model in report.unclassified
        )
    lines.extend(
        [
            "",
            (
                f"Summary: {report.summary.covered_cells}/{report.summary.total_cells} cells covered; "
                f"{report.summary.gap_cells} gaps; "
                f"exit criterion met: {report.summary.exit_criterion_met}."
            ),
        ]
    )
    return "\n".join(lines)
