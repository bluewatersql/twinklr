"""Prompt building utilities for asset templates.

This module provides functions to assemble complete prompts from AssetTemplate
specifications, applying prompt parts, policies, and negative hints.
"""

from __future__ import annotations

from .models import AssetTemplate


def build_prompt(tpl: AssetTemplate) -> str:
    """
    Build a complete prompt from an AssetTemplate.

    This function assembles the prompt from the template's PromptParts
    and applies the PromptPolicy constraints and negative hints.

    The prompt is assembled in this order:
    1. Preamble
    2. Subject (required)
    3. Style block
    4. Composition
    5. Background
    6. Lighting
    7. Constraints (from parts + policy + negative hints)
    8. Output intent

    Args:
        tpl: The AssetTemplate to build a prompt from

    Returns:
        Complete assembled prompt string with newline separators
    """
    p = tpl.prompt_parts

    # Build constraints from parts, policy, and negative hints
    constraints_bits: list[str] = []

    # Add explicit constraints from prompt parts
    if p.constraints.strip():
        constraints_bits.append(p.constraints.strip())

    # Add constraints from prompt policy
    if tpl.prompt_policy.require_high_contrast:
        constraints_bits.append("Readability: high contrast, bold shapes.")

    if tpl.prompt_policy.require_low_detail:
        constraints_bits.append("Keep detail low; avoid tiny patterns and thin lines.")

    if tpl.prompt_policy.require_clean_edges:
        constraints_bits.append("Clean edges; simple shading; no texture noise.")

    if tpl.prompt_policy.require_no_text:
        constraints_bits.append("Avoid: text.")

    if tpl.prompt_policy.require_no_logos:
        constraints_bits.append("Avoid: logos.")

    if tpl.prompt_policy.require_no_watermarks:
        constraints_bits.append("Avoid: watermarks.")

    # Add negative hints
    if tpl.negative_hints:
        constraints_bits.append("Avoid: " + ", ".join(tpl.negative_hints) + ".")

    # Assemble parts with newline separators, filtering out empty parts
    parts = [
        p.preamble.strip(),
        p.subject.strip(),
        p.style_block.strip(),
        p.composition.strip(),
        p.background.strip(),
        p.lighting.strip(),
        " ".join([c for c in constraints_bits if c]),
        p.output_intent.strip(),
    ]

    return "\n".join([x for x in parts if x])
