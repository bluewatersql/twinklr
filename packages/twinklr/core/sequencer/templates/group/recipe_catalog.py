"""RecipeCatalog — unified catalog merging builtins and promoted recipes.

Provides the same lookup interface as TemplateCatalog but backed by
EffectRecipe objects. Supports merging auto-converted builtins with
FE-promoted recipes.
"""

from __future__ import annotations

from twinklr.core.sequencer.templates.group.converter import convert_builtin_to_recipe
from twinklr.core.sequencer.templates.group.models.template import GroupPlanTemplate
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe
from twinklr.core.sequencer.vocabulary import GroupTemplateType, LaneKind

# Template type to lane mapping (matches TemplateInfo.compatible_lanes logic)
_TYPE_TO_LANE: dict[GroupTemplateType, LaneKind] = {
    GroupTemplateType.BASE: LaneKind.BASE,
    GroupTemplateType.RHYTHM: LaneKind.RHYTHM,
    GroupTemplateType.ACCENT: LaneKind.ACCENT,
}


class RecipeCatalog:
    """Unified recipe catalog merging builtins and promoted recipes.

    Provides lookup by recipe_id and filtering by lane, matching the
    interface pattern of TemplateCatalog.
    """

    def __init__(self, recipes: list[EffectRecipe]) -> None:
        self._recipes = list(recipes)
        self._by_id: dict[str, EffectRecipe] = {r.recipe_id: r for r in self._recipes}

    @property
    def recipes(self) -> list[EffectRecipe]:
        """All recipes in the catalog."""
        return list(self._recipes)

    def has_recipe(self, recipe_id: str) -> bool:
        """Check if a recipe exists in the catalog."""
        return recipe_id in self._by_id

    def get_recipe(self, recipe_id: str) -> EffectRecipe | None:
        """Get a recipe by ID, or None if not found."""
        return self._by_id.get(recipe_id)

    def list_by_lane(self, lane: LaneKind) -> list[EffectRecipe]:
        """List all recipes compatible with the given lane."""
        return [r for r in self._recipes if _TYPE_TO_LANE.get(r.template_type) == lane]

    @classmethod
    def merge(
        cls,
        builtins: list[EffectRecipe],
        promoted: list[EffectRecipe],
    ) -> RecipeCatalog:
        """Merge builtin and promoted recipes, with promoted taking precedence.

        If a promoted recipe has the same recipe_id as a builtin,
        the promoted version wins (override).

        Args:
            builtins: Auto-converted builtin recipes.
            promoted: FE-promoted recipes.

        Returns:
            Merged RecipeCatalog.
        """
        promoted_ids = {r.recipe_id for r in promoted}
        merged = [b for b in builtins if b.recipe_id not in promoted_ids]
        merged.extend(promoted)
        return cls(recipes=merged)

    @classmethod
    def from_builtins_and_promoted(
        cls,
        builtins: list[GroupPlanTemplate],
        promoted: list[EffectRecipe] | None = None,
    ) -> RecipeCatalog:
        """Build a unified catalog from builtin templates and optional promoted recipes.

        Converts builtins to EffectRecipe via ``convert_builtin_to_recipe``,
        then merges with promoted recipes (promoted take precedence on ID collision).

        Args:
            builtins: Builtin GroupPlanTemplate instances.
            promoted: Optional FE-promoted EffectRecipe instances.

        Returns:
            Unified RecipeCatalog.
        """
        converted = [convert_builtin_to_recipe(t) for t in builtins]
        return cls.merge(converted, promoted or [])
