"""Integration tests for GroupPlanner template framework."""

from __future__ import annotations

from twinklr.core.sequencer.templates.group_templates.bootstrap_traditional import (  # noqa: F401
    gtpl_scene_cozy_village_bg,
)
from twinklr.core.sequencer.templates.group_templates.library import (
    get_template,
    list_templates,
)
from twinklr.core.sequencer.templates.models import (
    TemplateRef,
    template_ref_from_info,
)


def test_template_registration_on_import():
    """Test that templates are auto-registered on import."""
    # Import should trigger @register_template decorators
    templates = list_templates()

    # Should have all bootstrap templates
    assert len(templates) >= 12

    # Should include expected template IDs
    template_ids = {t.template_id for t in templates}
    assert "gtpl_scene_cozy_village_bg" in template_ids
    assert "gtpl_feature_santa_center" in template_ids
    assert "gtpl_tree_polar_radial_burst" in template_ids


def test_template_lookup_by_id():
    """Test template lookup by ID returns correct template."""
    template = get_template("gtpl_scene_cozy_village_bg")

    assert template.template_id == "gtpl_scene_cozy_village_bg"
    assert template.name == "Scene Background — Cozy Village Night"
    assert "holiday_christmas_traditional" in template.tags


def test_template_lookup_by_alias():
    """Test template lookup by alias (case-insensitive)."""
    template = get_template("Cozy Village")

    assert template.template_id == "gtpl_scene_cozy_village_bg"


def test_template_ref_conversion():
    """Test converting TemplateInfo to TemplateRef for agent context."""
    templates = list_templates()
    assert len(templates) > 0

    # Convert first template
    info = templates[0]
    ref = template_ref_from_info(info)

    assert isinstance(ref, TemplateRef)
    assert ref.template_id == info.template_id
    assert ref.name == info.name
    assert ref.template_type == info.template_type.value
    assert list(ref.tags) == list(info.tags)


def test_template_refs_in_context():
    """Test that TemplateRef works in GroupPlanningContext (minimal test)."""
    # Build template refs from registry
    template_infos = list_templates()[:3]  # Use first 3
    template_refs = [template_ref_from_info(info) for info in template_infos]

    # Verify TemplateRef structure
    assert len(template_refs) == 3
    for ref in template_refs:
        assert isinstance(ref, TemplateRef)
        assert ref.template_id
        assert ref.name
        assert ref.template_type
        assert isinstance(ref.tags, list)

    # Verify TemplateRef can be serialized (important for Pydantic)
    ref_dict = template_refs[0].model_dump()
    assert "template_id" in ref_dict
    assert "name" in ref_dict
    assert "template_type" in ref_dict
    assert "tags" in ref_dict


def test_template_search_by_tags():
    """Test searching templates by tags for agent selection."""
    from twinklr.core.sequencer.templates.group_templates.library import (
        find_templates,
    )

    # Find tree polar templates
    results = find_templates(has_tag="tree_polar")
    assert len(results) >= 1

    # All results should have the tag
    for info in results:
        assert any("tree_polar" in tag.lower() for tag in info.tags)


def test_template_instance_independence():
    """Test that multiple calls to get_template return independent instances."""
    template1 = get_template("gtpl_scene_cozy_village_bg")
    template2 = get_template("gtpl_scene_cozy_village_bg")

    # Should be different instances
    assert template1 is not template2

    # Modifying one shouldn't affect the other
    template1.tags.append("modified")
    assert "modified" not in template2.tags
