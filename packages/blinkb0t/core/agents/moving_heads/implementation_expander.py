"""LLM-based implementation expansion for precise execution details.

Expands strategic plan with millisecond timing and targeting.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.agents.moving_heads.context import ContextShaper, Stage, build_semantic_groups
from blinkb0t.core.agents.moving_heads.models_agent_plan import AgentImplementation, AgentPlan
from blinkb0t.core.api.llm.openai.client import OpenAIClient
from blinkb0t.core.config.loader import load_app_config, load_fixture_group
from blinkb0t.core.config.models import JobConfig

logger = logging.getLogger(__name__)


class ImplementationResult(BaseModel):
    """Result of implementation expansion.

    Converted from dataclass to Pydantic for validation and serialization.
    """

    success: bool = Field(description="Whether implementation expansion succeeded")
    implementation: AgentImplementation | None = Field(
        default=None, description="Generated implementation if successful"
    )
    error: str | None = Field(default=None, description="Error message if failed")
    tokens_used: int = Field(ge=0, description="Number of tokens used")
    original_messages: list[dict[str, str]] | None = Field(
        default=None, description="Original messages for conversational refinement"
    )

    model_config = ConfigDict(
        frozen=False,
        extra="forbid",
        arbitrary_types_allowed=True,
    )


class ImplementationExpander:
    """Expands strategic plan to detailed implementation.

    Responsibilities (SIMPLIFIED for renderer_v2):
    1. Add fixture targeting details (choreographic decision)
    2. Handle layered effects
    3. Output bar-level timing (no conversion to ms)

    Renderer determines:
    - Bar→ms conversion (single source of truth via BeatGrid)
    - Transitions (based on curve types and boundaries)

    Example:
        expander = ImplementationExpander(
            job_config=job_config,
            openai_client=openai_client
        )

        result = expander.expand_implementation(
            plan=approved_plan,
            song_features=song_features,
            seq_fingerprint=seq_fingerprint
        )

        if result.success:
            implementation = result.implementation
    """

    def __init__(
        self,
        job_config: JobConfig,
        openai_client: OpenAIClient,
    ) -> None:
        """Initialize implementation expander.

        Args:
            job_config: Job configuration
            openai_client: OpenAI API client
        """
        self.app_config = load_app_config()
        self.job_config = job_config
        self.openai_client = openai_client
        self.context_shaper = ContextShaper(job_config=job_config)

        # Get agent config
        self.agent_config = job_config.agent.implementation_agent

        logger.debug("ImplementationExpander initialized")

    def expand_implementation(
        self,
        plan: AgentPlan,
        song_features: dict[str, Any],
        seq_fingerprint: dict[str, Any],
        template_metadata: list[dict[str, Any]],
    ) -> ImplementationResult:
        """Expand plan to detailed implementation.

        Args:
            plan: Approved plan from Stage 1
            song_features: Audio analysis
            seq_fingerprint: Sequence fingerprint
            template_metadata: Template metadata

        Returns:
            ImplementationResult with implementation or error
        """
        logger.info("Expanding plan to implementation...")

        # Shape context for implementation stage
        shaped_context = self.context_shaper.shape_for_stage(
            stage=Stage.IMPLEMENTATION,
            song_features=song_features,
            seq_fingerprint=seq_fingerprint,
            template_metadata=template_metadata,
            plan=plan.model_dump(),
        )

        logger.info(
            f"Context shaped: {shaped_context.token_estimate} tokens "
            f"(reduced {shaped_context.reduction_pct:.1f}%)"
        )

        # Build prompt
        prompt = self._build_prompt(shaped_context.data)

        # Log prompt for validation
        logger.info(f"Shaped context keys: {list(shaped_context.data.keys())}")
        logger.info(f"Timing data: {shaped_context.data.get('timing', {})}")
        logger.info(
            f"Plan sections count: {len(shaped_context.data.get('plan', {}).get('sections', []))}"
        )
        logger.info(f"Implementation prompt: {prompt}")

        # Call LLM
        try:
            logger.debug("Calling LLM for implementation expansion")

            # Build messages list for OpenAI API
            messages: list[dict[str, str]] = [
                {"role": "developer", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt},
            ]

            response = self.openai_client.generate_json(
                messages=messages,
                model=self.agent_config.model,
                temperature=self.agent_config.temperature,
            )

            logger.info(f"Implementation expanded: {json.dumps(response, indent=2)}")

            # Parse and validate
            implementation = self._parse_response(json.dumps(response))

            logger.info(f"Implementation expanded: {len(implementation.sections)} sections")

            return ImplementationResult(
                success=True,
                implementation=implementation,
                error=None,
                tokens_used=self.openai_client.get_total_token_usage().total_tokens,
                original_messages=messages,
            )
        except Exception as e:
            logger.error(f"Implementation expansion failed: {e}")
            return ImplementationResult(
                success=False,
                implementation=None,
                error=str(e),
                tokens_used=self.openai_client.get_total_token_usage().total_tokens,
                original_messages=None,
            )

    # ========================================================================
    # Private Methods - Prompt Building
    # ========================================================================

    def _get_system_prompt(self) -> str:
        """Load system prompt from file using version resolution."""
        from pathlib import Path

        from blinkb0t.core.config.models import SequencingVersionConfig

        # Get version config for prompt version
        version_config = SequencingVersionConfig()

        # Extract major version (e.g., "1.0.0" -> "v1")
        major_version = version_config.prompt.split(".")[0]
        version_dir = f"v{major_version}"

        # Build path relative to this file
        prompt_path = Path(__file__).parent / "prompts" / version_dir / "implementation_system.txt"
        return prompt_path.read_text()

    def _build_prompt(self, shaped_context: dict[str, Any]) -> str:
        """Build implementation prompt.

        Args:
            shaped_context: Context from ContextShaper (Stage.IMPLEMENTATION)

        Returns:
            Formatted prompt string
        """
        from pathlib import Path

        from blinkb0t.core.agents.moving_heads.models_agent_plan import AgentImplementation
        from blinkb0t.core.agents.schema_utils import get_json_schema_example
        from blinkb0t.core.config.models import SequencingVersionConfig

        # Load user prompt template
        version_config = SequencingVersionConfig()
        major_version = version_config.prompt.split(".")[0]
        version_dir = f"v{major_version}"
        prompt_path = Path(__file__).parent / "prompts" / version_dir / "implementation_user.txt"
        prompt_template = prompt_path.read_text()

        # Extract key data
        target, target_groups = self._format_semantic_groups()

        plan = shaped_context.get("plan", {})
        song_map = shaped_context.get("song_map", {})

        # Generate JSON schema from Pydantic model
        json_schema = get_json_schema_example(AgentImplementation)

        # Format prompt with parameters
        return prompt_template.format(
            overall_strategy=plan.get("overall_strategy", ""),
            plan_sections=self._format_plan_sections(plan),
            song_map_formatted=self._format_song_map(song_map),
            target_groups=target,
            target_groups_detail=target_groups,
            json_schema=json_schema,
        )

    def _format_semantic_groups(self) -> tuple[str, str]:
        fixtures = load_fixture_group(self.job_config.fixture_config_path)
        fixture_ids = [f.fixture_id for f in fixtures]
        semantic_groups = build_semantic_groups(fixture_ids)

        targets = ",".join(semantic_groups.keys())

        # Add fixture count to each group
        groups_with_counts = {}
        for group_name, group_fixture_ids in semantic_groups.items():
            groups_with_counts[group_name] = {
                "fixtures": group_fixture_ids,
                "count": len(group_fixture_ids),
            }

        return targets, json.dumps(groups_with_counts, indent=2)

    def _format_plan_sections(self, plan: dict[str, Any]) -> str:
        """Format plan sections for prompt."""
        sections = plan.get("sections", [])
        lines = []
        for section in sections:
            templates = section.get("templates", [])
            lines.append(
                f"- {section.get('name')}: bars {section.get('start_bar')}-{section.get('end_bar')}, "
                f"templates={templates}, energy={section.get('energy_level')}, "
                f'reasoning="{section.get("reasoning", "")}"'
            )
        return "\n".join(lines)

    def _format_plan(self, plan: dict[str, Any]) -> str:
        """Format plan for prompt."""
        sections = plan.get("sections", [])

        lines = []
        for section in sections:
            lines.append(f"\n**{section.get('name')}**")
            lines.append(f"- Bars: {section.get('start_bar')}-{section.get('end_bar')}")
            lines.append(f"- Role: {section.get('section_role')}")
            lines.append(f"- Energy: {section.get('energy_level')}")
            lines.append(f"- Template: {section.get('template_id')}")
            lines.append(f"- Params: {section.get('params')}")
            lines.append(f"- Pose: {section.get('base_pose')}")
            lines.append(f"- Target: {section.get('target')}")

        return "\n".join(lines)

    def _format_song_map(self, song_map: dict[str, Any]) -> str:
        """Format unified song map for prompt.
        Args:
            song_map: Unified song map from build_unified_song_map
        Returns:
            Formatted string with metadata, sections, and bar events
        """
        if not song_map:
            return "No song map available"

        lines = []

        # Metadata
        metadata = song_map.get("metadata", {})
        lines.append("### Metadata")
        lines.append(f"- Duration: {metadata.get('duration_s', 0):.1f}s")
        lines.append(f"- Tempo: {metadata.get('tempo_bpm', 0):.1f} BPM")
        lines.append(f"- Total Bars: {metadata.get('total_bars', 0)}")
        lines.append(f"- Total Events: {metadata.get('total_events', 0)}")
        lines.append("")

        # Section summaries
        sections = song_map.get("sections", [])
        if sections:
            lines.append("### Section Summaries")
            for section in sections:
                bar_range = section.get("bar_range", [0, 0])
                time_range = section.get("time_range", [0, 0])

                # Defensive: ensure bar_range and time_range are lists
                if not isinstance(bar_range, list):
                    bar_range = [0, 0]
                if not isinstance(time_range, list):
                    time_range = [0, 0]

                lines.append(
                    f"- **{section.get('label')}** (bars {bar_range[0]}-{bar_range[1]}): "
                    f"{time_range[0]:.1f}s - {time_range[1]:.1f}s, "
                    f"energy={section.get('energy_rank', 0):.2f}"
                )
            lines.append("")

        # Bar events (this is what LLM uses for timing lookups)
        events = song_map.get("events", [])
        if events:
            lines.append("### Bar Timeline (Use this for timing conversion)")
            lines.append("Each event shows: bar #, timestamp (seconds), and section context")
            lines.append("")
            for event in events:
                bar = event.get("bar")
                t_s = event.get("t_s", 0)
                t_ms = int(t_s * 1000)
                section_info = event.get("section")
                section_label = section_info.get("label") if section_info else "unknown"
                lines.append(f"Bar {bar}: {t_ms}ms ({section_label})")
            lines.append("")

        # Sequence timing events (if available)
        seq_timing = song_map.get("sequence_timing")
        if seq_timing:
            lines.append("### Sequence Timing Events")
            for event in seq_timing[:20]:  # Limit to first 20
                lines.append(
                    f"- {event.get('t_ms')}ms: {event.get('label')} ({event.get('track')})"
                )

        return "\n".join(lines)

    def _format_timing_tracks(self, timing_tracks: dict[str, Any]) -> str:
        """Format timing tracks for prompt."""
        if not timing_tracks:
            return "No timing tracks available"

        lines = []
        for track_name, events in timing_tracks.items():
            lines.append(f"\n**{track_name}**")
            lines.append(f"Events: {len(events)}")
            if events:
                # Events have 'time_ms' not 'start_ms'
                first_time = events[0].get("time_ms", 0)
                last_time = events[-1].get("time_ms", 0)
                lines.append(f"First event: {first_time}ms")
                lines.append(f"Last event: {last_time}ms")

        return "\n".join(lines)

    # ========================================================================
    # Private Methods - Response Parsing
    # ========================================================================

    def _parse_response(self, response_content: str) -> AgentImplementation:
        """Parse LLM response into Implementation object.

        Args:
            response_content: JSON string from LLM

        Returns:
            Validated Implementation object

        Raises:
            json.JSONDecodeError: If invalid JSON
            ValidationError: If validation fails
        """
        # Parse JSON
        impl_json = json.loads(response_content)

        # Validate with Pydantic
        implementation = AgentImplementation.model_validate(impl_json)

        logger.debug(f"Implementation parsed: {len(implementation.sections)} sections")

        return implementation
