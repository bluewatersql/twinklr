"""Context shaping for multi-stage agent orchestration.

Reduces token usage through stage-aware filtering and data consolidation.
Extended in with channel library support.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

# Re-export for backward compatibility
from blinkb0t.core.utils.fixtures import build_semantic_groups  # noqa: F401

if TYPE_CHECKING:
    from blinkb0t.core.config.models import JobConfig
from blinkb0t.core.domains.sequencing.libraries.moving_heads.dimmers import DIMMER_LIBRARY, DimmerID
from blinkb0t.core.domains.sequencing.libraries.moving_heads.geometry import (
    GEOMETRY_LIBRARY,
    GeometryID,
)
from blinkb0t.core.domains.sequencing.libraries.moving_heads.movements import (
    MOVEMENT_LIBRARY,
    MovementID,
)
from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.classification import (
    is_asymmetric,
)

logger = logging.getLogger(__name__)


def build_channel_library_context() -> dict[str, Any]:
    """Build channel library context for LLM planning.

    Extracts metadata from shutter, color, and gobo libraries
    for inclusion in planning prompts.

    Returns:
        Dictionary with channel library metadata

    Example:
        >>> context = build_channel_library_context()
        >>> context["shutter"][0]["pattern_id"]
        'open'
        >>> context["color"][0]["name"]
        'White'
    """
    from blinkb0t.core.domains.sequencing.libraries.channels import (
        ColorLibrary,
        GoboLibrary,
        ShutterLibrary,
    )

    # Use the built-in metadata methods (optimized for LLM context)
    return {
        "shutter": ShutterLibrary.get_all_metadata(),
        "color": ColorLibrary.get_all_metadata(),
        "gobo": GoboLibrary.get_all_metadata(),
    }


def build_template_context_for_llm(
    template_docs: list[Any],
) -> list[dict[str, Any]]:
    """Build compact template context for LLM choreography planning.

    Creates a simplified view of templates suitable for the LLM to make
    categorical selections (template_id + preset_id). Excludes implementation
    details that aren't needed for selection decisions.

    Args:
        template_docs: List of TemplateDoc objects (from Phase 0 models).

    Returns:
        List of compact template entries with:
        - template_id, name, category
        - description, energy_range, tags
        - presets (id, name for each)
        - behavior summary (movement/dimmer patterns)

    Example:
        >>> from blinkb0t.core.sequencer.moving_heads.compile.loader import TemplateLoader
        >>> loader = TemplateLoader()
        >>> loader.load_directory(Path("templates/"))
        >>> docs = [loader.get(tid) for tid in loader.list_templates()]
        >>> context = build_template_context_for_llm(docs)
        >>> context[0]["template_id"]
        'fan_pulse'
    """
    if not template_docs:
        return []

    context: list[dict[str, Any]] = []

    for doc in template_docs:
        template = doc.template
        presets = doc.presets

        # Core identification
        entry: dict[str, Any] = {
            "template_id": template.template_id,
            "name": template.name,
            "category": template.category,
        }

        # Metadata for selection reasoning
        if template.metadata:
            entry["description"] = template.metadata.description or ""
            entry["energy_range"] = template.metadata.energy_range
            entry["tags"] = list(template.metadata.tags)[:5]  # Limit tags
        else:
            entry["description"] = ""
            entry["energy_range"] = None
            entry["tags"] = []

        # Presets available for this template
        entry["presets"] = [{"preset_id": p.preset_id, "name": p.name} for p in presets]

        # Behavior summary for choreography reasoning
        # Extract distinct movement and dimmer patterns from steps
        movement_ids: set[str] = set()
        dimmer_ids: set[str] = set()
        has_phase_offset = False

        for step in template.steps:
            movement_ids.add(step.movement.movement_id)
            dimmer_ids.add(step.dimmer.dimmer_id)
            if step.timing.phase_offset is not None:
                from blinkb0t.core.sequencer.moving_heads.models.template import (
                    PhaseOffsetMode,
                )

                if step.timing.phase_offset.mode != PhaseOffsetMode.NONE:
                    has_phase_offset = True

        entry["behavior"] = {
            "movement_patterns": sorted(movement_ids),
            "dimmer_patterns": sorted(dimmer_ids),
            "has_chase_effect": has_phase_offset,
            "step_count": len(template.steps),
            "cycle_bars": template.repeat.cycle_bars,
            "repeat_mode": template.repeat.mode.value,
        }

        context.append(entry)

    return context


class Stage(str, Enum):
    """Agent stages for context shaping."""

    PLAN = "plan"
    VALIDATE = "validate"
    IMPLEMENTATION = "implementation"
    JUDGE = "judge"
    REFINEMENT = "refinement"


class ShapedContext(BaseModel):
    """Shaped context for a specific stage.

    Converted from dataclass to Pydantic for validation and serialization.
    """

    stage: Stage = Field(description="Agent stage this context is for")
    data: dict[str, Any] = Field(description="Shaped context data")
    token_estimate: int = Field(ge=0, description="Estimated token count")
    reduction_pct: float = Field(ge=0.0, le=100.0, description="Percentage reduction from original")

    model_config = ConfigDict(frozen=True, extra="forbid")


class TokenEstimator:
    """Estimates token counts for context data.

    Uses rough heuristics:
    - 1 token ≈ 4 characters (English text)
    - JSON overhead: ~20% more tokens
    """

    @staticmethod
    def estimate(data: dict[str, Any]) -> int:
        """Estimate token count for data.

        Args:
            data: Dictionary to estimate

        Returns:
            Estimated token count
        """
        json_str = json.dumps(data)
        char_count = len(json_str)

        # 1 token ≈ 4 chars, add 20% for JSON overhead
        token_estimate = int((char_count / 4) * 1.2)

        return token_estimate


class ContextShaper:
    """Shapes context for stage-aware token reduction.

    Responsibilities:
    1. Shape audio features (25k → 1.5k)
    2. Shape sequence fingerprint (15k → 1k)
    3. Shape template metadata (15k → 1.5k)
    4. Stage-aware filtering
    5. Token estimation and reporting

    Token Reduction Strategy:
    - **Audio Features**: Consolidate timing arrays, keep only essential metadata
    - **Sequence Fingerprint**: Extract timing tracks, discard channel data
    - **Template Metadata**: Keep template IDs, names, energy ranges; drop verbose descriptions
    - **Stage Filtering**: Each stage sees only relevant data (PLAN doesn't need implementation details)

    Stage-Specific Filtering:
    - **PLAN**: Needs audio summary + timing + templates (for template selection)
    - **VALIDATE**: Needs plan + audio summary (for heuristic checks)
    - **IMPLEMENTATION**: Needs plan + full timing arrays (for bar→ms conversion)
    - **JUDGE**: Needs plan + implementation + audio summary (for evaluation)
    - **REFINEMENT**: Needs plan + implementation + feedback (for improvement)
    """

    def __init__(self, job_config: JobConfig) -> None:
        """Initialize context shaper."""
        self.token_estimator = TokenEstimator()
        self.job_config = job_config
        logger.debug("ContextShaper initialized")

    def shape_for_stage(
        self,
        stage: Stage,
        song_features: dict[str, Any],
        seq_fingerprint: dict[str, Any] | None = None,
        template_metadata: list[dict[str, Any]] | None = None,
        plan: dict[str, Any] | None = None,
        channel_libraries: dict[str, Any] | None = None,
    ) -> ShapedContext:
        """Shape context for specific stage.

        Args:
            stage: Target stage
            song_features: Full audio analysis
            seq_fingerprint: Sequence fingerprint (optional)
            template_metadata: Template metadata list (optional)
            plan: Approved plan (for implementation/judge stages)
            channel_libraries: Channel library metadata (addition)

        Returns:
            ShapedContext with reduced data
        """
        if stage == Stage.PLAN:
            shaped_data = self._shape_for_plan(
                song_features, seq_fingerprint, template_metadata, channel_libraries
            )
        elif stage == Stage.IMPLEMENTATION:
            shaped_data = self._shape_for_implementation(
                song_features, seq_fingerprint, template_metadata, plan
            )
        elif stage == Stage.JUDGE:
            shaped_data = self._shape_for_judge(song_features, plan)
        elif stage == Stage.REFINEMENT:
            shaped_data = self._shape_for_refinement(
                song_features, seq_fingerprint, template_metadata, plan
            )
        else:
            raise ValueError(f"Unknown stage: {stage}")

        # Estimate tokens
        token_estimate = self.token_estimator.estimate(shaped_data)

        # Calculate reduction (rough estimate of original ~55k)
        original_estimate = 55000
        reduction_pct = ((original_estimate - token_estimate) / original_estimate) * 100

        logger.info(
            f"Context shaped for {stage.value}: "
            f"{token_estimate} tokens (reduced {reduction_pct:.1f}%)"
        )

        return ShapedContext(
            stage=stage,
            data=shaped_data,
            token_estimate=token_estimate,
            reduction_pct=reduction_pct,
        )

    # ========================================================================
    # Private Methods - Stage-Specific Shaping
    # ========================================================================

    def _shape_for_plan(
        self,
        song_features: dict[str, Any],
        seq_fingerprint: dict[str, Any] | None,
        template_metadata: list[dict[str, Any]] | None,
        channel_libraries: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Shape context for planning stage.

        Target: ~5k tokens: +1k for channel libraries

        Include:
        - Timing summary
        - Energy curve (downsampled)
        - Template metadata (compact)
        - Sequence fingerprint summary
        - Channel library metadata
        """
        shaped: dict[str, Any] = {}

        # 1. Timing (consolidated) - ~800 tokens
        shaped["timing"] = self._consolidate_timing(song_features)

        # 2. Energy (downsampled) - ~500 tokens
        shaped["energy"] = self._downsample_energy(song_features)

        # 3. Structure (if available) - ~200 tokens
        if "structure" in song_features:
            shaped["structure"] = song_features["structure"].get("sections", [])

        # 4. Template metadata (compact) - ~1500 tokens
        if template_metadata:
            shaped["templates"] = self._compact_template_metadata(template_metadata)

        # 5. Sequence fingerprint (summary) - ~800 tokens
        if seq_fingerprint:
            logger.debug(
                f"Summarizing sequence fingerprint: {json.dumps(self._summarize_fingerprint(seq_fingerprint), indent=2)}"
            )
            shaped["sequence_fingerprint"] = self._summarize_fingerprint(seq_fingerprint)

        # 6. Recommendations (calculated) - ~200 tokens
        shaped["recommendations"] = self._calculate_recommendations(song_features)

        # 7. Channel library metadata - ~1000 tokens
        if channel_libraries:
            shaped["channels"] = self._compact_channel_libraries(channel_libraries)

        return shaped

    def _shape_for_implementation(
        self,
        song_features: dict[str, Any],
        seq_fingerprint: dict[str, Any] | None,
        template_metadata: list[dict[str, Any]] | None,
        plan: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Shape context for implementation stage.

        Target: ~6k tokens

        Include:
        - Approved plan
        - Unified song map (bars/beats/timing aligned in single view)
        - Selected template details
        """
        from blinkb0t.core.domains.audio.context import build_unified_song_map

        shaped: dict[str, Any] = {}

        # 1. Approved plan - ~2k tokens
        shaped["plan"] = plan

        # 2. Unified song map - ~2k tokens
        # This replaces separate bars/beats arrays with a single unified timeline
        # where each event has bar #, beat #, AND timestamp all in one place
        # Use smart sampling to ~80 events (proven size from legacy version)
        shaped["song_map"] = build_unified_song_map(
            song_features=song_features,
            seq_fingerprint=seq_fingerprint,
            resolution="downbeat",  # Use downbeats for efficiency (legacy approach)
            max_events=80,  # Smart sampling to ~80 events (legacy proven size)
        )

        # 3. Selected template details - ~1k tokens
        if template_metadata and plan:
            shaped["template_details"] = self._extract_selected_templates(template_metadata, plan)

        return shaped

    def _shape_for_judge(
        self, song_features: dict[str, Any], plan: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Shape context for judge stage.

        Target: ~5k tokens

        Include:
        - Plan summary
        - High-level audio features
        - Scoring rubric
        """
        shaped: dict[str, Any] = {}

        # 1. Plan summary - ~2k tokens
        shaped["plan_summary"] = self._summarize_plan(plan) if plan else {}

        # 2. High-level audio features - ~500 tokens
        shaped["audio_summary"] = {
            "duration_s": song_features["duration_s"],
            "tempo_bpm": song_features["tempo_bpm"],
            "time_signature": song_features["time_signature"]["time_signature"],
            "bar_count": len(song_features["bars_s"]),
            "energy_stats": song_features.get("energy", {}).get("stats", {}),
        }

        # 3. Scoring rubric - ~2k tokens (defined in prompt)
        # Will be added by JudgePromptBuilder

        return shaped

    def _shape_for_refinement(
        self,
        song_features: dict[str, Any],
        seq_fingerprint: dict[str, Any] | None,
        template_metadata: list[dict[str, Any]] | None,
        plan: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Shape context for refinement stage.

        Target: ~5k tokens

        Similar to planning but includes previous plan for context.
        """
        # Start with plan context
        shaped = self._shape_for_plan(song_features, seq_fingerprint, template_metadata)

        # Add previous plan for reference - ~1k tokens
        if plan:
            shaped["previous_plan"] = plan

        return shaped

    # ========================================================================
    # Private Methods - Data Consolidation
    # ========================================================================

    def _consolidate_timing(self, song_features: dict[str, Any]) -> dict[str, Any]:
        """Consolidate timing data.

        From: Full bars array (~3k tokens)
        To: Summary (first 10, last 10, every 5th in middle) (~800 tokens)
        """
        bars_full = song_features["bars_s"]

        # First 10, last 10, every 5th in middle
        if len(bars_full) <= 20:
            bars_summary = bars_full
        else:
            bars_summary = bars_full[:10] + bars_full[10:-10:5] + bars_full[-10:]

        return {
            "duration_s": song_features["duration_s"],
            "tempo_bpm": song_features["tempo_bpm"],
            "time_signature": song_features["time_signature"]["time_signature"],
            "bar_count": len(bars_full),
            "bars_summary": [
                {"bar": i + 1, "t_s": round(t, 3)} for i, t in enumerate(bars_summary)
            ],
            "beats_per_bar": song_features.get("assumptions", {}).get("beats_per_bar", 4),
        }

    def _downsample_energy(self, song_features: dict[str, Any]) -> dict[str, Any]:
        """Downsample energy curve.

        From: Full energy array (~2k tokens)
        To: 30 points + peaks + stats (~500 tokens)
        """
        energy = song_features.get("energy", {})

        if not energy:
            return {}

        energy_times = energy.get("times_s", [])
        energy_vals = energy.get("phrase_level", [])

        # Downsample to 30 points
        step = max(1, len(energy_vals) // 30)
        energy_curve = [
            {"t_s": round(energy_times[i], 2), "val": round(energy_vals[i], 3)}
            for i in range(0, len(energy_vals), step)
        ][:30]

        return {
            "curve": energy_curve,
            "peaks": energy.get("peaks", [])[:5],  # Top 5 peaks
            "stats": energy.get("stats", {}),
        }

    def _compact_template_metadata(
        self, template_metadata: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Compact template metadata for planning.

        From: Full metadata (~15k tokens)
        To: Enhanced compact version (~2.5k tokens)

        Includes:
        - Basic metadata (name, category, description)
        - Step summaries (movements, geometry, dimmers used)
        - Geometry classification (SYMMETRIC/ASYMMETRIC)
        - Timing information (mode, min duration)
        """

        compacted = []

        for meta in template_metadata:
            compact_meta = {
                "template_id": meta["template_id"],
                "name": meta["name"],
                "category": meta["category"],
                "description": meta["metadata"].get("description", ""),
                "energy_range": meta["metadata"].get("energy_range", [0, 100]),
                "recommended_sections": meta["metadata"].get("recommended_sections", []),
                "tags": meta["metadata"].get("tags", [])[:5],  # First 5 tags
                "step_count": meta["step_count"],
            }

            # Add step summaries if steps are available
            if "steps" in meta:
                steps = meta["steps"]

                # Extract distinct movements
                movement_ids = set()
                for step in steps:
                    movement_ids.add(step.get("movement_id"))

                movements = []
                for mov_id in sorted(movement_ids):
                    try:
                        pattern = MOVEMENT_LIBRARY[MovementID(mov_id)]
                        movements.append({"id": mov_id, "name": pattern.name})
                    except (KeyError, ValueError):
                        movements.append({"id": mov_id, "name": mov_id})

                compact_meta["movements"] = movements

                # Extract distinct geometries
                geometry_ids = set()
                has_asymmetric = False
                for step in steps:
                    geo_id = step.get("geometry_id")
                    if geo_id:
                        geometry_ids.add(geo_id)
                        if is_asymmetric(geo_id):
                            has_asymmetric = True

                geometries = []
                for geo_id in sorted(geometry_ids):
                    try:
                        geometry_def = GEOMETRY_LIBRARY[GeometryID(geo_id)]
                        geometries.append({"id": geo_id, "summary": geometry_def.summary})
                    except (KeyError, ValueError):
                        geometries.append({"id": geo_id, "summary": geo_id})

                compact_meta["geometries"] = geometries
                compact_meta["geometry_type"] = "ASYMMETRIC" if has_asymmetric else "SYMMETRIC"

                # Extract distinct dimmers
                dimmer_ids = set()
                for step in steps:
                    dimmer_ids.add(step.get("dimmer_id"))

                dimmers = []
                for dim_id in sorted(dimmer_ids):
                    try:
                        dimmer_def = DIMMER_LIBRARY[DimmerID(dim_id)]
                        dimmers.append({"id": dim_id, "description": dimmer_def.description})
                    except (KeyError, ValueError):
                        dimmers.append({"id": dim_id, "description": dim_id})

                compact_meta["dimmers"] = dimmers

            # Add timing information if available
            if "timing" in meta:
                timing = meta["timing"]
                compact_meta["timing_type"] = timing.get("mode", "MUSICAL")
                compact_meta["min_duration_bars"] = timing.get("default_duration_bars", 8.0)

            compacted.append(compact_meta)

        return compacted

    def _compact_channel_libraries(self, channel_libraries: dict[str, Any]) -> dict[str, Any]:
        """Compact channel library metadata for planning.

        From: Full library metadata (~2k tokens)
        To: Compact version (~1k tokens)

        Includes:
        - Shutter patterns with energy levels
        - Color presets with moods
        - Gobo patterns with visual density
        """
        compacted: dict[str, Any] = {}

        # Shutter library
        if "shutter" in channel_libraries:
            shutter_patterns = []
            for pattern in channel_libraries["shutter"]:
                shutter_patterns.append(
                    {
                        "pattern_id": pattern["pattern_id"],
                        "name": pattern["name"],
                        "energy_level": pattern.get("energy_level", 5),
                        "description": pattern.get("description", "")[:80],  # Truncate
                    }
                )
            compacted["shutter"] = shutter_patterns

        # Color library
        if "color" in channel_libraries:
            color_presets = []
            for preset in channel_libraries["color"]:
                color_presets.append(
                    {
                        "color_id": preset["color_id"],
                        "name": preset["name"],
                        "mood": preset.get("mood", "neutral"),
                        "category": preset.get("category", "neutral"),
                    }
                )
            compacted["color"] = color_presets

        # Gobo library
        if "gobo" in channel_libraries:
            gobo_patterns = []
            for pattern in channel_libraries["gobo"]:
                gobo_patterns.append(
                    {
                        "gobo_id": pattern["gobo_id"],
                        "name": pattern["name"],
                        "visual_density": pattern.get("visual_density", 5),
                        "category": pattern.get("category", "geometric"),
                    }
                )
            compacted["gobo"] = gobo_patterns

        return compacted

    def _summarize_fingerprint(self, seq_fingerprint: dict[str, Any]) -> dict[str, Any]:
        """Summarize sequence fingerprint.

        From: Full fingerprint (~15k tokens)
        To: Summary (~800 tokens)
        """
        # Map from SequenceAnalyzer output to expected structure
        effect_hist = seq_fingerprint.get("effect_type_histogram", {})
        total_effects = sum(effect_hist.values())

        # Derive timing density from activity_proxy
        activity_proxy = seq_fingerprint.get("activity_proxy", {})
        bins = activity_proxy.get("bins", [])
        bin_s = activity_proxy.get("bin_s", 1.0)

        timing_density = {}
        if bins:
            # Calculate basic density statistics
            import numpy as np

            bins_array = np.array(bins)
            timing_density = {
                "avg_effects_per_second": float(np.mean(bins_array) / bin_s) if bin_s > 0 else 0.0,
                "max_effects_per_second": float(np.max(bins_array) / bin_s) if bin_s > 0 else 0.0,
                "busy_sections_pct": float(np.sum(bins_array > 0) / len(bins_array) * 100)
                if bins
                else 0.0,
            }

        return {
            "existing_effects": {
                "total_count": total_effects,
                "by_type": effect_hist,
                "coverage_pct": 0,  # TODO: Calculate if needed
            },
            "color_palette": [],  # Not extracted by current SequenceAnalyzer
            "timing_density": timing_density,
            "effect_coverage": {
                "pan_tilt_pct": 0,  # Not extracted by current SequenceAnalyzer
                "dimmer_pct": 0,  # Not extracted by current SequenceAnalyzer
            },
        }

    def _calculate_recommendations(self, song_features: dict[str, Any]) -> dict[str, Any]:
        """Calculate planning recommendations.

        Provides guidance based on song characteristics.
        """
        bar_count = len(song_features["bars_s"])
        tempo_bpm = song_features["tempo_bpm"]

        # Target 8-16 bars per section
        recommended_bars_per_section = 12
        avg_section_duration_s = (recommended_bars_per_section * 60 / tempo_bpm) * 4

        min_sections = bar_count // 16
        max_sections = bar_count // 8

        return {
            "recommended_bars_per_section": recommended_bars_per_section,
            "target_section_duration_s": round(avg_section_duration_s, 1),
            "min_sections": min_sections,
            "max_sections": max_sections,
        }

    def _filter_timing_tracks(self, seq_fingerprint: dict[str, Any]) -> dict[str, Any]:
        """Filter timing tracks to beat/phrase tracks only."""
        timing_track_events = seq_fingerprint.get("timing_track_events", {})

        filtered = {}
        for track_name, events in timing_track_events.items():
            if any(kw in track_name.lower() for kw in ["beat", "phrase", "bar"]):
                # Take first 50 events
                filtered[track_name] = events[:50]

        return filtered

    def _extract_selected_templates(
        self, template_metadata: list[dict[str, Any]], plan: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract only templates referenced in plan."""
        # Get template IDs from plan (plans have multiple templates per section)
        plan_template_ids = set()
        for section in plan.get("sections", []):
            templates = section.get("templates", [])
            plan_template_ids.update(templates)

        # Filter metadata
        selected = [meta for meta in template_metadata if meta["template_id"] in plan_template_ids]

        return selected

    def _summarize_plan(self, plan: dict[str, Any] | None) -> dict[str, Any]:
        """Summarize plan for judge context."""
        if not plan:
            return {}

        sections = plan.get("sections", [])

        return {
            "section_count": len(sections),
            "sections": [
                {
                    "name": s.get("name"),
                    "template_id": s.get("template_id"),
                    "bars": f"{s.get('start_bar')}-{s.get('end_bar')}",
                }
                for s in sections
            ],
            "templates_used": list({s.get("template_id") for s in sections}),
        }
