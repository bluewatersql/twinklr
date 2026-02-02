"""Deterministic prompt builder for asset templates.

Assembles complete prompts from AssetTemplate specifications.
NO LLM involved - purely deterministic string assembly.
"""

from twinklr.core.sequencer.templates.assets.models import AssetTemplate, PromptPolicy


def policy_to_constraint_text(policy: PromptPolicy) -> list[str]:
    """Convert PromptPolicy flags to constraint text lines.

    Args:
        policy: PromptPolicy with constraint flags.

    Returns:
        List of constraint text lines.
    """
    lines: list[str] = []

    if policy.require_high_contrast:
        lines.append("High contrast required")
    if policy.require_low_detail:
        lines.append("Low detail, simple shapes preferred")
    if policy.require_clean_edges:
        lines.append("Clean, crisp edges (no blur)")
    if policy.require_no_text:
        lines.append("CRITICAL: No text, letters, or words")
    if policy.require_no_logos:
        lines.append("CRITICAL: No brand logos or trademarks")
    if policy.require_no_watermarks:
        lines.append("CRITICAL: No watermarks")
    if policy.require_seam_safe:
        lines.append("CRITICAL: Seamless tiling required (tileable on all edges)")

    return lines


def build_prompt(template: AssetTemplate) -> str:
    """Build complete prompt from AssetTemplate (deterministic).

    Assembles prompt parts in order:
    1. preamble
    2. subject (REQUIRED)
    3. style_block
    4. composition
    5. background
    6. lighting
    7. constraints (from parts + policy + negative hints)
    8. output_intent

    Empty parts are omitted. Sections separated by double newlines.

    Args:
        template: AssetTemplate to build prompt from.

    Returns:
        Complete prompt string.

    Example:
        >>> template = AssetTemplate(...)
        >>> prompt = build_prompt(template)
        >>> print(prompt)
        Create a Christmas light show background

        Night sky with subtle gradient and scattered stars

        Simple, clean, low detail
        ...
    """
    parts_list: list[str] = []

    # 1. Preamble (optional)
    if template.prompt_parts.preamble:
        parts_list.append(template.prompt_parts.preamble)

    # 2. Subject (REQUIRED)
    parts_list.append(template.prompt_parts.subject)

    # 3. Style (optional)
    if template.prompt_parts.style_block:
        parts_list.append(template.prompt_parts.style_block)

    # 4. Composition (optional)
    if template.prompt_parts.composition:
        parts_list.append(template.prompt_parts.composition)

    # 5. Background (optional)
    if template.prompt_parts.background:
        parts_list.append(template.prompt_parts.background)

    # 6. Lighting (optional)
    if template.prompt_parts.lighting:
        parts_list.append(template.prompt_parts.lighting)

    # 7. Constraints (parts + policy + negative)
    constraint_lines: list[str] = []

    # From prompt_parts.constraints
    if template.prompt_parts.constraints:
        constraint_lines.append(template.prompt_parts.constraints)

    # From policy flags
    policy_lines = policy_to_constraint_text(template.prompt_policy)
    constraint_lines.extend(policy_lines)

    # From negative_hints
    if template.negative_hints:
        constraint_lines.append(f"Avoid: {', '.join(template.negative_hints)}")

    if constraint_lines:
        parts_list.append("\n".join(constraint_lines))

    # 8. Output intent (optional)
    if template.prompt_parts.output_intent:
        parts_list.append(template.prompt_parts.output_intent)

    # Join with double newlines
    return "\n\n".join(parts_list)


def build_negative_prompt(template: AssetTemplate) -> str:
    """Build negative prompt from negative_hints.

    Args:
        template: AssetTemplate with negative_hints.

    Returns:
        Negative prompt string (comma-separated).

    Example:
        >>> template = AssetTemplate(negative_hints=["text", "logos", "watermarks"])
        >>> neg_prompt = build_negative_prompt(template)
        >>> print(neg_prompt)
        "logos, text, watermarks"
    """
    return ", ".join(template.negative_hints)
