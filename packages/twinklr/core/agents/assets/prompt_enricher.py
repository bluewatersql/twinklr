"""LLM prompt enrichment for image asset specs.

Takes image AssetSpecs and uses an LLM to generate rich, detailed
image generation prompts. Text specs skip enrichment entirely.
"""

from __future__ import annotations

import logging
from typing import Any

from twinklr.core.agents.assets.models import AssetSpec, EnrichedPrompt
from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.result import AgentResult
from twinklr.core.agents.spec import AgentMode, AgentSpec

logger = logging.getLogger(__name__)

# Prompt pack path relative to the agents base path
_PROMPT_PACK = "assets/prompts/asset_prompt_enricher"


def build_enricher_spec(
    *,
    model: str = "gpt-5-mini",
    temperature: float = 0.6,
    token_budget: int | None = None,
) -> AgentSpec:
    """Create the agent spec for asset prompt enrichment.

    Args:
        model: LLM model name.
        temperature: Sampling temperature.
        token_budget: Optional per-call token limit.

    Returns:
        AgentSpec configured for oneshot prompt enrichment.
    """
    return AgentSpec(
        name="asset_prompt_enricher",
        prompt_pack=_PROMPT_PACK,
        response_model=EnrichedPrompt,
        mode=AgentMode.ONESHOT,
        model=model,
        temperature=temperature,
        max_schema_repair_attempts=1,
        token_budget=token_budget,
    )


def build_enrichment_variables(
    spec: AssetSpec,
    motif_description: str | None = None,
    motif_usage_notes: str | None = None,
    builtin_prompt: str | None = None,
) -> dict[str, Any]:
    """Build template variables for the enricher prompt pack.

    Routes to narrative-aware variables when spec has narrative_subject,
    otherwise uses the standard motif-based variables.

    Args:
        spec: The AssetSpec to enrich.
        motif_description: Visual description from MotifDefinition.
        motif_usage_notes: Usage notes from MotifDefinition.
        builtin_prompt: Assembled prompt from a matched builtin template.

    Returns:
        Template variables dict for Jinja2 rendering.
    """
    base: dict[str, Any] = {
        "category": spec.category.value,
        "background": spec.background.value,
        "width": spec.width,
        "height": spec.height,
        "style_tags": spec.style_tags,
        "palette_colors": spec.palette_colors,
    }

    if spec.narrative_subject:
        # Narrative asset path — subject-based prompting
        base.update(
            {
                "narrative_subject": spec.narrative_subject,
                "narrative_description": spec.narrative_description or "",
                "story_context": spec.scene_context[0] if spec.scene_context else "",
                "color_guidance": spec.color_guidance,
                "mood": spec.mood,
                "song_title": spec.song_title,
            }
        )
    else:
        # Effect asset path — motif-based prompting (existing)
        base.update(
            {
                "narrative_subject": None,
                "motif_id": spec.motif_id,
                "motif_description": motif_description or "",
                "motif_usage_notes": motif_usage_notes or "",
                "theme_id": spec.theme_id,
                "palette_id": spec.palette_id,
                "target_roles": spec.target_roles,
                "content_tags": spec.content_tags,
                "scene_context": spec.scene_context,
                "builtin_prompt": builtin_prompt,
            }
        )

    return base


async def enrich_spec(
    spec: AssetSpec,
    runner: AsyncAgentRunner,
    enricher_spec: AgentSpec,
    *,
    motif_description: str | None = None,
    motif_usage_notes: str | None = None,
    builtin_prompt: str | None = None,
) -> AssetSpec:
    """Enrich an image spec with an LLM-generated prompt.

    Calls the enricher agent to produce a rich image generation prompt
    from the spec's context (motif, theme, scene, etc.).

    Args:
        spec: The image AssetSpec to enrich (must have motif_id).
        runner: AsyncAgentRunner for LLM calls.
        enricher_spec: AgentSpec for the enricher agent.
        motif_description: Visual description from MotifDefinition.
        motif_usage_notes: Usage notes from MotifDefinition.
        builtin_prompt: Assembled prompt from a matched builtin template.

    Returns:
        New AssetSpec with prompt and negative_prompt populated.

    Raises:
        RuntimeError: If LLM call fails after repair attempts.
    """
    variables = build_enrichment_variables(
        spec,
        motif_description=motif_description,
        motif_usage_notes=motif_usage_notes,
        builtin_prompt=builtin_prompt,
    )

    agent_result: AgentResult = await runner.run(spec=enricher_spec, variables=variables)

    if not agent_result.success or agent_result.data is None:
        raise RuntimeError(f"Enricher failed for spec {spec.spec_id}: {agent_result.error_message}")

    enriched = agent_result.data
    if not isinstance(enriched, EnrichedPrompt):
        raise RuntimeError(
            f"Enricher returned unexpected type {type(enriched).__name__} for spec {spec.spec_id}"
        )

    # Return a new frozen spec with prompts populated
    return spec.model_copy(
        update={
            "prompt": enriched.prompt,
            "negative_prompt": enriched.negative_prompt,
        }
    )
