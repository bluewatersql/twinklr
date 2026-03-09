"""Deterministic validation for recipe candidates and enrichments."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import ValidationError

from twinklr.core.recipe_builder.models import (
    CandidateValidationResult,
    MetadataEnrichmentCandidate,
    RecipeCandidate,
    ValidationIssue,
    ValidationReport,
)
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe
from twinklr.core.sequencer.vocabulary import GroupTemplateType, LaneKind

# All known xLights effect types (matching effect_map.py names)
_KNOWN_EFFECT_TYPES: frozenset[str] = frozenset(
    {
        "Color Wash",
        "Bars",
        "Spirals",
        "Twinkle",
        "Meteors",
        "Fan",
        "Shockwave",
        "Strobe",
        "On",
        "Off",
        "Snowflakes",
        "Marquee",
        "SingleStrand",
        "Ripple",
        "Fire",
        "Pinwheel",
        "Morph",
        "Butterfly",
        "Galaxy",
        "Plasma",
        "Lightning",
        "Wave",
        "Pictures",
        "DMX",
        "Glediator",
    }
)

_TEMPLATE_TO_LANE: dict[GroupTemplateType, LaneKind] = {
    GroupTemplateType.BASE: LaneKind.BASE,
    GroupTemplateType.RHYTHM: LaneKind.RHYTHM,
    GroupTemplateType.ACCENT: LaneKind.ACCENT,
}

_STRUCTURAL_FIELDS: frozenset[str] = frozenset(
    {
        "layers",
        "palette_spec",
        "timing",
        "template_type",
        "visual_intent",
        "recipe_version",
        "recipe_id",
    }
)


def validate_all(
    recipe_candidates: list[RecipeCandidate],
    metadata_candidates: list[MetadataEnrichmentCandidate],
    library_recipes: list[EffectRecipe],
) -> ValidationReport:
    """Run all checks on all candidates and return an aggregated report."""
    recipe_results = [
        validate_recipe_candidate(c, library_recipes) for c in recipe_candidates
    ]
    metadata_results = [
        validate_metadata_candidate(c, library_recipes) for c in metadata_candidates
    ]

    counts: dict[str, int] = {"error": 0, "warning": 0, "info": 0}
    for result in recipe_results + metadata_results:
        for issue in result.issues:
            counts[issue.severity] = counts.get(issue.severity, 0) + 1

    return ValidationReport(
        generated_at=datetime.now(tz=UTC),
        recipe_candidate_results=recipe_results,
        metadata_candidate_results=metadata_results,
        issue_counts=counts,
    )


def validate_recipe_candidate(
    candidate: RecipeCandidate,
    library_recipes: list[EffectRecipe],
) -> CandidateValidationResult:
    """Run deterministic checks on a single RecipeCandidate."""
    issues: list[ValidationIssue] = []
    recipe = candidate.recipe
    subject = candidate.candidate_id

    # Schema re-validation
    try:
        EffectRecipe.model_validate(recipe.model_dump())
    except (ValidationError, Exception) as exc:
        issues.append(
            ValidationIssue(
                severity="error",
                check_name="schema_validity",
                message=f"Recipe failed schema re-validation: {exc}",
                subject_id=subject,
            )
        )

    # Effect handler compatibility
    for layer in recipe.layers:
        if layer.effect_type not in _KNOWN_EFFECT_TYPES:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    check_name="effect_handler_compatibility",
                    message=(
                        f"Layer '{layer.layer_name}' uses unknown effect_type "
                        f"'{layer.effect_type}'"
                    ),
                    subject_id=subject,
                )
            )

    # Lane compatibility
    if recipe.template_type not in _TEMPLATE_TO_LANE:
        issues.append(
            ValidationIssue(
                severity="warning",
                check_name="lane_compatibility",
                message=f"template_type '{recipe.template_type}' has no standard lane mapping",
                subject_id=subject,
            )
        )

    # Timing sanity
    if recipe.timing.bars_min is not None and recipe.timing.bars_max is not None:
        if recipe.timing.bars_min > recipe.timing.bars_max:
            issues.append(
                ValidationIssue(
                    severity="error",
                    check_name="timing_sanity",
                    message=(
                        f"bars_min ({recipe.timing.bars_min}) > "
                        f"bars_max ({recipe.timing.bars_max})"
                    ),
                    subject_id=subject,
                )
            )

    # Duplicate check against library
    library_ids = {r.recipe_id for r in library_recipes}
    if recipe.recipe_id in library_ids:
        issues.append(
            ValidationIssue(
                severity="error",
                check_name="duplicate_check",
                message=f"recipe_id '{recipe.recipe_id}' already exists in library",
                subject_id=subject,
            )
        )
    else:
        for lib_recipe in library_recipes:
            if (
                lib_recipe.effect_family == recipe.effect_family
                and lib_recipe.style_markers.energy_affinity == recipe.style_markers.energy_affinity
                and abs(lib_recipe.style_markers.complexity - recipe.style_markers.complexity) <= 0.1
            ):
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        check_name="duplicate_check",
                        message=(
                            f"Similar to existing recipe '{lib_recipe.recipe_id}' "
                            f"(same family '{recipe.effect_family}', "
                            f"same energy, complexity within 0.1)"
                        ),
                        subject_id=subject,
                    )
                )
                break

    # Metadata completeness
    if not recipe.name:
        issues.append(
            ValidationIssue(
                severity="warning",
                check_name="metadata_completeness",
                message="Recipe name is empty",
                subject_id=subject,
            )
        )
    if not recipe.tags:
        issues.append(
            ValidationIssue(
                severity="warning",
                check_name="metadata_completeness",
                message="Recipe tags is empty",
                subject_id=subject,
            )
        )

    # Effect family coherence
    if recipe.effect_family == "unknown":
        issues.append(
            ValidationIssue(
                severity="warning",
                check_name="effect_family_coherence",
                message="effect_family is 'unknown'",
                subject_id=subject,
            )
        )

    # Layer count sanity
    if len(recipe.layers) == 0:
        issues.append(
            ValidationIssue(
                severity="error",
                check_name="layer_sanity",
                message="Recipe has no layers",
                subject_id=subject,
            )
        )

    passed = not any(i.severity == "error" for i in issues)
    return CandidateValidationResult(
        candidate_id=subject,
        issues=issues,
        passed=passed,
    )


def validate_metadata_candidate(
    candidate: MetadataEnrichmentCandidate,
    library_recipes: list[EffectRecipe],
) -> CandidateValidationResult:
    """Run deterministic checks on a single MetadataEnrichmentCandidate."""
    issues: list[ValidationIssue] = []
    subject = candidate.candidate_id

    library_ids = {r.recipe_id for r in library_recipes}
    if candidate.target_recipe_id not in library_ids:
        issues.append(
            ValidationIssue(
                severity="error",
                check_name="target_exists",
                message=(
                    f"target_recipe_id '{candidate.target_recipe_id}' "
                    f"does not exist in library"
                ),
                subject_id=subject,
            )
        )

    patch = candidate.proposed_metadata_patch
    forbidden = _STRUCTURAL_FIELDS & patch.keys()
    if forbidden:
        issues.append(
            ValidationIssue(
                severity="error",
                check_name="patch_structural_fields",
                message=f"Patch contains structural fields: {sorted(forbidden)}",
                subject_id=subject,
            )
        )

    if not patch:
        issues.append(
            ValidationIssue(
                severity="error",
                check_name="patch_not_empty",
                message="proposed_metadata_patch is empty",
                subject_id=subject,
            )
        )

    passed = not any(i.severity == "error" for i in issues)
    return CandidateValidationResult(
        candidate_id=subject,
        issues=issues,
        passed=passed,
    )
