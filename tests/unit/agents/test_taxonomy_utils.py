"""Tests for taxonomy utilities."""


from twinklr.core.agents.taxonomy import (
    BlendMode,
    ChoreographyStyle,
    EnergyTarget,
    LayerRole,
    MotionDensity,
    TargetRole,
    TimingDriver,
)
from twinklr.core.agents.taxonomy_utils import get_taxonomy_dict, inject_taxonomy


def test_get_taxonomy_dict_includes_all_enums():
    """Test that get_taxonomy_dict includes all taxonomy enums."""
    taxonomy = get_taxonomy_dict()

    # Check all expected enum classes are present
    expected_classes = [
        "LayerRole",
        "BlendMode",
        "TimingDriver",
        "TargetRole",
        "EnergyTarget",
        "ChoreographyStyle",
        "MotionDensity",
    ]

    for class_name in expected_classes:
        assert class_name in taxonomy, f"Missing {class_name} in taxonomy dict"


def test_get_taxonomy_dict_values_match_enums():
    """Test that taxonomy dict values match actual enum values."""
    taxonomy = get_taxonomy_dict()

    # Verify LayerRole
    assert set(taxonomy["LayerRole"]) == {e.value for e in LayerRole}

    # Verify BlendMode
    assert set(taxonomy["BlendMode"]) == {e.value for e in BlendMode}

    # Verify TimingDriver
    assert set(taxonomy["TimingDriver"]) == {e.value for e in TimingDriver}

    # Verify TargetRole
    assert set(taxonomy["TargetRole"]) == {e.value for e in TargetRole}

    # Verify EnergyTarget
    assert set(taxonomy["EnergyTarget"]) == {e.value for e in EnergyTarget}

    # Verify ChoreographyStyle
    assert set(taxonomy["ChoreographyStyle"]) == {e.value for e in ChoreographyStyle}

    # Verify MotionDensity
    assert set(taxonomy["MotionDensity"]) == {e.value for e in MotionDensity}


def test_get_taxonomy_dict_returns_strings():
    """Test that taxonomy dict values are string lists."""
    taxonomy = get_taxonomy_dict()

    for class_name, values in taxonomy.items():
        assert isinstance(values, list), f"{class_name} values should be a list"
        for value in values:
            assert isinstance(value, str), f"{class_name} value {value} should be string"


def test_inject_taxonomy_adds_taxonomy_key():
    """Test that inject_taxonomy adds taxonomy to variables."""
    variables = {"foo": "bar"}
    result = inject_taxonomy(variables)

    assert "taxonomy" in result
    assert "foo" in result
    assert result["foo"] == "bar"


def test_inject_taxonomy_preserves_existing_taxonomy():
    """Test that inject_taxonomy doesn't overwrite existing taxonomy."""
    custom_taxonomy = {"LayerRole": ["CUSTOM_ROLE"]}
    variables = {"taxonomy": custom_taxonomy}

    result = inject_taxonomy(variables)

    assert result["taxonomy"] == custom_taxonomy


def test_inject_taxonomy_returns_new_dict():
    """Test that inject_taxonomy returns a new dict (doesn't mutate input)."""
    variables = {"foo": "bar"}
    result = inject_taxonomy(variables)

    assert "taxonomy" not in variables
    assert "taxonomy" in result
    assert variables is not result


def test_taxonomy_includes_all_layer_roles():
    """Test that taxonomy includes all LayerRole values."""
    taxonomy = get_taxonomy_dict()

    expected_roles = {"BASE", "RHYTHM", "ACCENT", "HIGHLIGHT", "FILL", "TEXTURE", "CUSTOM"}
    assert set(taxonomy["LayerRole"]) == expected_roles


def test_taxonomy_includes_all_target_roles():
    """Test that taxonomy includes all TargetRole values."""
    taxonomy = get_taxonomy_dict()

    expected_roles = {
        "OUTLINE",
        "MEGA_TREE",
        "HERO",
        "ARCHES",
        "TREES",
        "PROPS",
        "FLOODS",
        "ACCENTS",
        "WINDOWS",
        "MATRIX",
        "MOVING_HEADS",
    }
    assert set(taxonomy["TargetRole"]) == expected_roles


def test_taxonomy_includes_issue_enums():
    """Test that taxonomy includes issue-related enums for judge agents."""
    taxonomy = get_taxonomy_dict()

    # Check issue-related enum classes are present
    expected_issue_enums = ["IssueCategory", "IssueSeverity", "IssueEffort", "IssueScope", "SuggestedAction"]

    for enum_name in expected_issue_enums:
        assert enum_name in taxonomy, f"Missing {enum_name} in taxonomy dict"
        assert isinstance(taxonomy[enum_name], list), f"{enum_name} should be a list"
        assert len(taxonomy[enum_name]) > 0, f"{enum_name} should not be empty"


def test_taxonomy_issue_category_values():
    """Test that IssueCategory values match the actual enum."""
    from twinklr.core.agents.issues import IssueCategory

    taxonomy = get_taxonomy_dict()

    expected_categories = {e.value for e in IssueCategory}
    assert set(taxonomy["IssueCategory"]) == expected_categories


def test_taxonomy_issue_severity_values():
    """Test that IssueSeverity values match the actual enum."""
    from twinklr.core.agents.issues import IssueSeverity

    taxonomy = get_taxonomy_dict()

    expected_severities = {e.value for e in IssueSeverity}
    assert set(taxonomy["IssueSeverity"]) == expected_severities
