"""Tests for SequencedEffect and DmxEffect data models."""

from __future__ import annotations

import pytest

from blinkb0t.core.domains.sequencing.models.channels import DmxEffect, SequencedEffect


class TestSequencedEffect:
    """Test SequencedEffect model."""

    def test_valid_creation(self, mock_channel_state):
        """Test valid SequencedEffect creation."""
        effect = SequencedEffect(
            targets=["stage_left"],
            channels={"pan": mock_channel_state, "tilt": mock_channel_state},
            start_ms=100,
            end_ms=500,
            metadata={"pattern": "circle"},
        )
        assert effect.targets == ["stage_left"]
        assert len(effect.channels) == 2
        assert effect.start_ms == 100
        assert effect.end_ms == 500
        assert effect.metadata == {"pattern": "circle"}

    def test_valid_creation_multiple_targets(self, mock_channel_state):
        """Test valid SequencedEffect with multiple targets."""
        effect = SequencedEffect(
            targets=["LEFT", "RIGHT"],
            channels={"pan": mock_channel_state},
            start_ms=0,
            end_ms=1000,
        )
        assert len(effect.targets) == 2
        assert "LEFT" in effect.targets
        assert "RIGHT" in effect.targets

    def test_valid_creation_without_metadata(self, mock_channel_state):
        """Test valid SequencedEffect without metadata."""
        effect = SequencedEffect(
            targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=0, end_ms=1000
        )
        assert effect.metadata == {}

    def test_end_time_must_be_greater_than_start(self, mock_channel_state):
        """Test end_ms must be > start_ms."""
        with pytest.raises(ValueError, match=r"end_ms .* must be > start_ms"):
            SequencedEffect(
                targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=500, end_ms=100
            )

    def test_end_time_equal_to_start_raises(self, mock_channel_state):
        """Test end_ms equal to start_ms raises error."""
        with pytest.raises(ValueError, match=r"end_ms .* must be > start_ms"):
            SequencedEffect(
                targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=100, end_ms=100
            )

    def test_empty_targets_raises(self, mock_channel_state):
        """Test empty targets raises error."""
        with pytest.raises(ValueError, match="targets cannot be empty"):
            SequencedEffect(
                targets=[], channels={"pan": mock_channel_state}, start_ms=100, end_ms=500
            )

    def test_empty_channels_raises(self):
        """Test empty channels raises error."""
        with pytest.raises(ValueError, match="channels cannot be empty"):
            SequencedEffect(targets=["ALL"], channels={}, start_ms=100, end_ms=500)

    def test_non_string_target_raises(self, mock_channel_state):
        """Test non-string target raises error."""
        with pytest.raises(ValueError, match="All targets must be strings"):
            SequencedEffect(
                targets=["ALL", 123],  # type: ignore
                channels={"pan": mock_channel_state},
                start_ms=100,
                end_ms=500,
            )

    def test_immutability(self, mock_channel_state):
        """Test that SequencedEffect is immutable."""
        effect = SequencedEffect(
            targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=0, end_ms=1000
        )
        with pytest.raises((AttributeError, TypeError)):  # dataclass frozen=True raises error
            effect.start_ms = 500  # type: ignore

    def test_multiple_channels(self, mock_channel_state):
        """Test SequencedEffect with multiple channels."""
        channels = {
            "pan": mock_channel_state,
            "tilt": mock_channel_state,
            "shutter": mock_channel_state,
            "color": mock_channel_state,
        }
        effect = SequencedEffect(targets=["ALL"], channels=channels, start_ms=0, end_ms=1000)
        assert len(effect.channels) == 4
        assert all(ch in effect.channels for ch in ["pan", "tilt", "shutter", "color"])


class TestDmxEffect:
    """Test DmxEffect model."""

    def test_valid_creation(self, mock_channel_state):
        """Test valid DmxEffect creation."""
        effect = DmxEffect(
            fixture_id="MH1",
            start_ms=100,
            end_ms=500,
            channels={
                "pan": mock_channel_state,
                "tilt": mock_channel_state,
                "shutter": mock_channel_state,
            },
            metadata={"type": "movement"},
        )
        assert effect.fixture_id == "MH1"
        assert len(effect.channels) == 3
        assert effect.start_ms == 100
        assert effect.end_ms == 500
        assert effect.metadata == {"type": "movement"}

    def test_valid_creation_without_metadata(self, mock_channel_state):
        """Test valid DmxEffect without metadata."""
        effect = DmxEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            channels={"pan": mock_channel_state},
        )
        assert effect.metadata == {}

    def test_end_time_must_be_greater_than_start(self, mock_channel_state):
        """Test end_ms must be > start_ms."""
        with pytest.raises(ValueError, match=r"end_ms .* must be > start_ms"):
            DmxEffect(
                fixture_id="MH1", start_ms=500, end_ms=100, channels={"pan": mock_channel_state}
            )

    def test_end_time_equal_to_start_raises(self, mock_channel_state):
        """Test end_ms equal to start_ms raises error."""
        with pytest.raises(ValueError, match=r"end_ms .* must be > start_ms"):
            DmxEffect(
                fixture_id="MH1", start_ms=100, end_ms=100, channels={"pan": mock_channel_state}
            )

    def test_empty_fixture_id_raises(self, mock_channel_state):
        """Test empty fixture_id raises error."""
        with pytest.raises(ValueError, match="fixture_id cannot be empty"):
            DmxEffect(fixture_id="", start_ms=100, end_ms=500, channels={"pan": mock_channel_state})

    def test_empty_channels_raises(self):
        """Test empty channels raises error."""
        with pytest.raises(ValueError, match="channels cannot be empty"):
            DmxEffect(fixture_id="MH1", start_ms=100, end_ms=500, channels={})

    def test_immutability(self, mock_channel_state):
        """Test that DmxEffect is immutable."""
        effect = DmxEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            channels={"pan": mock_channel_state},
        )
        with pytest.raises((AttributeError, TypeError)):  # dataclass frozen=True raises error
            effect.start_ms = 500  # type: ignore

    def test_complete_channel_set(self, mock_channel_state):
        """Test DmxEffect with complete channel set."""
        channels = {
            "pan": mock_channel_state,
            "tilt": mock_channel_state,
            "dimmer": mock_channel_state,
            "shutter": mock_channel_state,
            "color": mock_channel_state,
            "gobo": mock_channel_state,
        }
        effect = DmxEffect(fixture_id="MH1", start_ms=0, end_ms=1000, channels=channels)
        assert len(effect.channels) == 6
        assert all(
            ch in effect.channels for ch in ["pan", "tilt", "dimmer", "shutter", "color", "gobo"]
        )

    def test_metadata_types(self, mock_channel_state):
        """Test various metadata types."""
        metadata = {
            "type": "gap_fill",
            "source": "gap_filler",
            "count": 42,
            "enabled": True,
            "nested": {"key": "value"},
        }
        effect = DmxEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            channels={"pan": mock_channel_state},
            metadata=metadata,
        )
        assert effect.metadata["type"] == "gap_fill"
        assert effect.metadata["count"] == 42
        assert effect.metadata["enabled"] is True
        assert effect.metadata["nested"]["key"] == "value"


class TestDataModelEdgeCases:
    """Test edge cases for data models."""

    def test_sequenced_effect_zero_start_time(self, mock_channel_state):
        """Test SequencedEffect with start_ms=0."""
        effect = SequencedEffect(
            targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=0, end_ms=1
        )
        assert effect.start_ms == 0
        assert effect.end_ms == 1

    def test_dmx_effect_zero_start_time(self, mock_channel_state):
        """Test DmxEffect with start_ms=0."""
        effect = DmxEffect(
            fixture_id="MH1", start_ms=0, end_ms=1, channels={"pan": mock_channel_state}
        )
        assert effect.start_ms == 0
        assert effect.end_ms == 1

    def test_sequenced_effect_large_time_values(self, mock_channel_state):
        """Test SequencedEffect with large time values."""
        effect = SequencedEffect(
            targets=["ALL"],
            channels={"pan": mock_channel_state},
            start_ms=1000000,
            end_ms=2000000,
        )
        assert effect.start_ms == 1000000
        assert effect.end_ms == 2000000

    def test_dmx_effect_large_time_values(self, mock_channel_state):
        """Test DmxEffect with large time values."""
        effect = DmxEffect(
            fixture_id="MH1",
            start_ms=1000000,
            end_ms=2000000,
            channels={"pan": mock_channel_state},
        )
        assert effect.start_ms == 1000000
        assert effect.end_ms == 2000000

    def test_sequenced_effect_single_channel(self, mock_channel_state):
        """Test SequencedEffect with single channel."""
        effect = SequencedEffect(
            targets=["ALL"], channels={"pan": mock_channel_state}, start_ms=0, end_ms=1000
        )
        assert len(effect.channels) == 1
        assert "pan" in effect.channels

    def test_dmx_effect_single_channel(self, mock_channel_state):
        """Test DmxEffect with single channel."""
        effect = DmxEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            channels={"pan": mock_channel_state},
        )
        assert len(effect.channels) == 1
        assert "pan" in effect.channels

    def test_sequenced_effect_single_target(self, mock_channel_state):
        """Test SequencedEffect with single target."""
        effect = SequencedEffect(
            targets=["MH1"], channels={"pan": mock_channel_state}, start_ms=0, end_ms=1000
        )
        assert len(effect.targets) == 1
        assert effect.targets[0] == "MH1"
