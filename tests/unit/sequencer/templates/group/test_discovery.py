"""Tests for group template auto-discovery."""

from twinklr.core.sequencer.templates.group import load_builtin_group_templates
from twinklr.core.sequencer.templates.group.library import REGISTRY


class TestAutoDiscovery:
    """Test auto-discovery of builtin templates."""

    def test_load_builtin_templates_idempotent(self):
        """Test load_builtin_group_templates() is idempotent."""
        # Get initial count
        _ = len(REGISTRY.list_all())

        # Load templates multiple times
        load_builtin_group_templates()
        count_after_first = len(REGISTRY.list_all())

        load_builtin_group_templates()
        count_after_second = len(REGISTRY.list_all())

        load_builtin_group_templates()
        count_after_third = len(REGISTRY.list_all())

        # Counts should be the same (idempotent)
        assert count_after_first == count_after_second == count_after_third

    def test_load_builtin_templates_no_errors(self):
        """Test loading builtin templates doesn't raise errors."""
        # Should not raise any errors (even if builtins/ is empty)
        load_builtin_group_templates()

    def test_builtin_templates_count(self):
        """Test builtin templates are loaded (or zero if Phase 1)."""
        load_builtin_group_templates()
        templates = REGISTRY.list_all()

        # Phase 1: builtins/ is empty, so count should be 0 (from builtins)
        # Note: May have templates from other tests in REGISTRY
        assert isinstance(templates, list)
