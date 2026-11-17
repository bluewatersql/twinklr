from typing import Literal, overload

from twinklr.core.sequencer.models.template import (
    DimmerPulse,
    Movement,
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
    movement_dict = step.movement.model_dump()
    dimmer_dict = step.dimmer.model_dump() if step.dimmer is not None else {}
    timing_dict = step.timing.model_dump()

    if patch.movement is not None:
        movement_dict = deep_merge(movement_dict, patch.movement)
    if patch.dimmer is not None:
        dimmer_dict = deep_merge(dimmer_dict, patch.dimmer)
    if patch.timing is not None:
        timing_dict = deep_merge(timing_dict, patch.timing)

    return step.model_copy(
        update={
            "timing": StepTiming(**timing_dict),
            "movement": Movement(**movement_dict),
            "dimmer": DimmerPulse(**dimmer_dict) if dimmer_dict else None,
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

    Creates a new Template with the preset's step patches applied.
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
        repeat=template.repeat,
        steps=new_steps,
        metadata=template.metadata,
        overlays=template.overlays,
    )

    if return_provenance:
        return new_template, provenance
    return new_template
