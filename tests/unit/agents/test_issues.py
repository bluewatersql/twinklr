"""Tests for TargetedAction model and ActionType enum."""

from pydantic import ValidationError
import pytest

from twinklr.core.agents.issues import (
    ActionType,
    Issue,
    IssueCategory,
    IssueEffort,
    IssueLocation,
    IssueScope,
    IssueSeverity,
    SuggestedAction,
    TargetedAction,
)


class TestTargetedAction:
    """Tests for TargetedAction model."""

    def test_targeted_action_add_target_valid(self) -> None:
        """Create a valid ADD_TARGET action with lane and target."""
        action = TargetedAction(
            action_type=ActionType.ADD_TARGET,
            section_id="verse_1",
            lane="RHYTHM",
            target="group:ARCHES",
            description="Add ARCHES to RHYTHM lane",
        )
        assert action.action_type == ActionType.ADD_TARGET
        assert action.lane == "RHYTHM"
        assert action.target == "group:ARCHES"
        assert action.section_id == "verse_1"

    def test_targeted_action_swap_template_valid(self) -> None:
        """Create SWAP_TEMPLATE with template_id and replacement_template_id."""
        action = TargetedAction(
            action_type=ActionType.SWAP_TEMPLATE,
            section_id="chorus_1",
            template_id="gtpl_rhythm_sparkle",
            replacement_template_id="gtpl_rhythm_pulse",
            description="Swap to pulse template for variety",
        )
        assert action.action_type == ActionType.SWAP_TEMPLATE
        assert action.template_id == "gtpl_rhythm_sparkle"
        assert action.replacement_template_id == "gtpl_rhythm_pulse"

    def test_targeted_action_swap_template_missing_replacement(self) -> None:
        """SWAP_TEMPLATE without replacement_template_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TargetedAction(
                action_type=ActionType.SWAP_TEMPLATE,
                section_id="chorus_1",
                template_id="gtpl_rhythm_sparkle",
                description="Swap template",
            )
        assert "replacement_template_id" in str(exc_info.value).lower() or (
            "SWAP_TEMPLATE" in str(exc_info.value)
        )

    def test_targeted_action_change_palette_valid(self) -> None:
        """Create CHANGE_PALETTE with palette_id."""
        action = TargetedAction(
            action_type=ActionType.CHANGE_PALETTE,
            section_id="verse_1",
            palette_id="core.peppermint",
            description="Use peppermint palette",
        )
        assert action.action_type == ActionType.CHANGE_PALETTE
        assert action.palette_id == "core.peppermint"

    def test_targeted_action_change_palette_without_palette_id(self) -> None:
        """CHANGE_PALETTE without palette_id is valid (removal intent)."""
        action = TargetedAction(
            action_type=ActionType.CHANGE_PALETTE,
            section_id="verse_1",
            description="Remove section palette override",
        )
        assert action.action_type == ActionType.CHANGE_PALETTE
        assert action.palette_id is None

    def test_targeted_action_add_target_missing_lane(self) -> None:
        """ADD_TARGET without lane raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TargetedAction(
                action_type=ActionType.ADD_TARGET,
                section_id="verse_1",
                target="group:ARCHES",
                description="Add target",
            )
        assert "lane" in str(exc_info.value).lower() or "target" in str(exc_info.value).lower()

    def test_targeted_action_other_type_minimal(self) -> None:
        """OTHER type requires only section_id and description."""
        action = TargetedAction(
            action_type=ActionType.OTHER,
            section_id="verse_1",
            description="General refinement needed",
        )
        assert action.action_type == ActionType.OTHER
        assert action.lane is None
        assert action.target is None
        assert action.template_id is None

    def test_targeted_action_serialization_roundtrip(self) -> None:
        """model_dump and reconstruct preserves data."""
        original = TargetedAction(
            action_type=ActionType.ADD_TARGET,
            section_id="chorus_1",
            lane="ACCENT",
            target="group:HERO_1",
            description="Add HERO to ACCENT lane",
        )
        dumped = original.model_dump()
        reconstructed = TargetedAction.model_validate(dumped)
        assert reconstructed == original
        assert reconstructed.model_dump() == dumped

    def test_issue_with_targeted_actions(self) -> None:
        """Issue with non-empty targeted_actions list."""
        action = TargetedAction(
            action_type=ActionType.OTHER,
            section_id="verse_1",
            description="Apply fix",
        )
        issue = Issue(
            issue_id="TEST_001",
            category=IssueCategory.VARIETY,
            severity=IssueSeverity.WARN,
            estimated_effort=IssueEffort.LOW,
            scope=IssueScope.SECTION,
            location=IssueLocation(section_id="verse_1"),
            rule="DON'T lack variety",
            message="Same template repeated",
            fix_hint="Add variety",
            acceptance_test="Variety improved",
            suggested_action=SuggestedAction.PATCH,
            targeted_actions=[action],
        )
        assert len(issue.targeted_actions) == 1
        assert issue.targeted_actions[0].description == "Apply fix"

    def test_issue_with_empty_targeted_actions(self) -> None:
        """Backward compatibility: empty list default for targeted_actions."""
        issue = Issue(
            issue_id="TEST_002",
            category=IssueCategory.TIMING,
            severity=IssueSeverity.ERROR,
            estimated_effort=IssueEffort.MEDIUM,
            scope=IssueScope.SECTION,
            location=IssueLocation(),
            rule="DON'T overlap timing",
            message="Timing overlap",
            fix_hint="Adjust bars",
            acceptance_test="No overlap",
            suggested_action=SuggestedAction.REPLAN_SECTION,
        )
        assert issue.targeted_actions == []
        assert isinstance(issue.targeted_actions, list)


class TestActionType:
    """Tests for ActionType enum."""

    def test_action_type_enum_values(self) -> None:
        """All expected enum values exist."""
        assert ActionType.ADD_TARGET == "ADD_TARGET"
        assert ActionType.REMOVE_TARGET == "REMOVE_TARGET"
        assert ActionType.ADD_PLACEMENT == "ADD_PLACEMENT"
        assert ActionType.REMOVE_PLACEMENT == "REMOVE_PLACEMENT"
        assert ActionType.SWAP_TEMPLATE == "SWAP_TEMPLATE"
        assert ActionType.CHANGE_PALETTE == "CHANGE_PALETTE"
        assert ActionType.CHANGE_THEME == "CHANGE_THEME"
        assert ActionType.ADD_MOTIF == "ADD_MOTIF"
        assert ActionType.REMOVE_MOTIF == "REMOVE_MOTIF"
        assert ActionType.ADJUST_TIMING == "ADJUST_TIMING"
        assert ActionType.REORDER_GROUPS == "REORDER_GROUPS"
        assert ActionType.OTHER == "OTHER"
