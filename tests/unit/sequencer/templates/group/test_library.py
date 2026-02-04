"""Tests for group template registry."""

import re

import pytest

from twinklr.core.sequencer.templates.group.library import (
    REGISTRY,
    GroupTemplateRegistry,
    TemplateNotFoundError,
    _norm_key,
    get_group_template,
    list_group_templates,
    register_group_template,
)
from twinklr.core.sequencer.templates.group.models import GroupPlanTemplate, ProjectionSpec
from twinklr.core.sequencer.vocabulary import (
    GroupTemplateType,
    GroupVisualIntent,
    ProjectionIntent,
)


class TestNormKey:
    """Test key normalization function."""

    def test_lowercase(self):
        """Test conversion to lowercase."""
        assert _norm_key("TEST") == "test"
        assert _norm_key("TeSt") == "test"

    def test_spaces_to_underscores(self):
        """Test spaces converted to underscores."""
        assert _norm_key("test template") == "test_template"
        assert _norm_key("my test") == "my_test"

    def test_special_chars_to_underscores(self):
        """Test special characters converted to underscores."""
        assert _norm_key("test-template") == "test_template"
        assert _norm_key("test.template") == "test_template"

    def test_strip_leading_trailing_underscores(self):
        """Test leading/trailing underscores stripped."""
        assert _norm_key("_test_") == "test"
        assert _norm_key("__test__") == "test"

    def test_alphanumeric_preserved(self):
        """Test alphanumeric characters preserved."""
        assert _norm_key("test123") == "test123"
        assert _norm_key("abc_123") == "abc_123"


class TestGroupTemplateRegistry:
    """Test GroupTemplateRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create fresh registry for each test."""
        return GroupTemplateRegistry()

    @pytest.fixture
    def sample_factory(self):
        """Create sample template factory."""

        def factory() -> GroupPlanTemplate:
            return GroupPlanTemplate(
                template_id="test_template",
                name="Test Template",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
                tags=["test", "sample"],
            )

        return factory

    def test_register_template(self, registry, sample_factory):
        """Test registering a template."""
        registry.register(sample_factory)

        # Should be able to retrieve by id
        template = registry.get("test_template")
        assert template.template_id == "test_template"
        assert template.name == "Test Template"

    def test_register_with_aliases(self, registry, sample_factory):
        """Test registering with aliases."""
        registry.register(sample_factory, aliases=["alias1", "Sample Test"])

        # Should retrieve by id
        t1 = registry.get("test_template")
        assert t1.template_id == "test_template"

        # Should retrieve by alias
        t2 = registry.get("alias1")
        assert t2.template_id == "test_template"

        # Should retrieve by name
        t3 = registry.get("Test Template")
        assert t3.template_id == "test_template"

        # Should retrieve by alias (normalized)
        t4 = registry.get("sample test")
        assert t4.template_id == "test_template"

    def test_register_duplicate_fails(self, registry, sample_factory):
        """Test registering duplicate template_id fails."""
        registry.register(sample_factory)

        with pytest.raises(ValueError, match=re.escape("already registered")):
            registry.register(sample_factory)

    def test_get_nonexistent_template(self, registry):
        """Test getting nonexistent template raises error."""
        with pytest.raises(TemplateNotFoundError, match=re.escape("Unknown.*template")):
            registry.get("nonexistent")

    def test_get_deep_copy_default(self, registry, sample_factory):
        """Test get() returns deep copy by default."""
        registry.register(sample_factory)

        t1 = registry.get("test_template")
        t2 = registry.get("test_template")

        # Should be different instances
        assert t1 is not t2

        # But equal values
        assert t1.template_id == t2.template_id
        assert t1.name == t2.name

    def test_get_no_deep_copy(self, registry, sample_factory):
        """Test get() with deep_copy=False."""
        registry.register(sample_factory)

        t1 = registry.get("test_template", deep_copy=False)
        t2 = registry.get("test_template", deep_copy=False)

        # Should still be different instances (factory creates new each time)
        assert t1 is not t2

    def test_list_all_empty(self, registry):
        """Test list_all() with empty registry."""
        assert registry.list_all() == []

    def test_list_all_multiple_templates(self, registry):
        """Test list_all() with multiple templates."""

        def factory1():
            return GroupPlanTemplate(
                template_id="template_a",
                name="A Template",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
            )

        def factory2():
            return GroupPlanTemplate(
                template_id="template_b",
                name="B Template",
                template_type=GroupTemplateType.RHYTHM,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
            )

        registry.register(factory1)
        registry.register(factory2)

        templates = registry.list_all()
        assert len(templates) == 2

        # Should be sorted by template_type, then name
        assert templates[0].template_id == "template_a"
        assert templates[1].template_id == "template_b"

    def test_find_by_template_type(self, registry):
        """Test find() filtering by template_type."""

        def base_factory():
            return GroupPlanTemplate(
                template_id="base_template",
                name="Base",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
            )

        def rhythm_factory():
            return GroupPlanTemplate(
                template_id="rhythm_template",
                name="Rhythm",
                template_type=GroupTemplateType.RHYTHM,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
            )

        registry.register(base_factory)
        registry.register(rhythm_factory)

        # Find BASE templates
        base_templates = registry.find(template_type=GroupTemplateType.BASE)
        assert len(base_templates) == 1
        assert base_templates[0].template_id == "base_template"

        # Find RHYTHM templates
        rhythm_templates = registry.find(template_type=GroupTemplateType.RHYTHM)
        assert len(rhythm_templates) == 1
        assert rhythm_templates[0].template_id == "rhythm_template"

    def test_find_by_tag(self, registry):
        """Test find() filtering by tag."""

        def factory1():
            return GroupPlanTemplate(
                template_id="template1",
                name="Template 1",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
                tags=["starfield", "calm"],
            )

        def factory2():
            return GroupPlanTemplate(
                template_id="template2",
                name="Template 2",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
                tags=["pulse", "energetic"],
            )

        registry.register(factory1)
        registry.register(factory2)

        # Find by tag (case-insensitive)
        starfield = registry.find(has_tag="starfield")
        assert len(starfield) == 1
        assert starfield[0].template_id == "template1"

        # Find by tag (different case)
        calm = registry.find(has_tag="CALM")
        assert len(calm) == 1
        assert calm[0].template_id == "template1"

    def test_find_by_name_contains(self, registry):
        """Test find() filtering by name substring."""

        def factory1():
            return GroupPlanTemplate(
                template_id="template1",
                name="Starfield Slow",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
            )

        def factory2():
            return GroupPlanTemplate(
                template_id="template2",
                name="Starfield Fast",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
            )

        registry.register(factory1)
        registry.register(factory2)

        # Find by substring
        starfield = registry.find(name_contains="starfield")
        assert len(starfield) == 2

        # Find specific variant
        slow = registry.find(name_contains="slow")
        assert len(slow) == 1
        assert slow[0].template_id == "template1"

    def test_find_combined_filters(self, registry):
        """Test find() with multiple filters."""

        def factory1():
            return GroupPlanTemplate(
                template_id="base_starfield",
                name="Starfield Base",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
                tags=["starfield"],
            )

        def factory2():
            return GroupPlanTemplate(
                template_id="rhythm_starfield",
                name="Starfield Rhythm",
                template_type=GroupTemplateType.RHYTHM,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
                tags=["starfield"],
            )

        registry.register(factory1)
        registry.register(factory2)

        # Find BASE templates with starfield tag
        result = registry.find(template_type=GroupTemplateType.BASE, has_tag="starfield")
        assert len(result) == 1
        assert result[0].template_id == "base_starfield"


class TestRegistryDecorator:
    """Test @register_group_template decorator."""

    def test_decorator_registers_template(self):
        """Test decorator registers template in global registry."""
        # Create a new registry for isolation
        _ = GroupTemplateRegistry()

        @register_group_template(aliases=["Test Decorator"])
        def make_test_decorator_template() -> GroupPlanTemplate:
            return GroupPlanTemplate(
                template_id="decorator_test",
                name="Decorator Test",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
            )

        # Should be registered in global REGISTRY
        template = REGISTRY.get("decorator_test")
        assert template.template_id == "decorator_test"

    def test_decorator_preserves_function(self):
        """Test decorator preserves original function."""

        @register_group_template()
        def make_preserved_template() -> GroupPlanTemplate:
            return GroupPlanTemplate(
                template_id="preserved",
                name="Preserved",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
            )

        # Function should still be callable
        template = make_preserved_template()
        assert template.template_id == "preserved"


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_get_group_template(self):
        """Test get_group_template() convenience function."""

        @register_group_template()
        def make_convenience_test() -> GroupPlanTemplate:
            return GroupPlanTemplate(
                template_id="convenience_test",
                name="Convenience Test",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
            )

        template = get_group_template("convenience_test")
        assert template.template_id == "convenience_test"

    def test_list_group_templates(self):
        """Test list_group_templates() convenience function."""
        templates = list_group_templates()
        # Should return list (may have templates from other tests)
        assert isinstance(templates, list)
