"""LLM-based plan generation for template selection.

Generates strategic choreography plans using template library.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from blinkb0t.core.agents.moving_heads.context import ContextShaper, Stage, build_library_metadata
from blinkb0t.core.agents.moving_heads.models_agent_plan import AgentPlan
from blinkb0t.core.agents.schema_utils import get_json_schema_example
from blinkb0t.core.api.llm.openai.client import OpenAIClient, Verbosity
from blinkb0t.core.config.loader import load_app_config
from blinkb0t.core.config.models import JobConfig, SequencingVersionConfig

logger = logging.getLogger(__name__)


class PlanGenerationResult(BaseModel):
    """Result of plan generation.

    Converted from dataclass to Pydantic for:
    - Automatic validation
    - JSON serialization
    - Better error messages
    """

    success: bool = Field(description="Whether plan generation succeeded")
    plan: AgentPlan | None = Field(default=None, description="Generated plan if successful")
    error: str | None = Field(default=None, description="Error message if failed")
    tokens_used: int = Field(ge=0, description="Number of tokens used")
    retries: int = Field(ge=0, description="Number of retries attempted")
    original_messages: list[dict[str, str]] | None = Field(
        default=None, description="Original messages for conversational refinement"
    )

    model_config = ConfigDict(
        frozen=False,
        extra="forbid",
        arbitrary_types_allowed=True,  # Allow AgentPlan
    )


class PlanGenerationError(Exception):
    """Raised when plan generation fails."""

    pass


class PlanGenerator:
    """Generates template-based choreography plans using LLM.

    Responsibilities:
    1. Build planning prompt with shaped context
    2. Call LLM (configurable model/temp)
    3. Parse plan JSON
    4. Validate plan structure
    5. Handle LLM errors/retries

    Example:
        generator = PlanGenerator(
            job_config=job_config,
            openai_client=openai_client
        )

        result = generator.generate_plan(
            song_features=song_features,
            seq_fingerprint=seq_fingerprint,
            template_metadata=template_metadata
        )

        if result.success:
            plan = result.plan
    """

    def __init__(self, job_config: JobConfig, openai_client: OpenAIClient) -> None:
        """Initialize plan generator.

        Args:
            job_config: Job configuration
            openai_client: OpenAI API client
        """
        self.app_config = load_app_config()
        self.job_config = job_config
        self.openai_client = openai_client
        self.context_shaper = ContextShaper(job_config=job_config)

        # Get agent config
        self.agent_config = job_config.agent.plan_agent

        # Load system prompt
        self.system_prompt = self._load_system_prompt()

        logger.debug("PlanGenerator initialized")

    def generate_plan(
        self,
        song_features: dict[str, Any],
        seq_fingerprint: dict[str, Any],
        template_metadata: list[dict[str, Any]],
    ) -> PlanGenerationResult:
        """Generate choreography plan.

        Args:
            song_features: Audio analysis
            seq_fingerprint: Sequence fingerprint
            template_metadata: Template library metadata

        Returns:
            PlanGenerationResult with plan or error
        """
        logger.info("Generating choreography plan...")

        library_metadata = build_library_metadata()

        # Shape context
        shaped_context = self.context_shaper.shape_for_stage(
            stage=Stage.PLAN,
            song_features=song_features,
            seq_fingerprint=seq_fingerprint,
            template_metadata=template_metadata,
            library_metadata=library_metadata,
        )

        logger.info(
            f"Context shaped: {shaped_context.token_estimate} tokens "
            f"(reduced {shaped_context.reduction_pct:.1f}%)"
        )

        # Build prompt
        prompt = self._build_prompt(shaped_context.data)

        logger.info(f"Shaped context keys: {list(shaped_context.data.keys())}")
        logger.info(
            f"Libraries in context: {list(shaped_context.data.get('libraries', {}).keys())}"
        )
        logger.info(f"Template count: {len(template_metadata)}")
        logger.info(f"Plan prompt: {prompt}")

        # Call LLM with retries
        max_retries = 2
        tokens_used = 0

        messages: list[dict[str, str]] = [
            {"role": "developer", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"LLM call attempt {attempt + 1}/{max_retries + 1}")

                response = self.openai_client.generate_json(
                    messages=messages,
                    model=self.agent_config.model,
                    temperature=self.agent_config.temperature,
                    verbosity=Verbosity.HIGH,
                )

                prompt_tokens = self.openai_client.get_total_token_usage().prompt_tokens
                response_tokens = self.openai_client.get_total_token_usage().completion_tokens
                tokens_used = self.openai_client.get_total_token_usage().total_tokens

                logger.info(f"Plan generated: {tokens_used} tokens used")
                logger.info(f"Prompt tokens: {prompt_tokens}")
                logger.info(f"Response tokens: {response_tokens}")
                logger.info(f"Plan generated: {json.dumps(response, indent=2)}")

                # Parse and validate
                plan = self._parse_response(json.dumps(response))

                logger.info(
                    f"Plan generated successfully: {len(plan.sections)} sections, "
                    f"{tokens_used} tokens used"
                )

                return PlanGenerationResult(
                    success=True,
                    plan=plan,
                    error=None,
                    tokens_used=tokens_used,
                    retries=attempt,
                    original_messages=messages,
                )

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"Plan parsing failed (attempt {attempt + 1}): {e}")

                if attempt == max_retries:
                    return PlanGenerationResult(
                        success=False,
                        plan=None,
                        error=f"Failed to parse plan after {max_retries + 1} attempts: {e}",
                        tokens_used=tokens_used,
                        retries=attempt,
                        original_messages=None,
                    )

                # Add clarification for retry
                prompt = self._add_retry_context(prompt, str(e))

            except Exception as e:
                logger.error(f"Plan generation failed: {e}")
                return PlanGenerationResult(
                    success=False,
                    plan=None,
                    error=str(e),
                    tokens_used=tokens_used,
                    retries=attempt,
                    original_messages=None,
                )

        # Should not reach here
        return PlanGenerationResult(
            success=False,
            plan=None,
            error="Unexpected error in plan generation",
            tokens_used=tokens_used,
            retries=max_retries,
            original_messages=None,
        )

    # ========================================================================
    # Private Methods - Prompt Building
    # ========================================================================

    def _load_system_prompt(self) -> str:
        """Load system prompt from file using version resolution."""

        from blinkb0t.core.config.models import SequencingVersionConfig

        # Get version config for prompt version
        version_config = SequencingVersionConfig()

        # Extract major version (e.g., "1.0.0" -> "v1")
        major_version = version_config.prompt.split(".")[0]
        version_dir = f"v{major_version}"

        # Build path relative to this file
        prompt_path = Path(__file__).parent / "prompts" / version_dir / "plan_system.txt"
        return prompt_path.read_text()

    def _build_prompt(self, shaped_context: dict[str, Any]) -> str:
        """Build planning prompt with shaped context.

        Args:
            shaped_context: Context from ContextShaper

        Returns:
            Formatted prompt string
        """

        # Load user prompt template
        version_config = SequencingVersionConfig()
        major_version = version_config.prompt.split(".")[0]
        version_dir = f"v{major_version}"
        prompt_path = Path(__file__).parent / "prompts" / version_dir / "plan_user.txt"
        prompt_template = prompt_path.read_text()

        # Extract key data
        timing = shaped_context.get("timing", {})
        energy = shaped_context.get("energy", {})
        templates = shaped_context.get("templates", [])
        recommendations = shaped_context.get("recommendations", {})
        fingerprint = shaped_context.get("sequence_fingerprint", {})
        # Library metadata is stored under "libraries" key, not "channels"
        libraries = shaped_context.get("libraries", {})

        # Generate JSON schema from Pydantic model (clean, no deprecated fields)
        json_schema = get_json_schema_example(AgentPlan)

        # Format prompt with parameters
        return prompt_template.format(
            duration_s=timing.get("duration_s"),
            tempo_bpm=timing.get("tempo_bpm"),
            time_signature=timing.get("time_signature"),
            bar_count=timing.get("bar_count"),
            beats_per_bar=timing.get("beats_per_bar"),
            energy_summary=self._format_energy_summary(energy),
            template_library=self._format_template_library(templates),
            channel_libraries=self._format_channel_libraries(libraries),
            fingerprint_summary=self._format_fingerprint_summary(fingerprint),
            recommended_bars_per_section=recommendations.get("recommended_bars_per_section"),
            min_sections=recommendations.get("min_sections"),
            max_sections=recommendations.get("max_sections"),
            target_section_duration_s=recommendations.get("target_section_duration_s"),
            json_schema=json_schema,
        )

    def _format_energy_summary(self, energy: dict[str, Any]) -> str:
        """Format energy data for prompt."""
        if not energy:
            return "No energy data available"

        curve = energy.get("curve", [])
        peaks = energy.get("peaks", [])
        stats = energy.get("stats", {})

        lines = []
        lines.append(f"- Range: {stats.get('min', 0):.2f} - {stats.get('max', 1):.2f}")
        lines.append(f"- Average: {stats.get('mean', 0.5):.2f}")

        if peaks:
            lines.append("- Peak moments:")
            for peak in peaks[:3]:
                lines.append(f"  * {peak.get('t_s')}s: {peak.get('val'):.2f}")

        if curve:
            lines.append(f"- Energy curve: {len(curve)} sample points")

        return "\n".join(lines)

    def _format_template_library(self, templates: list[dict[str, Any]]) -> str:
        """Format template library for prompt."""
        if not templates:
            return "No templates available"

        # Group by category
        by_category: dict[str, list[dict[str, Any]]] = {}
        for template in templates:
            category = template.get("category", "unknown")
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(template)

        lines = []
        for category, category_templates in sorted(by_category.items()):
            lines.append(f"\n### {category.upper()}")
            for template in category_templates:
                lines.append(f"\n**{template['template_id']}**")
                lines.append(f"- Name: {template['name']}")
                lines.append(f"- Description: {template['description']}")
                lines.append(f"- Energy Range: {template['energy_range']}")
                lines.append(f"- Recommended For: {', '.join(template['recommended_sections'])}")
                lines.append(f"- Tags: {', '.join(template['tags'])}")
                lines.append(f"- Steps: {template['step_count']}")

        return "\n".join(lines)

    def _format_channel_libraries(self, libraries: dict[str, Any]) -> str:
        """Format library metadata (movements, geometries, dimmers) for prompt."""
        if not libraries:
            return "No library metadata available"

        lines = []

        # Movement patterns
        if "movements" in libraries and libraries["movements"]:
            lines.append("### Movement Patterns")
            for pattern in libraries["movements"][:10]:  # Limit to 10
                lines.append(
                    f"- **{pattern['movement_id']}**: {pattern['name']} "
                    f"({pattern.get('description', '')[:50]})"
                )
            lines.append("")

        # Geometry patterns
        if "geometries" in libraries and libraries["geometries"]:
            lines.append("### Geometry Patterns")
            for pattern in libraries["geometries"][:10]:  # Limit to 10
                lines.append(
                    f"- **{pattern['geometry_id']}**: {pattern['name']} "
                    f"({pattern.get('summary', '')[:50]})"
                )
            lines.append("")

        # Dimmer patterns
        if "dimmers" in libraries and libraries["dimmers"]:
            lines.append("### Dimmer Patterns")
            for pattern in libraries["dimmers"][:10]:  # Limit to 10
                lines.append(
                    f"- **{pattern['dimmer_id']}**: {pattern['name']} "
                    f"({pattern.get('description', '')[:50]})"
                )
            lines.append("")

        if not lines:
            return "No library metadata available"

        return "\n".join(lines)

    def _format_fingerprint_summary(self, fingerprint: dict[str, Any]) -> str:
        """Format sequence fingerprint for prompt."""
        if not fingerprint:
            return "No existing sequence data"

        existing_effects = fingerprint.get("existing_effects", {})
        coverage = fingerprint.get("effect_coverage", {})

        lines = []
        lines.append(f"- Existing effects: {existing_effects.get('total_count', 0)}")
        lines.append(
            f"- Coverage: Pan/Tilt {coverage.get('pan_tilt_pct', 0):.1f}%, "
            f"Dimmer {coverage.get('dimmer_pct', 0):.1f}%"
        )

        if existing_effects.get("by_type"):
            lines.append("- Effect types:")
            for effect_type, count in existing_effects["by_type"].items():
                lines.append(f"  * {effect_type}: {count}")

        return "\n".join(lines)

    def _add_retry_context(self, original_prompt: str, error_msg: str) -> str:
        """Add error context for retry."""
        retry_context = f"""

## RETRY NOTICE
The previous response had an error: {error_msg}

Please ensure:
1. Valid JSON format
2. All required fields present
3. Correct data types (numbers, strings, etc.)
4. Template IDs match library
5. Pose IDs are valid abstractions

Try again with corrected output."""

        return original_prompt + retry_context

    # ========================================================================
    # Private Methods - Response Parsing
    # ========================================================================

    def _parse_response(self, response_content: str) -> AgentPlan:
        """Parse LLM response into AgentPlan object.

        Args:
            response_content: JSON string from LLM

        Returns:
            Validated AgentPlan object

        Raises:
            json.JSONDecodeError: If invalid JSON
            ValidationError: If validation fails
        """
        # Parse JSON
        plan_json = json.loads(response_content)

        # Validate with Pydantic
        plan = AgentPlan.model_validate(plan_json)

        logger.debug(
            f"Plan parsed: {len(plan.sections)} sections, "
            f"variety={plan.template_variety_score}, "
            f"energy={plan.energy_alignment_score}"
        )

        return plan
