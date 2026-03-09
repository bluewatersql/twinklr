"""LLM-backed creative recipe generation.

Uses catalog analysis and opportunity context to generate novel,
diverse EffectRecipe candidates via LLM. Falls back to deterministic
generation when no LLM client is available or in dry-run mode.
"""

from __future__ import annotations

import json
import logging
import random
import uuid
from typing import Any

from pydantic import ValidationError

from twinklr.core.recipe_builder.evidence import format_analysis_for_prompt
from twinklr.core.recipe_builder.models import (
    CatalogAnalysis,
    Opportunity,
    RecipeCandidate,
)
from twinklr.core.sequencer.templates.group.models.template import TimingHints
from twinklr.core.sequencer.templates.group.recipe import (
    ColorSource,
    EffectRecipe,
    PaletteSpec,
    RecipeLayer,
    RecipeProvenance,
    StyleMarkers,
)
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    EnergyTarget,
    GroupTemplateType,
    GroupVisualIntent,
    MotionVerb,
    VisualDepth,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a creative lighting designer for xLights holiday and entertainment \
light shows. You generate EffectRecipe JSON specifications that define \
multi-layer composite effects combining xLights effects with motion, \
blending, and color for visually striking lighting sequences.

## Available xLights Effect Types and Their Parameters

Color Wash — Smooth color gradients and transitions
  params: horizontal_fade, vertical_fade, shimmer, cycles, speed

Twinkle — Twinkling/sparkling point lights
  params: count (1-100), steps (1-200), strobe (bool), re_random (bool), style

Fire — Realistic fire/flame simulation
  params: height (1-100), hue_shift (0-100), growth_cycles, grow_with_music (bool), location

Spirals — Rotating spiral patterns
  params: palette_count, movement, rotation, thickness, blend, 3d, grow, shrink

Meteors — Falling meteor/shooting star trails
  params: count (1-100), length (1-100), speed (1-50), swirl_intensity, direction, color_type

Fan — Radiating fan patterns
  params: num_blades, blade_width, revolutions, start_angle, start_radius, end_radius, blend_edges

Shockwave — Expanding burst/shockwave effects
  params: start_radius, end_radius, start_width, end_width, accel, blend_edges

Strobe — Rapid on/off flashing
  params: num_strobes, strobe_duration, strobe_type

Snowflakes — Falling snowflake patterns
  params: count (1-100), speed (1-50), snowflake_type

Marquee — Sequential chase/marquee patterns
  params: band_size, skip_size, speed, stagger, thickness, reverse, wrap_x, wrap_y

SingleStrand — Single strand chase effects
  params: chase_type, speed, color_chase, group_count, chase_rotations, fade_type

Ripple — Concentric ripple patterns
  params: object_to_draw, movement, thickness, cycles, rotation, velocity, spacing

Pinwheel — Rotating pinwheel patterns
  params: arms, arm_size, twist, thickness, speed, offset, style, clockwise, 3d

On — Static solid color
  params: shimmer, shimmer_cycles

## Layer Composition

Each recipe has 1-3 layers that compose visually:
- BACKGROUND: Base ambient layer (typically high density, lower mix on upper layers)
- MIDGROUND: Main visual element
- FOREGROUND: Detail/accent overlay (lower density, ADD or SCREEN blend)
- ACCENT: Momentary emphasis
- TEXTURE: Subtle texture overlay

## Motion Verbs
PULSE, SWEEP, WAVE, RIPPLE, CHASE, STROBE, BOUNCE, SPARKLE, FADE, WIPE, \
TWINKLE, SHIMMER, ROLL, FLIP

## Blend Modes
NORMAL (base layer), ADD (additive brightness), SCREEN (lighten), MASK (cutout)

## Color Modes and Palette Roles
Modes: MONOCHROME, DICHROME, TRIAD, ANALOGOUS, FULL_SPECTRUM
Roles: "primary", "accent", "secondary"
color_source per layer: "palette_primary", "palette_accent", "explicit", "white_only"

## Energy Targets
LOW (ambient/relaxed), MED (moderate), HIGH (energetic), BUILD (rising tension), \
RELEASE (falling tension), PEAK (climactic moment)

## Template Types
BASE (sustained looks, 4-64 bars), RHYTHM (beat-synced, 1-16 bars), \
ACCENT (short bursts, 1-4 bars), TRANSITION (between sections), \
SPECIAL (unique moments)

## Visual Intents
ABSTRACT, IMAGERY, HYBRID, TEXTURE, GEOMETRIC, ORGANIC

## Design Principles
- Combine different effect types across layers for visual depth and contrast
- Use complementary blend modes (ADD foreground over NORMAL background)
- Match motion verbs to the visual feel (SHIMMER for ambient, CHASE for energetic)
- Vary density across layers (denser backgrounds, sparser foregrounds)
- Use meaningful effect parameters — don't leave params empty
- timing_offset_beats on upper layers creates staggered visual interest
- Multi-layer recipes are more interesting than single-layer ones
- Consider how the recipe would look on real LED fixtures

## Output Format
Output a single EffectRecipe as valid JSON. Do NOT wrap in markdown code fences."""


def _build_user_prompt(
    opportunity: Opportunity,
    analysis: CatalogAnalysis,
    example_recipes: list[EffectRecipe],
) -> str:
    """Build a user prompt for a specific opportunity."""
    parts: list[str] = []

    # Catalog context
    parts.append("## Current Catalog Analysis")
    parts.append(format_analysis_for_prompt(analysis))
    parts.append("")

    # Opportunity
    parts.append("## Creative Opportunity")
    parts.append(opportunity.description)
    if opportunity.context:
        parts.append(f"Context: {opportunity.context}")
    parts.append("")

    # Constraints from opportunity
    constraints: list[str] = []
    if opportunity.target_effect_type:
        constraints.append(
            f"- Primary effect_type in at least one layer MUST be: \"{opportunity.target_effect_type}\""
        )
    if opportunity.target_energy:
        constraints.append(
            f"- energy_affinity MUST be: \"{opportunity.target_energy}\""
        )
    if opportunity.target_template_type:
        constraints.append(
            f"- template_type MUST be: \"{opportunity.target_template_type}\""
        )
    if opportunity.target_motions:
        constraints.append(
            f"- At least one layer MUST use motion: {opportunity.target_motions}"
        )
    if constraints:
        parts.append("## Constraints")
        parts.extend(constraints)
        parts.append("")

    # Examples
    if example_recipes:
        parts.append("## Example Recipes (for format reference — create something DIFFERENT)")
        for i, recipe in enumerate(example_recipes[:3], 1):
            recipe_json = recipe.model_dump(mode="json")
            parts.append(f"### Example {i}: {recipe.name}")
            parts.append(json.dumps(recipe_json, indent=2))
            parts.append("")

    # Schema guidance
    parts.append("## Required JSON Schema Fields")
    parts.append(json.dumps(_SCHEMA_GUIDE, indent=2))
    parts.append("")

    # Final instructions
    parts.append("## Instructions")
    parts.append("Generate ONE creative, original EffectRecipe JSON for this opportunity.")
    parts.append("- recipe_id format: \"rb_{effect_family}_{short_descriptor}_v1\"")
    parts.append("- effect_type in layers MUST be one of the valid xLights effects listed above")
    parts.append("- Be creative with layer composition, motion verbs, and parameters")
    parts.append("- Use 1-3 layers for visual depth — prefer 2+ layers")
    parts.append("- params values should use {\"value\": <static_value>} format")
    parts.append("- complexity (0.0-1.0) should reflect the recipe's visual complexity")
    parts.append("- provenance.source must be \"generated\"")

    return "\n".join(parts)


_SCHEMA_GUIDE: dict[str, Any] = {
    "recipe_id": "string (rb_{family}_{descriptor}_v1)",
    "name": "string (display name)",
    "description": "string (creative description of the visual effect)",
    "recipe_version": "1.0.0",
    "effect_family": "string (snake_case family name, e.g. 'fire', 'twinkle', 'ripple_wave')",
    "template_type": "BASE | RHYTHM | ACCENT | TRANSITION | SPECIAL",
    "visual_intent": "ABSTRACT | IMAGERY | HYBRID | TEXTURE | GEOMETRIC | ORGANIC",
    "tags": ["list", "of", "descriptive", "tags"],
    "timing": {
        "bars_min": "int (1-256)",
        "bars_max": "int (1-256)",
        "emphasize_downbeats": "bool",
    },
    "palette_spec": {
        "mode": "MONOCHROME | DICHROME | TRIAD | ANALOGOUS | FULL_SPECTRUM",
        "palette_roles": ["primary", "accent (optional)"],
    },
    "layers": [
        {
            "layer_index": "int (0=bottom)",
            "layer_name": "string",
            "layer_depth": "BACKGROUND | MIDGROUND | FOREGROUND | ACCENT | TEXTURE",
            "effect_type": "string (xLights effect name from list above)",
            "blend_mode": "NORMAL | ADD | SCREEN | MASK",
            "mix": "float (0.0-1.0)",
            "params": {"param_name": {"value": "static_value"}},
            "motion": ["MOTION_VERB"],
            "density": "float (0.0-1.0)",
            "color_source": "palette_primary | palette_accent | white_only",
        },
    ],
    "provenance": {"source": "generated"},
    "style_markers": {
        "complexity": "float (0.0-1.0)",
        "energy_affinity": "LOW | MED | HIGH | BUILD | RELEASE | PEAK",
    },
}


# ---------------------------------------------------------------------------
# LLM generation
# ---------------------------------------------------------------------------


def _select_diverse_examples(
    recipes: list[EffectRecipe],
    opportunity: Opportunity,
    count: int = 3,
) -> list[EffectRecipe]:
    """Select diverse example recipes for the prompt.

    Picks recipes that demonstrate format variety while avoiding
    recipes too similar to the target opportunity.
    """
    if not recipes:
        return []

    candidates = list(recipes)
    random.shuffle(candidates)

    selected: list[EffectRecipe] = []
    used_effects: set[str] = set()
    used_energies: set[str] = set()

    for recipe in candidates:
        if len(selected) >= count:
            break

        primary_effect = recipe.layers[0].effect_type if recipe.layers else ""
        energy = recipe.style_markers.energy_affinity.value

        # Skip if too similar to target
        if (
            opportunity.target_effect_type
            and primary_effect == opportunity.target_effect_type
        ):
            continue

        # Prefer diversity
        if primary_effect in used_effects and energy in used_energies:
            continue

        selected.append(recipe)
        used_effects.add(primary_effect)
        used_energies.add(energy)

    # Fill remaining slots if we filtered too aggressively
    if len(selected) < count:
        for recipe in candidates:
            if recipe not in selected and len(selected) < count:
                selected.append(recipe)

    return selected[:count]


def _parse_llm_response(raw: dict[str, Any]) -> EffectRecipe:
    """Parse and validate raw LLM JSON output into an EffectRecipe.

    Applies fixups for common LLM output quirks before validation.
    """
    # Fixup: ensure layers is a list of dicts with proper types
    if "layers" in raw:
        for layer in raw["layers"]:
            # Convert params to ParamValue format if needed
            if "params" in layer:
                fixed_params: dict[str, Any] = {}
                for k, v in layer["params"].items():
                    if isinstance(v, dict):
                        fixed_params[k] = v
                    else:
                        fixed_params[k] = {"value": v}
                layer["params"] = fixed_params

            # Ensure motion is a list
            if "motion" in layer and isinstance(layer["motion"], str):
                layer["motion"] = [layer["motion"]]

    # Fixup: ensure tags is a list
    if "tags" in raw and isinstance(raw["tags"], str):
        raw["tags"] = [raw["tags"]]

    return EffectRecipe.model_validate(raw)


def generate_with_llm(
    opportunities: list[Opportunity],
    analysis: CatalogAnalysis,
    catalog_recipes: list[EffectRecipe],
    llm_client: Any,
    model: str = "gpt-4.1",
    temperature: float = 0.9,
) -> list[RecipeCandidate]:
    """Generate recipe candidates using LLM for each opportunity.

    Args:
        opportunities: Identified creative opportunities.
        analysis: Catalog analysis for prompt context.
        catalog_recipes: Full catalog for example selection.
        llm_client: OpenAIClient instance.
        model: LLM model to use.
        temperature: Sampling temperature (higher = more creative).

    Returns:
        List of successfully generated RecipeCandidate instances.
    """
    candidates: list[RecipeCandidate] = []

    for opp in opportunities:
        examples = _select_diverse_examples(catalog_recipes, opp)
        user_prompt = _build_user_prompt(opp, analysis, examples)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            logger.info(
                "Generating recipe for opportunity %s: %s",
                opp.opportunity_id,
                opp.category,
            )

            raw = llm_client.generate_json(
                messages=messages,
                model=model,
                temperature=temperature,
            )

            recipe = _parse_llm_response(raw)

            candidate = RecipeCandidate(
                candidate_id=uuid.uuid4().hex[:12],
                source_opportunity_id=opp.opportunity_id,
                recipe=recipe,
                generation_mode="llm",
                rationale=f"LLM generation for: {opp.description}",
                confidence=0.8,
            )
            candidates.append(candidate)
            logger.info(
                "Generated recipe '%s' (effect_family=%s, energy=%s, layers=%d)",
                recipe.name,
                recipe.effect_family,
                recipe.style_markers.energy_affinity.value,
                len(recipe.layers),
            )

        except ValidationError as exc:
            logger.warning(
                "LLM output failed validation for opportunity %s: %s",
                opp.opportunity_id,
                exc,
            )
        except Exception as exc:
            logger.warning(
                "LLM generation failed for opportunity %s: %s",
                opp.opportunity_id,
                exc,
            )

    return candidates


# ---------------------------------------------------------------------------
# Deterministic fallback
# ---------------------------------------------------------------------------

_ENERGY_MAP: dict[str, EnergyTarget] = {
    "LOW": EnergyTarget.LOW,
    "MED": EnergyTarget.MED,
    "HIGH": EnergyTarget.HIGH,
}

_EFFECT_DEFAULTS: dict[str, dict[str, Any]] = {
    "Color Wash": {
        "blend": BlendMode.NORMAL,
        "depth": VisualDepth.BACKGROUND,
        "density": 0.85,
        "motion": [MotionVerb.FADE],
        "params": {"horizontal_fade": {"value": 50}, "shimmer": {"value": True}},
    },
    "Twinkle": {
        "blend": BlendMode.SCREEN,
        "depth": VisualDepth.FOREGROUND,
        "density": 0.4,
        "motion": [MotionVerb.SPARKLE],
        "params": {"count": {"value": 15}, "steps": {"value": 40}},
    },
    "Fire": {
        "blend": BlendMode.ADD,
        "depth": VisualDepth.MIDGROUND,
        "density": 0.7,
        "motion": [MotionVerb.SHIMMER],
        "params": {"height": {"value": 50}, "hue_shift": {"value": 10}},
    },
    "Spirals": {
        "blend": BlendMode.ADD,
        "depth": VisualDepth.MIDGROUND,
        "density": 0.6,
        "motion": [MotionVerb.SWEEP],
        "params": {"palette_count": {"value": 3}, "rotation": {"value": 10}},
    },
    "Meteors": {
        "blend": BlendMode.ADD,
        "depth": VisualDepth.FOREGROUND,
        "density": 0.3,
        "motion": [MotionVerb.SWEEP],
        "params": {"count": {"value": 5}, "length": {"value": 30}, "speed": {"value": 10}},
    },
    "Shockwave": {
        "blend": BlendMode.ADD,
        "depth": VisualDepth.ACCENT,
        "density": 0.5,
        "motion": [MotionVerb.RIPPLE],
        "params": {"start_radius": {"value": 1}, "end_radius": {"value": 200}, "accel": {"value": 3}},
    },
    "Ripple": {
        "blend": BlendMode.SCREEN,
        "depth": VisualDepth.MIDGROUND,
        "density": 0.5,
        "motion": [MotionVerb.RIPPLE],
        "params": {"thickness": {"value": 20}, "cycles": {"value": 3}},
    },
    "Snowflakes": {
        "blend": BlendMode.SCREEN,
        "depth": VisualDepth.FOREGROUND,
        "density": 0.35,
        "motion": [MotionVerb.FADE],
        "params": {"count": {"value": 20}, "speed": {"value": 10}},
    },
    "Pinwheel": {
        "blend": BlendMode.ADD,
        "depth": VisualDepth.MIDGROUND,
        "density": 0.6,
        "motion": [MotionVerb.SWEEP],
        "params": {"arms": {"value": 4}, "twist": {"value": 30}, "speed": {"value": 10}},
    },
}


def _deterministic_recipe(opportunity: Opportunity) -> EffectRecipe:
    """Build a deterministic recipe from an opportunity.

    Uses the opportunity constraints to build a valid recipe without
    LLM involvement. Produces diverse output by varying parameters
    based on the opportunity category and targets.
    """
    effect_type = opportunity.target_effect_type or "Twinkle"
    energy_str = opportunity.target_energy or "MED"
    energy = _ENERGY_MAP.get(energy_str, EnergyTarget.MED)

    template_type_str = opportunity.target_template_type or {
        EnergyTarget.LOW: "BASE",
        EnergyTarget.MED: "RHYTHM",
        EnergyTarget.HIGH: "ACCENT",
    }.get(energy, "BASE")
    template_type = GroupTemplateType(template_type_str)

    # Get effect defaults
    defaults = _EFFECT_DEFAULTS.get(effect_type, _EFFECT_DEFAULTS["Twinkle"])

    # Build motion from opportunity or defaults
    motions = (
        [MotionVerb(m) for m in opportunity.target_motions]
        if opportunity.target_motions
        else defaults["motion"]
    )

    family = effect_type.lower().replace(" ", "_")
    short_id = uuid.uuid4().hex[:6]

    layers = [
        RecipeLayer(
            layer_index=0,
            layer_name=f"{family}_main",
            layer_depth=defaults["depth"],
            effect_type=effect_type,
            blend_mode=defaults["blend"],
            mix=1.0,
            params=defaults["params"],
            motion=motions,
            density=defaults["density"],
            color_source=ColorSource.PALETTE_PRIMARY,
        ),
    ]

    complexity = {
        EnergyTarget.LOW: 0.25,
        EnergyTarget.MED: 0.5,
        EnergyTarget.HIGH: 0.75,
    }.get(energy, 0.5)

    timing_map = {
        GroupTemplateType.BASE: TimingHints(bars_min=4, bars_max=64, emphasize_downbeats=True),
        GroupTemplateType.RHYTHM: TimingHints(bars_min=1, bars_max=16, emphasize_downbeats=True),
        GroupTemplateType.ACCENT: TimingHints(bars_min=1, bars_max=4, emphasize_downbeats=True),
    }

    return EffectRecipe(
        recipe_id=f"rb_{family}_{short_id}_v1",
        name=f"{effect_type} — {energy.value} energy (generated)",
        description=f"Deterministic recipe: {opportunity.description}",
        recipe_version="1.0.0",
        effect_family=family,
        template_type=template_type,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=[family, energy.value.lower(), "generated", opportunity.category],
        timing=timing_map.get(template_type, TimingHints(bars_min=4, bars_max=32)),
        palette_spec=PaletteSpec(mode=ColorMode.DICHROME, palette_roles=["primary", "accent"]),
        layers=tuple(layers),
        provenance=RecipeProvenance(source="generated"),
        style_markers=StyleMarkers(complexity=complexity, energy_affinity=energy),
    )


def generate_deterministic(
    opportunities: list[Opportunity],
) -> list[RecipeCandidate]:
    """Generate recipe candidates deterministically (no LLM).

    Args:
        opportunities: Identified creative opportunities.

    Returns:
        List of RecipeCandidate instances.
    """
    candidates: list[RecipeCandidate] = []

    for opp in opportunities:
        try:
            recipe = _deterministic_recipe(opp)
            candidates.append(
                RecipeCandidate(
                    candidate_id=uuid.uuid4().hex[:12],
                    source_opportunity_id=opp.opportunity_id,
                    recipe=recipe,
                    generation_mode="deterministic",
                    rationale=f"Deterministic generation for: {opp.description}",
                    confidence=0.4,
                ),
            )
        except Exception as exc:
            logger.warning(
                "Deterministic generation failed for opportunity %s: %s",
                opp.opportunity_id,
                exc,
            )

    return candidates


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_candidates(
    opportunities: list[Opportunity],
    analysis: CatalogAnalysis,
    catalog_recipes: list[EffectRecipe],
    llm_client: Any | None = None,
    dry_run: bool = False,
    model: str = "gpt-4.1",
    temperature: float = 0.9,
) -> list[RecipeCandidate]:
    """Generate recipe candidates from opportunities.

    Uses LLM when available; falls back to deterministic generation
    in dry-run mode or when no client is provided.

    Args:
        opportunities: Creative opportunities to generate for.
        analysis: Catalog analysis for prompt context.
        catalog_recipes: Full catalog for example selection.
        llm_client: Optional OpenAIClient instance.
        dry_run: Skip LLM calls, use deterministic fallback.
        model: LLM model to use.
        temperature: Sampling temperature.

    Returns:
        List of RecipeCandidate instances.
    """
    if dry_run or llm_client is None:
        if llm_client is None and not dry_run:
            logger.warning(
                "No LLM client provided — falling back to deterministic generation",
            )
        return generate_deterministic(opportunities)

    return generate_with_llm(
        opportunities=opportunities,
        analysis=analysis,
        catalog_recipes=catalog_recipes,
        llm_client=llm_client,
        model=model,
        temperature=temperature,
    )
