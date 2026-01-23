"""Prompt template rendering with Jinja2."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class RenderError(Exception):
    """Raised when template rendering fails."""

    pass


class PromptRenderer:
    """Renders prompt templates using Jinja2.

    Features:
    - Jinja2 strict mode (StrictUndefined)
    - Fail-fast on missing variables
    - Full Jinja2 feature set (conditionals, loops, filters)
    """

    def __init__(self) -> None:
        """Initialize prompt renderer."""
        try:
            from jinja2 import Environment, StrictUndefined

            self.env = Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
            self.use_jinja2 = True
            logger.debug("PromptRenderer initialized with Jinja2")

        except ImportError:
            logger.warning("Jinja2 not available, using simple renderer")
            self.use_jinja2 = False

    def render(self, template: str, variables: dict[str, Any]) -> str:
        """Render template with variables.

        Args:
            template: Template string (Jinja2 format)
            variables: Variables for template rendering

        Returns:
            Rendered template string

        Raises:
            RenderError: If rendering fails (missing variables, syntax errors, etc.)
        """
        if not self.use_jinja2:
            # Fallback to simple renderer
            return self._simple_render(template, variables)

        try:
            from jinja2 import TemplateSyntaxError, UndefinedError

            jinja_template = self.env.from_string(template)
            return jinja_template.render(**variables)

        except UndefinedError as e:
            raise RenderError(f"Missing variable in template: {e}") from e

        except TemplateSyntaxError as e:
            raise RenderError(f"Invalid template syntax: {e}") from e

        except Exception as e:
            raise RenderError(f"Template rendering failed: {e}") from e

    def _simple_render(self, template: str, variables: dict[str, Any]) -> str:
        """Simple $var renderer (fallback if Jinja2 not available).

        Args:
            template: Template with $var placeholders
            variables: Variables for substitution

        Returns:
            Rendered string

        Raises:
            RenderError: If variable not found
        """
        result = template

        # Handle $$ escape first (replace with placeholder)
        result = result.replace("$$", "\x00DOLLAR\x00")

        # Replace $var with values
        for key, value in variables.items():
            placeholder = f"${key}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))

        # Check for unresolved variables
        import re

        unresolved = re.findall(r"\$(\w+)", result)
        if unresolved:
            raise RenderError(f"Unresolved variables in template: {unresolved}")

        # Restore escaped dollars
        result = result.replace("\x00DOLLAR\x00", "$")

        return result
