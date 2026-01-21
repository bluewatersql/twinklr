"""Template loading with validation and parameter substitution.

Loads template JSON files and validates them against Pydantic models
and Phase 0 library enums. Supports parameter substitution for
template reusability.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from blinkb0t.core.domains.sequencing.libraries.moving_heads.dimmers import (
    DIMMER_LIBRARY,
    DimmerID,
)
from blinkb0t.core.domains.sequencing.libraries.moving_heads.geometry import (
    GEOMETRY_LIBRARY,
    GeometryID,
)
from blinkb0t.core.domains.sequencing.libraries.moving_heads.movements import (
    MOVEMENT_LIBRARY,
    MovementID,
)
from blinkb0t.core.domains.sequencing.models.templates import Template

logger = logging.getLogger(__name__)


class TemplateLoadError(Exception):
    """Raised when template loading fails."""

    pass


class TemplateValidationError(Exception):
    """Raised when template validation fails."""

    pass


class TemplateLoader:
    """Loads and validates multi-step templates from JSON.

    Responsibilities:
    1. Load JSON files from template directory
    2. Validate against Pydantic models
    3. Verify pattern IDs against library enums
    4. Substitute template parameters
    5. Cache loaded templates

    Example:
        loader = TemplateLoader(template_dir="data/v2/templates")

        # Load with parameter substitution
        template = loader.load_template(
            "energetic_fan_pulse",
            params={"intensity": "DRAMATIC"}
        )

        # Use loaded template
        for step in template.steps:
            print(f"Step {step.step_id}: {step.movement_id}")
    """

    def __init__(
        self,
        template_dir: str | Path,
        enable_cache: bool = True,
    ):
        """Initialize template loader.

        Args:
            template_dir: Directory containing template JSON files
            enable_cache: Whether to cache loaded templates
        """
        self.template_dir = Path(template_dir)
        self.enable_cache = enable_cache
        self._cache: dict[str, Template] = {}

        if not self.template_dir.exists():
            raise TemplateLoadError(f"Template directory does not exist: {self.template_dir}")

        logger.debug(f"TemplateLoader initialized: {self.template_dir}")

    def load_template(
        self,
        template_id: str,
        params: dict[str, str] | None = None,
        force_reload: bool = False,
    ) -> Template:
        """Load template by ID with optional parameter substitution.

        Args:
            template_id: Template identifier (without .json extension)
            params: Template parameters for substitution (e.g., {"intensity": "DRAMATIC"})
            force_reload: Skip cache and reload from disk

        Returns:
            Validated template with parameters substituted

        Raises:
            TemplateLoadError: If template file not found or JSON invalid
            TemplateValidationError: If template validation fails

        Example:
            template = loader.load_template(
                "energetic_fan_pulse",
                params={"intensity": "DRAMATIC", "speed": "FAST"}
            )
        """
        # Check cache (only if no params and cache enabled)
        cache_key = f"{template_id}:{json.dumps(params or {}, sort_keys=True)}"
        if self.enable_cache and not force_reload and cache_key in self._cache:
            logger.debug(f"Returning cached template: {template_id}")
            return self._cache[cache_key]

        # Load JSON file
        template_path = self.template_dir / f"{template_id}.json"
        if not template_path.exists():
            raise TemplateLoadError(
                f"Template file not found: {template_path}\n"
                f"Available templates: {self.list_templates()}"
            )

        try:
            with template_path.open() as f:
                template_json = json.load(f)
        except json.JSONDecodeError as e:
            raise TemplateLoadError(f"Invalid JSON in template {template_id}: {e}") from e

        # Substitute parameters
        if params:
            template_json = self._substitute_parameters(template_json, params)

        # Validate and parse with Pydantic
        try:
            template = Template.model_validate(template_json)
        except ValidationError as e:
            raise TemplateValidationError(
                f"Template validation failed for {template_id}:\n{e}"
            ) from e

        # Validate pattern IDs against libraries
        self._validate_pattern_ids(template, template_id)

        # Cache if enabled
        if self.enable_cache:
            self._cache[cache_key] = template

        logger.info(
            f"Loaded template: {template_id} ({len(template.steps)} steps, params={params})"
        )

        return template

    def list_templates(self) -> list[str]:
        """List all available template IDs.

        Returns:
            List of template IDs (without .json extension)
        """
        return [path.stem for path in self.template_dir.glob("*.json")]

    def load_all(self) -> dict[str, Template]:
        """Load and cache all templates.

        Useful for startup preloading to avoid lazy loading delays.

        Returns:
            Dictionary mapping template_id → Template

        Example:
            loader = TemplateLoader(template_dir="data/v2/templates")
            all_templates = loader.load_all()

            # All templates now cached
            template = loader.load_template("energetic_fan_pulse")  # From cache
        """
        all_templates = {}
        template_ids = self.list_templates()

        logger.info(f"Loading all templates: {len(template_ids)} templates")

        for template_id in template_ids:
            try:
                template = self.load_template(template_id)
                all_templates[template_id] = template
            except Exception as e:
                logger.error(f"Failed to load template '{template_id}': {e}")
                # Continue loading other templates

        logger.info(f"Loaded {len(all_templates)} templates successfully")

        return all_templates

    def get_template_metadata(self, template_id: str) -> dict[str, Any]:
        """Get template metadata with step and timing information.

        Includes steps for context enrichment (movement/geometry/dimmer summaries).

        Args:
            template_id: Template identifier

        Returns:
            Template metadata dict with steps and timing
        """
        template_path = self.template_dir / f"{template_id}.json"
        if not template_path.exists():
            raise TemplateLoadError(f"Template not found: {template_id}")

        with template_path.open() as f:
            template_json: dict[str, Any] = json.load(f)

        return {
            "template_id": template_json.get("template_id"),
            "name": template_json.get("name"),
            "category": template_json.get("category"),
            "metadata": template_json.get("metadata", {}),
            "step_count": len(template_json.get("steps", [])),
            "steps": template_json.get("steps", []),
            "timing": template_json.get("timing", {}),
        }

    def get_all_metadata(self) -> list[dict[str, Any]]:
        """Get metadata for all templates without loading full templates.

        Useful for LLM context building - provides compact view of all
        available templates for intelligent selection.

        Returns:
            List of template metadata dicts

        Example:
            loader = TemplateLoader(template_dir="data/v2/templates")
            metadata = loader.get_all_metadata()

            # Use in LLM prompt
            for meta in metadata:
                print(f"{meta['name']}: {meta['metadata']['description']}")
        """
        metadata_list = []
        template_ids = self.list_templates()

        for template_id in template_ids:
            try:
                metadata = self.get_template_metadata(template_id)
                metadata_list.append(metadata)
            except Exception as e:
                logger.warning(f"Failed to load metadata for '{template_id}': {e}")
                # Continue with other templates

        return metadata_list

    def clear_cache(self) -> None:
        """Clear template cache.

        Useful after updating template files or for memory management.
        """
        self._cache.clear()
        logger.debug("Template cache cleared")

    # ========================================================================
    # Private Methods
    # ========================================================================

    def _substitute_parameters(
        self, template_json: dict[str, Any], params: dict[str, str]
    ) -> dict[str, Any]:
        """Recursively substitute {{param}} placeholders with values.

        Args:
            template_json: Template dict (possibly nested)
            params: Parameter dict (e.g., {"intensity": "DRAMATIC"})

        Returns:
            Template dict with substitutions applied

        Example:
            template = {"movement_params": {"intensity": "{{intensity}}"}}
            params = {"intensity": "DRAMATIC"}
            result = _substitute_parameters(template, params)
            # Result: {"movement_params": {"intensity": "DRAMATIC"}}
        """
        # Pattern for matching {{param_name}}
        pattern = re.compile(r"\{\{(\w+)\}\}")

        def substitute_value(value: Any) -> Any:
            """Recursively substitute in value."""
            if isinstance(value, str):
                # Replace all {{param}} with actual values
                def replacer(match: re.Match[str]) -> str:
                    param_name = match.group(1)
                    if param_name in params:
                        return params[param_name]
                    # Leave unchanged if param not provided
                    logger.warning(f"Parameter '{param_name}' not provided, leaving as placeholder")
                    return match.group(0)

                return pattern.sub(replacer, value)

            elif isinstance(value, dict):
                return {k: substitute_value(v) for k, v in value.items()}

            elif isinstance(value, list):
                return [substitute_value(item) for item in value]

            else:
                return value

        result: dict[str, Any] = substitute_value(template_json)
        return result

    def _validate_pattern_ids(self, template: Template, template_id: str) -> None:
        """Validate pattern IDs against library enums.

        Args:
            template: Validated template
            template_id: Template identifier (for error messages)

        Raises:
            TemplateValidationError: If pattern ID not found in library
        """
        errors = []

        for step in template.steps:
            # Validate movement_id
            try:
                MovementID(step.movement_id)
            except ValueError:
                if step.movement_id not in MOVEMENT_LIBRARY:
                    errors.append(
                        f"Step '{step.step_id}': Invalid movement_id '{step.movement_id}'. "
                        f"Available: {[m.value for m in MovementID]}"
                    )

            # Validate geometry_id (optional)
            if step.geometry_id:
                try:
                    GeometryID(step.geometry_id)
                except ValueError:
                    if step.geometry_id not in GEOMETRY_LIBRARY:
                        errors.append(
                            f"Step '{step.step_id}': Invalid geometry_id '{step.geometry_id}'. "
                            f"Available: {[g.value for g in GeometryID]}"
                        )

            # Validate dimmer_id
            try:
                DimmerID(step.dimmer_id)
            except ValueError:
                if step.dimmer_id not in DIMMER_LIBRARY:
                    errors.append(
                        f"Step '{step.step_id}': Invalid dimmer_id '{step.dimmer_id}'. "
                        f"Available: {[d.value for d in DimmerID]}"
                    )

        if errors:
            raise TemplateValidationError(
                f"Pattern ID validation failed for template '{template_id}':\n"
                + "\n".join(f"  - {error}" for error in errors)
            )
