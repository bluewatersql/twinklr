"""HybridTemplateCompiler — routes to RecipeCompiler or DefaultTemplateCompiler.

Tries the RecipeCompiler first (for recipe IDs from RecipeCatalog).
Falls back to DefaultTemplateCompiler for builtin template IDs
registered in GroupTemplateRegistry.
"""

from __future__ import annotations

from twinklr.core.sequencer.display.composition.models import CompiledEffect, TemplateCompileError
from twinklr.core.sequencer.display.composition.recipe_compiler import RecipeCompiler
from twinklr.core.sequencer.display.composition.template_compiler import (
    DefaultTemplateCompiler,
    TemplateCompileContext,
)
from twinklr.core.sequencer.templates.group.models import GroupPlacement


class HybridTemplateCompiler:
    """Routes compilation to the appropriate compiler based on template_id.

    Recipe IDs (found in RecipeCatalog) are compiled via RecipeCompiler.
    All others fall back to DefaultTemplateCompiler (GroupTemplateRegistry).
    """

    def __init__(
        self,
        recipe_compiler: RecipeCompiler,
        default_compiler: DefaultTemplateCompiler,
    ) -> None:
        self._recipe_compiler = recipe_compiler
        self._default_compiler = default_compiler

    def compile(
        self,
        placement: GroupPlacement,
        context: TemplateCompileContext,
    ) -> list[CompiledEffect]:
        """Compile a placement, routing to the appropriate compiler.

        Args:
            placement: Group placement from the plan.
            context: Compile context with timing, palette, intensity.

        Returns:
            List of CompiledEffect from the chosen compiler.

        Raises:
            TemplateCompileError: If neither compiler recognises the ID.
        """
        if self._recipe_compiler.can_compile(placement.template_id):
            return self._recipe_compiler.compile(placement, context)

        try:
            return self._default_compiler.compile(placement, context)
        except TemplateCompileError:
            raise TemplateCompileError(
                template_id=placement.template_id,
                reason="not found in RecipeCatalog or GroupTemplateRegistry",
            ) from None
