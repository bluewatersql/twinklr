"""Template instantiation utilities for converting templates into planning skeletons.

This module provides functions to convert GroupPlanTemplate instances into
GroupPlanSkeleton objects and generate AssetRequests from AssetSlots.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .models import GroupPlanTemplate, LayerRole


class AssetRequest(BaseModel):
    """
    GroupPlanner -> AssetCreation handoff stub.

    This represents a request for an asset to be created or selected,
    derived from a template's AssetSlot specification.
    """

    request_id: str
    slot_id: str
    slot_type: str
    preferred_tags: list[str] = Field(default_factory=list)
    prompt_hint: str | None = None
    defaults: dict = Field(default_factory=dict)


class GroupPlanLayer(BaseModel):
    """Layer specification in a group plan skeleton."""

    layer: LayerRole
    motifs: list[str] = Field(default_factory=list)
    motions: list[str] = Field(default_factory=list)
    notes: str | None = None


class GroupPlanSkeleton(BaseModel):
    """
    Intermediate representation of a group plan derived from a template.

    This skeleton contains the structural elements from the template,
    ready to be populated with timing, placement, and rendering details
    by the GroupPlanner agent.
    """

    schema_version: str = "group_plan_skeleton.v1"
    template_id: str
    group_id: str
    projection: dict
    constraints: dict
    layers: list[GroupPlanLayer] = Field(default_factory=list)
    asset_requests: list[AssetRequest] = Field(default_factory=list)


def instantiate_group_template(tpl: GroupPlanTemplate, group_id: str) -> GroupPlanSkeleton:
    """
    Instantiate a GroupPlanTemplate into a GroupPlanSkeleton with AssetRequests.

    This function:
    1. Extracts layer recipes and converts them to GroupPlanLayer format
    2. Generates AssetRequest instances from AssetSlots
    3. Captures projection and constraint settings
    4. Returns a skeleton ready for the GroupPlanner to populate with timing/placement

    Args:
        tpl: The template to instantiate
        group_id: The display group ID this template is being applied to

    Returns:
        GroupPlanSkeleton with layers and asset requests
    """
    # Convert layer recipes to simplified layer format
    layers = [
        GroupPlanLayer(
            layer=r.layer,
            motifs=list(r.motifs),
            motions=[m.value for m in r.motion],
            notes=r.notes,
        )
        for r in tpl.layer_recipe
    ]

    # Generate asset requests from slots
    asset_requests: list[AssetRequest] = []
    for i, slot in enumerate(tpl.asset_slots):
        asset_requests.append(
            AssetRequest(
                request_id=f"{group_id}:{tpl.template_id}:{slot.slot_id}:{i}",
                slot_id=slot.slot_id,
                slot_type=slot.slot_type.value,
                preferred_tags=list(slot.preferred_tags),
                prompt_hint=slot.prompt_hint,
                defaults=slot.defaults.model_dump(mode="json"),
            )
        )

    return GroupPlanSkeleton(
        template_id=tpl.template_id,
        group_id=group_id,
        projection=tpl.projection.model_dump(mode="json"),
        constraints=tpl.constraints.model_dump(mode="json"),
        layers=layers,
        asset_requests=asset_requests,
    )
