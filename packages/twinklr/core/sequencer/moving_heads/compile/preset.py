from typing import Literal, overload

from twinklr.core.sequencer.models.template import (
    BaseTiming,
    Color,
    Dimmer,
    Geometry,
    Gobo,
    Movement,
    PhaseOffset,
    Shutter,
    StepPatch,
    StepTiming,
    Template,
    TemplatePreset,
    TemplateStep,
)
from twinklr.core.sequencer.moving_heads.compile.patch import deep_merge


def apply_step_patch(step: TemplateStep, patch: StepPatch) -> TemplateStep:
    """Apply a step patch to a template step.

    Creates a new TemplateStep with patched values. The original
    step is not modified.

    Args:
        step: The original step to patch.
        patch: The patch containing overrides.

    Returns:
        A new TemplateStep with patches applied.
    """
    # Convert step components to dicts for merging
    geometry_dict = step.geometry.model_dump()
    movement_dict = step.movement.model_dump()
    dimmer_dict = step.dimmer.model_dump()
    timing_dict = step.timing.model_dump()
    color_dict = step.color.model_dump() if step.color is not None else None
    shutter_dict = step.shutter.model_dump() if step.shutter is not None else None
    gobo_dict = step.gobo.model_dump() if step.gobo is not None else None

    # Apply patches if present
    if patch.geometry is not None:
        geometry_dict = deep_merge(geometry_dict, patch.geometry)

    if patch.movement is not None:
        movement_dict = deep_merge(movement_dict, patch.movement)

    if patch.dimmer is not None:
        dimmer_dict = deep_merge(dimmer_dict, patch.dimmer)

    if patch.timing is not None:
        timing_dict = deep_merge(timing_dict, patch.timing)

    if patch.color is not None:
        color_dict = deep_merge(color_dict or {}, patch.color)
    if patch.shutter is not None:
        shutter_dict = deep_merge(shutter_dict or {}, patch.shutter)
    if patch.gobo is not None:
        gobo_dict = deep_merge(gobo_dict or {}, patch.gobo)

    # Reconstruct timing (nested structure)
    base_timing = BaseTiming(**timing_dict["base_timing"])

    if timing_dict.get("phase_offset") is not None:
        phase_offset = PhaseOffset(**timing_dict["phase_offset"])
        new_timing = StepTiming(base_timing=base_timing, phase_offset=phase_offset)
    else:
        new_timing = StepTiming(base_timing=base_timing)

    # Create new step with patched components
    return step.model_copy(
        update={
            "timing": new_timing,
            "geometry": Geometry(**geometry_dict),
            "movement": Movement(**movement_dict),
            "dimmer": Dimmer(**dimmer_dict),
            "color": Color(**color_dict) if color_dict is not None else None,
            "shutter": Shutter(**shutter_dict) if shutter_dict is not None else None,
            "gobo": Gobo(**gobo_dict) if gobo_dict is not None else None,
        },
        deep=True,
    )


@overload
def apply_preset(
    template: Template,
    preset: TemplatePreset,
    *,
    return_provenance: Literal[False] = ...,
    base_provenance: list[str] | None = ...,
) -> Template: ...


@overload
def apply_preset(
    template: Template,
    preset: TemplatePreset,
    *,
    return_provenance: Literal[True],
    base_provenance: list[str] | None = ...,
) -> tuple[Template, list[str]]: ...


def apply_preset(
    template: Template,
    preset: TemplatePreset,
    *,
    return_provenance: bool = False,
    base_provenance: list[str] | None = None,
) -> Template | tuple[Template, list[str]]:
    """Apply a preset to a template.

    Creates a new Template with preset defaults and step patches applied.
    The original template is not modified.

    Args:
        template: The original template to apply preset to.
        preset: The preset containing overrides.
        return_provenance: If True, return provenance tracking info.
        base_provenance: Starting provenance list (for chaining presets).

    Returns:
        If return_provenance is False: New Template with preset applied.
        If return_provenance is True: Tuple of (Template, provenance list).
    """
    # Initialize provenance
    provenance: list[str] = list(base_provenance) if base_provenance else []
    if not provenance:
        provenance.append(f"template:{template.template_id}")

    # Merge defaults
    new_defaults = deep_merge(template.defaults, preset.defaults)

    # Apply step patches
    new_steps: list[TemplateStep] = []

    for step in template.steps:
        if step.step_id in preset.step_patches:
            patched_step = apply_step_patch(step, preset.step_patches[step.step_id])
            new_steps.append(patched_step)
        else:
            # No patch for this step - create new instance to maintain immutability
            new_steps.append(step.model_copy(deep=True))

    # Track provenance
    provenance.append(f"preset:{preset.preset_id}")

    # Create new template with patched values
    new_template = Template(
        template_id=template.template_id,
        version=template.version,
        name=template.name,
        category=template.category,
        roles=list(template.roles),
        repeat=template.repeat,
        defaults=new_defaults,
        steps=new_steps,
        metadata=template.metadata,
    )

    if return_provenance:
        return new_template, provenance
    return new_template
