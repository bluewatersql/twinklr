"""RecipeCatalog — unified catalog of EffectRecipe objects.

Provides lookup by recipe_id and filtering by lane, matching the
interface pattern of TemplateCatalog. Loaded from TemplateStore.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import TYPE_CHECKING

from twinklr.core.sequencer.templates.group.recipe import EffectRecipe
from twinklr.core.sequencer.vocabulary import GroupTemplateType, LaneKind

if TYPE_CHECKING:
    from twinklr.core.sequencer.templates.group.store import TemplateStore

logger = logging.getLogger(__name__)

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
        recipe_ids = [recipe.recipe_id for recipe in recipes]
        duplicate_ids = sorted(
            recipe_id for recipe_id in set(recipe_ids) if recipe_ids.count(recipe_id) > 1
        )
        if duplicate_ids:
            raise ValueError(f"RecipeCatalog contains duplicate recipe IDs: {duplicate_ids}")
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

    def to_canonical_data(self) -> list[dict[str, object]]:
        """Return stable JSON-compatible recipe data sorted by identity.

        ``RecipeCatalog`` is an arbitrary Pydantic field type. Without an explicit
        serializer, cache-key construction falls back to ``str(object)`` and embeds a
        process-local memory address.
        """
        return [
            recipe.model_dump(mode="json")
            for recipe in sorted(self._recipes, key=lambda item: item.recipe_id)
        ]

    @property
    def fingerprint(self) -> str:
        """Content fingerprint for cache identities and diagnostics."""
        canonical = json.dumps(
            self.to_canonical_data(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

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
    def from_store(
        cls,
        store: TemplateStore,
        promoted: list[EffectRecipe] | None = None,
    ) -> RecipeCatalog:
        """Build a unified catalog from a TemplateStore.

        Loads all recipes from the JSON-backed store and merges with
        optional promoted recipes.

        Args:
            store: TemplateStore with JSON-backed recipes.
            promoted: Optional FE-promoted EffectRecipe instances.

        Returns:
            Unified RecipeCatalog.
        """
        builtins: list[EffectRecipe] = []
        for recipe_id in store.all_recipe_ids():
            recipe = store.get_recipe(recipe_id)
            if recipe is not None:
                builtins.append(recipe)
            else:
                logger.warning(f"Failed to load recipe {recipe_id} from store")
        return cls.merge(builtins, promoted or [])

    @classmethod
    def from_store_strict(
        cls,
        store: TemplateStore,
        promoted: list[EffectRecipe] | None = None,
    ) -> RecipeCatalog:
        """Build an effective catalog only after every store entry validates."""
        return cls.merge(store.load_all_strict(), promoted or [])
