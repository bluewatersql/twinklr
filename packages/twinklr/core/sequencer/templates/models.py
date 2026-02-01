"""Template reference models for agent context.

Provides lightweight template metadata for agent prompt context without
materializing full template instances.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TemplateRef(BaseModel):
    """Lightweight template reference for agent context.

    Provides just enough information for the agent to make informed
    template selection without including full template definition.
    """

    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(description="Unique template identifier")
    name: str = Field(description="Human-readable template name")
    description: str = Field(default="", description="Brief template description")
    template_type: str = Field(description="Template type/category")
    tags: list[str] = Field(
        default_factory=list, description="Tags for search and categorization"
    )


def template_ref_from_info(info: Any) -> TemplateRef:
    """Convert TemplateInfo to TemplateRef.

    Args:
        info: TemplateInfo from template registry

    Returns:
        TemplateRef for agent context
    """
    return TemplateRef(
        template_id=info.template_id,
        name=info.name,
        description="",  # TemplateInfo doesn't have description
        template_type=info.template_type if hasattr(info.template_type, "value") else str(info.template_type),
        tags=list(info.tags),
    )
