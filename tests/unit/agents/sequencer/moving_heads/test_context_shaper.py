"""Tests for moving head context shaper."""

from blinkb0t.core.agents.sequencer.moving_heads.context_shaper import (
    MovingHeadContextShaper,
)


def test_shaper_init():
    """Test context shaper initialization."""
    shaper = MovingHeadContextShaper(
        max_tokens=1000,
        preserve_keys=["custom_key"],
    )

    assert shaper.max_tokens == 1000
    # Should merge custom key with defaults
    assert "custom_key" in shaper.preserve_keys
    assert "song_structure" in shaper.preserve_keys  # Default
    assert "fixtures" in shaper.preserve_keys  # Default


def test_shaper_init_defaults():
    """Test context shaper with default settings."""
    shaper = MovingHeadContextShaper()

    assert shaper.max_tokens == 4000  # Default
    assert "song_structure" in shaper.preserve_keys
    assert "fixtures" in shaper.preserve_keys
    assert "beat_grid" in shaper.preserve_keys


def test_shape_under_budget():
    """Test shaping when context is under token budget."""
    shaper = MovingHeadContextShaper(max_tokens=10000)

    context = {
        "song_structure": {"intro": [0, 8], "verse": [8, 24]},
        "fixtures": {"count": 4},
        "templates": ["template1", "template2"],
        "extra": "data",
    }

    shaped = shaper.shape(context=context)

    # Should preserve everything when under budget
    assert shaped.data == context
    assert shaped.stats["original_estimate"] > 0
    assert shaped.stats["shaped_estimate"] == shaped.stats["original_estimate"]
    assert shaped.stats["reduction_pct"] == 0.0
    assert shaped.stats["preserved_keys"] == list(context.keys())
    assert shaped.stats["removed_keys"] == []


def test_shape_over_budget_non_preserve():
    """Test shaping removes non-preserved keys when over budget."""
    shaper = MovingHeadContextShaper(
        max_tokens=100,  # Very low budget
        preserve_keys=["song_structure", "fixtures"],
    )

    context = {
        "song_structure": {"intro": [0, 8]},
        "fixtures": {"count": 4},
        "large_data": "x" * 1000,  # Large key to exceed budget
        "extra": "more data",
    }

    shaped = shaper.shape(context=context)

    # Should keep preserved keys
    assert "song_structure" in shaped.data
    assert "fixtures" in shaped.data

    # Should remove non-preserved keys
    assert "large_data" not in shaped.data or len(shaped.data.get("large_data", "")) < len(
        context["large_data"]
    )
    assert shaped.stats["reduction_pct"] > 0


def test_shape_preserves_required_keys():
    """Test that preserve_keys are always kept."""
    shaper = MovingHeadContextShaper(
        max_tokens=50,  # Very low
        preserve_keys=["song_structure"],
    )

    context = {
        "song_structure": {"critical": "data"},
        "removable": "x" * 1000,
    }

    shaped = shaper.shape(context=context)

    # song_structure must be preserved
    assert "song_structure" in shaped.data
    assert shaped.data["song_structure"] == context["song_structure"]


def test_shape_summarizes_audio_features():
    """Test that detailed audio features are summarized."""
    shaper = MovingHeadContextShaper(max_tokens=200)

    context = {
        "song_structure": {"intro": [0, 8]},
        "audio_features": {
            "beats": [0.0, 0.5, 1.0, 1.5, 2.0] * 100,  # Large array
            "energy": [0.8, 0.9, 0.7, 0.6, 0.5] * 100,
            "spectral": {"bands": list(range(1000))},
        },
    }

    shaped = shaper.shape(context=context)

    # Audio features should be summarized or removed
    if "audio_features" in shaped.data:
        # If kept, should be summarized
        features = shaped.data["audio_features"]
        if "beats" in features:
            # Should be dict with truncated data
            assert isinstance(features["beats"], dict)
            assert "first" in features["beats"]


def test_shape_truncates_template_list():
    """Test that available_templates is preserved (not truncated) since it's a critical key."""
    shaper = MovingHeadContextShaper(max_tokens=300)

    context = {
        "song_structure": {"intro": [0, 8]},
        "available_templates": [f"template_{i}" for i in range(200)],
    }

    shaped = shaper.shape(context=context)

    # available_templates should be preserved in full (it's a critical key for judge validation)
    assert "available_templates" in shaped.data
    assert len(shaped.data["available_templates"]) == len(context["available_templates"])


def test_shape_with_iteration_feedback():
    """Test that feedback from previous iterations is handled."""
    shaper = MovingHeadContextShaper(max_tokens=500)

    context = {
        "song_structure": {"intro": [0, 8]},
        "feedback": [
            "Previous plan had issues",
            "Judge noted: fix timing",
            "Validator failed on: templates",
        ],
    }

    shaped = shaper.shape(context=context)

    # Feedback should be preserved (it's important)
    assert "feedback" in shaped.data  # Should always be preserved
    assert len(shaped.data["feedback"]) > 0


def test_shape_nested_structures():
    """Test shaping handles nested dictionaries."""
    shaper = MovingHeadContextShaper(max_tokens=300)

    context = {
        "song_structure": {
            "sections": {
                "intro": {"start": 0, "end": 8, "bars": 4},
                "verse1": {"start": 8, "end": 24, "bars": 8},
                "chorus1": {"start": 24, "end": 40, "bars": 8},
            }
        },
        "fixtures": {
            "rig": {
                "groups": [
                    {"name": "front", "count": 4},
                    {"name": "back", "count": 4},
                ]
            }
        },
    }

    shaped = shaper.shape(context=context)

    # Should handle nested structures
    assert isinstance(shaped.data, dict)
    assert shaped.stats["shaped_estimate"] <= shaper.max_tokens


def test_shaper_logging():
    """Test that shaper logs reduction details."""
    shaper = MovingHeadContextShaper(max_tokens=100)

    context = {
        "song_structure": {"intro": [0, 8]},
        "large_field": "x" * 1000,
    }

    shaped = shaper.shape(context=context)

    # Should have removal info
    if shaped.stats["reduction_pct"] > 0:
        assert len(shaped.stats["removed_keys"]) > 0


def test_shaper_deterministic():
    """Test that shaping is deterministic."""
    shaper = MovingHeadContextShaper(max_tokens=200, preserve_keys=["fixtures"])

    context = {
        "fixtures": {"count": 4},
        "data1": "x" * 100,
        "data2": "y" * 100,
    }

    shaped1 = shaper.shape(context=context)
    shaped2 = shaper.shape(context=context)

    # Should produce same result
    assert shaped1.data == shaped2.data
    assert shaped1.stats["shaped_estimate"] == shaped2.stats["shaped_estimate"]
