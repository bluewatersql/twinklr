"""Tests for the rig helper that infers fixture roles."""

from __future__ import annotations


class TestInferFixtureRole:
    """Tests for _infer_fixture_role helper."""

    def test_single_fixture_group(self) -> None:
        """A group with 1 fixture assigns CENTER."""
        from twinklr.core.sequencer.moving_heads.fixture_builder import _infer_fixture_role

        assert _infer_fixture_role(group_id="g1", fixture_index=0, group_size=1) == "CENTER"

    def test_two_fixture_group(self) -> None:
        """A group with 2 fixtures assigns LEFT/RIGHT."""
        from twinklr.core.sequencer.moving_heads.fixture_builder import _infer_fixture_role

        assert _infer_fixture_role(group_id="g1", fixture_index=0, group_size=2) == "LEFT"
        assert _infer_fixture_role(group_id="g1", fixture_index=1, group_size=2) == "RIGHT"

    def test_three_fixture_group(self) -> None:
        """A group with 3 fixtures assigns LEFT/CENTER/RIGHT."""
        from twinklr.core.sequencer.moving_heads.fixture_builder import _infer_fixture_role

        assert _infer_fixture_role(group_id="g1", fixture_index=0, group_size=3) == "LEFT"
        assert _infer_fixture_role(group_id="g1", fixture_index=1, group_size=3) == "CENTER"
        assert _infer_fixture_role(group_id="g1", fixture_index=2, group_size=3) == "RIGHT"

    def test_four_fixture_group(self) -> None:
        """A group with 4 fixtures assigns OUTER_LEFT/.../OUTER_RIGHT."""
        from twinklr.core.sequencer.moving_heads.fixture_builder import _infer_fixture_role

        assert _infer_fixture_role(group_id="g1", fixture_index=0, group_size=4) == "OUTER_LEFT"
        assert _infer_fixture_role(group_id="g1", fixture_index=1, group_size=4) == "INNER_LEFT"
        assert _infer_fixture_role(group_id="g1", fixture_index=2, group_size=4) == "INNER_RIGHT"
        assert _infer_fixture_role(group_id="g1", fixture_index=3, group_size=4) == "OUTER_RIGHT"

    def test_five_fixture_group_spreads_across_the_spatial_vocabulary(self) -> None:
        """Groups of 5+ used to get positional names (`front_2`) that match no role
        any template declares, so every step was silently skipped and the rig
        rendered nothing at all."""
        from twinklr.core.sequencer.moving_heads.fixture_builder import _infer_fixture_role

        roles = [
            _infer_fixture_role(group_id="front", fixture_index=index, group_size=5)
            for index in range(5)
        ]
        assert roles == ["FAR_LEFT", "MID_LEFT", "CENTER", "CENTER_RIGHT", "FAR_RIGHT"]

    def test_large_group_spreads_across_the_spatial_vocabulary(self) -> None:
        """An 8-head rig gets a symmetric left-to-right fan of real roles."""
        from twinklr.core.sequencer.moving_heads.fixture_builder import _infer_fixture_role

        roles = [
            _infer_fixture_role(group_id="array", fixture_index=index, group_size=8)
            for index in range(8)
        ]
        assert roles == [
            "FAR_LEFT",
            "OUTER_LEFT",
            "MID_LEFT",
            "INNER_LEFT",
            "INNER_RIGHT",
            "MID_RIGHT",
            "OUTER_RIGHT",
            "FAR_RIGHT",
        ]
