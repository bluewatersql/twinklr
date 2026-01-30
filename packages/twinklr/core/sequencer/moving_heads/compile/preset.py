from typing import Literal, overload

from twinklr.core.sequencer.models.template import (
    BaseTiming,
    Dimmer,
    Geometry,
    Movement,
    PhaseOffset,
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

    # Apply patches if present
    if patch.geometry is not None:
        geometry_dict = deep_merge(geometry_dict, patch.geometry)

    if patch.movement is not None:
        movement_dict = deep_merge(movement_dict, patch.movement)

    if patch.dimmer is not None:
        dimmer_dict = deep_merge(dimmer_dict, patch.dimmer)

    if patch.timing is not None:
        timing_dict = deep_merge(timing_dict, patch.timing)

    # Reconstruct timing (nested structure)
    base_timing = BaseTiming(**timing_dict["base_timing"])

    if timing_dict.get("phase_offset") is not None:
        phase_offset = PhaseOffset(**timing_dict["phase_offset"])
        new_timing = StepTiming(base_timing=base_timing, phase_offset=phase_offset)
    else:
        new_timing = StepTiming(base_timing=base_timing)

    # Create new step with patched components
    return TemplateStep(
        step_id=step.step_id,
        target=step.target,
        timing=new_timing,
        geometry=Geometry(**geometry_dict),
        movement=Movement(**movement_dict),
        dimmer=Dimmer(**dimmer_dict),
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
            new_steps.append(
                TemplateStep(
                    step_id=step.step_id,
                    target=step.target,
                    timing=step.timing,
                    geometry=step.geometry,
                    movement=step.movement,
                    dimmer=step.dimmer,
                )
            )

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
