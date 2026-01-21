"""Unit tests for per-fixture timing offset explosion."""

from __future__ import annotations

import pytest

from blinkb0t.core.domains.sequencing.moving_heads.resolvers.template_resolver import (
    scale_offsets_to_fixture_count,
)


class TestScaleOffsetsToFixtureCount:
    """Test offset scaling for different fixture counts."""

    def test_8_fixtures_identity(self):
        """8 fixtures should return array as-is."""
        offsets = [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0]
        result = scale_offsets_to_fixture_count(offsets, 8)
        assert result == offsets

    def test_4_fixtures_subsample(self):
        """4 fixtures should use indices [1, 3, 5, 7]."""
        offsets = [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0]
        result = scale_offsets_to_fixture_count(offsets, 4)
        # indices [1, 3, 5, 7] → [0.0, 1.0, 0.0, 1.0]
        assert result == [0.0, 1.0, 0.0, 1.0]

    def test_6_fixtures_subsample(self):
        """6 fixtures should use indices [1, 2, 3, 4, 5, 6]."""
        offsets = [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0]
        result = scale_offsets_to_fixture_count(offsets, 6)
        # indices [1, 2, 3, 4, 5, 6] → [0.0, 1.0, 1.0, 0.0, 0.0, 1.0]
        assert result == [0.0, 1.0, 1.0, 0.0, 0.0, 1.0]

    def test_12_fixtures_tile_and_trim(self):
        """12 fixtures should tile pattern and trim to length."""
        offsets = [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0]
        result = scale_offsets_to_fixture_count(offsets, 12)

        expected = [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0]
        assert result == expected

    def test_16_fixtures_tile_twice(self):
        """16 fixtures should tile pattern exactly twice."""
        offsets = [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0]
        result = scale_offsets_to_fixture_count(offsets, 16)
        expected = offsets * 2
        assert result == expected

    def test_progressive_chase_pattern(self):
        """Test with progressive chase offsets (ping_pong_chase)."""
        offsets = [0.0, 0.0625, 0.125, 0.1875, 0.25, 0.3125, 0.375, 0.4375]

        # 4 fixtures
        result_4 = scale_offsets_to_fixture_count(offsets, 4)
        assert result_4 == [0.0625, 0.1875, 0.3125, 0.4375]

        # 6 fixtures
        result_6 = scale_offsets_to_fixture_count(offsets, 6)
        assert result_6 == [0.0625, 0.125, 0.1875, 0.25, 0.3125, 0.375]

    def test_invalid_length_raises_error(self):
        """Non-8-element array should raise ValueError."""
        offsets = [0.0, 0.5, 1.0]  # Only 3 elements
        with pytest.raises(ValueError, match="exactly 8 elements"):
            scale_offsets_to_fixture_count(offsets, 4)

    def test_empty_array_raises_error(self):
        """Empty array should raise ValueError."""
        with pytest.raises(ValueError, match="exactly 8 elements"):
            scale_offsets_to_fixture_count([], 4)

    def test_2_fixtures_general_case(self):
        """2 fixtures should use general interpolation."""
        offsets = [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0]
        result = scale_offsets_to_fixture_count(offsets, 2)
        # step = 8/2 = 4, indices [0, 4] → [0.0, 0.0]
        assert len(result) == 2
        assert result == [0.0, 0.0]

    def test_single_fixture(self):
        """Single fixture should return first element."""
        offsets = [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0]
        result = scale_offsets_to_fixture_count(offsets, 1)
        assert result == [0.0]


class TestTemplateResolverIntegration:
    """Integration tests for template resolver with per-fixture offsets."""

    @pytest.fixture
    def mock_fixtures_4(self):
        """Create mock 4-fixture group."""
        from unittest.mock import Mock

        fixtures = Mock()
        fixtures.__iter__ = Mock(
            return_value=iter(
                [
                    Mock(fixture_id="MH1"),
                    Mock(fixture_id="MH2"),
                    Mock(fixture_id="MH3"),
                    Mock(fixture_id="MH4"),
                ]
            )
        )
        return fixtures

    def test_accordion_explosion_4_fixtures(self, mock_fixtures_4, tmp_path):
        """Test accordion template explodes correctly for 4 fixtures."""
        from blinkb0t.core.domains.sequencing.moving_heads.resolvers.template_resolver import (
            TemplateResolver,
        )

        # Create template file
        template_content = """{
          "template_id": "test_accordion",
          "name": "Test Accordion",
          "category": "low_energy",
          "steps": [{
            "step_id": "main",
            "target": "ALL",
            "timing": {
              "base_timing": {"duration_bars": 4.0},
              "per_fixture_offsets": [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0]
            },
            "movement_id": "sweep_lr",
            "geometry_id": "mirror_lr",
            "dimmer_id": "breathe"
          }]
        }"""

        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "test_accordion.json").write_text(template_content)

        # Create resolver with fixtures
        resolver = TemplateResolver(template_dir=template_dir, fixtures=mock_fixtures_4)

        # Mock semantic groups
        resolver.semantic_groups = {"ALL": ["MH1", "MH2", "MH3", "MH4"]}

        # Resolve template
        section = {
            "template_id": "test_accordion",
            "targets": ["ALL"],
        }

        instructions = resolver.resolve(section, {})

        # Should explode to 4 instructions
        assert len(instructions) == 4

        # Check targets
        assert instructions[0]["target"] == "MH1"
        assert instructions[1]["target"] == "MH2"
        assert instructions[2]["target"] == "MH3"
        assert instructions[3]["target"] == "MH4"

        # Check timing offsets (scaled from 8 to 4: [0, 1, 0, 1])
        assert instructions[0]["timing"]["start_offset_bars"] == 0.0
        assert instructions[1]["timing"]["start_offset_bars"] == 1.0
        assert instructions[2]["timing"]["start_offset_bars"] == 0.0
        assert instructions[3]["timing"]["start_offset_bars"] == 1.0

    def test_normal_template_no_explosion(self, mock_fixtures_4, tmp_path):
        """Test template without per_fixture_offsets doesn't explode."""
        from blinkb0t.core.domains.sequencing.moving_heads.resolvers.template_resolver import (
            TemplateResolver,
        )

        # Create template file
        template_content = """{
          "template_id": "test_normal",
          "name": "Test Normal",
          "category": "medium_energy",
          "steps": [{
            "step_id": "main",
            "target": "ALL",
            "timing": {
              "base_timing": {"duration_bars": 4.0}
            },
            "movement_id": "sweep_lr",
            "geometry_id": "mirror_lr",
            "dimmer_id": "breathe"
          }]
        }"""

        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "test_normal.json").write_text(template_content)

        # Create resolver with fixtures
        resolver = TemplateResolver(template_dir=template_dir, fixtures=mock_fixtures_4)

        # Resolve template
        section = {
            "template_id": "test_normal",
            "targets": ["ALL"],
        }

        instructions = resolver.resolve(section, {})

        # Should return single instruction (no explosion)
        assert len(instructions) == 1
        assert instructions[0]["target"] == "ALL"
        assert instructions[0]["timing"]["start_offset_bars"] == 0.0
