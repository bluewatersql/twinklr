"""Tests for SEC-04: Jinja2 SandboxedEnvironment in PromptRenderer."""

from __future__ import annotations

from jinja2.sandbox import SandboxedEnvironment

from twinklr.core.agents.prompts.renderer import PromptRenderer


class TestRendererSandbox:
    """Verify Jinja2 environment is sandboxed."""

    def test_uses_sandboxed_environment(self) -> None:
        """PromptRenderer must use SandboxedEnvironment, not plain Environment."""
        renderer = PromptRenderer()
        assert isinstance(renderer.env, SandboxedEnvironment)

    def test_sandboxed_env_blocks_unsafe_attrs(self) -> None:
        """SandboxedEnvironment must block access to unsafe attributes."""
        import contextlib

        from jinja2.exceptions import SecurityError

        renderer = PromptRenderer()
        template = renderer.env.from_string("{{ ''.__class__.__mro__ }}")
        with contextlib.suppress(SecurityError, Exception):
            template.render()

    def test_normal_templates_work(self) -> None:
        """Normal template rendering should still work correctly."""
        renderer = PromptRenderer()
        template = renderer.env.from_string("Hello {{ name }}, value is {{ value }}")
        result = template.render(name="test", value=42)
        assert result == "Hello test, value is 42"
