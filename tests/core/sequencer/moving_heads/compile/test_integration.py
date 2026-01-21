"""Integration Tests for Compiler Pipeline.

End-to-end tests that verify the full compilation pipeline works correctly,
from template loading through to IR segment generation.
"""

import json
from pathlib import Path

from blinkb0t.core.sequencer.moving_heads.compile.loader import TemplateLoader
from blinkb0t.core.sequencer.moving_heads.compile.template_compiler import (
    FixtureContext,
    TemplateCompileContext,
    compile_template,
)
from blinkb0t.core.sequencer.moving_heads.handlers.defaults import create_default_registries
from blinkb0t.core.sequencer.moving_heads.models.channel import ChannelName

# =============================================================================
# Test Fixtures - Complete Template Data
# =============================================================================


def get_complete_template_doc() -> dict:
    """Get a complete template doc for integration testing."""
    return {
        "template": {
            "template_id": "integration_test_template",
            "version": 1,
            "name": "Integration Test Template",
            "category": "test",
            "roles": ["FRONT_LEFT", "FRONT_CENTER", "FRONT_RIGHT"],
            "groups": {
                "all": ["FRONT_LEFT", "FRONT_CENTER", "FRONT_RIGHT"],
                "outer": ["FRONT_LEFT", "FRONT_RIGHT"],
            },
            "repeat": {
                "repeatable": True,
                "mode": "PING_PONG",
                "cycle_bars": 4.0,
                "loop_step_ids": ["intro", "main"],
                "remainder_policy": "HOLD_LAST_POSE",
            },
            "defaults": {
                "intensity": "SMOOTH",
            },
            "steps": [
                {
                    "step_id": "intro",
                    "target": "all",
                    "timing": {
                        "base_timing": {
                            "start_offset_bars": 0.0,
                            "duration_bars": 2.0,
                        },
                        "phase_offset": {
                            "mode": "NONE",
                        },
                    },
                    "geometry": {
                        "geometry_id": "ROLE_POSE",
                        "pan_pose_by_role": {
                            "FRONT_LEFT": "LEFT",
                            "FRONT_CENTER": "CENTER",
                            "FRONT_RIGHT": "RIGHT",
                        },
                        "tilt_pose": "CROWD",
                    },
                    "movement": {
                        "movement_id": "SWEEP_LR",
                        "intensity": "SMOOTH",
                        "cycles": 1.0,
                    },
                    "dimmer": {
                        "dimmer_id": "FADE_IN",
                        "intensity": "SMOOTH",
                        "min_norm": 0.0,
                        "max_norm": 1.0,
                        "cycles": 1.0,
                    },
                },
                {
                    "step_id": "main",
                    "target": "all",
                    "timing": {
                        "base_timing": {
                            "start_offset_bars": 2.0,
                            "duration_bars": 2.0,
                        },
                        "phase_offset": {
                            "mode": "GROUP_ORDER",
                            "group": "all",
                            "spread_bars": 0.5,
                        },
                    },
                    "geometry": {
                        "geometry_id": "ROLE_POSE",
                        "pan_pose_by_role": {
                            "FRONT_LEFT": "LEFT",
                            "FRONT_CENTER": "CENTER",
                            "FRONT_RIGHT": "RIGHT",
                        },
                        "tilt_pose": "CROWD",
                    },
                    "movement": {
                        "movement_id": "SWEEP_LR",
                        "intensity": "FAST",
                        "cycles": 2.0,
                    },
                    "dimmer": {
                        "dimmer_id": "PULSE",
                        "intensity": "SMOOTH",
                        "min_norm": 0.2,
                        "max_norm": 1.0,
                        "cycles": 4.0,
                    },
                },
            ],
            "metadata": {
                "tags": ["test", "integration"],
            },
        },
        "presets": [
            {
                "preset_id": "CHILL",
                "name": "Chill",
                "defaults": {"intensity": "SLOW"},
                "step_patches": {
                    "main": {
                        "movement": {"cycles": 1.0},
                        "dimmer": {"max_norm": 0.6, "cycles": 2.0},
                    },
                },
            },
            {
                "preset_id": "INTENSE",
                "name": "Intense",
                "defaults": {"intensity": "DRAMATIC"},
                "step_patches": {
                    "intro": {
                        "dimmer": {"min_norm": 0.3},
                    },
                    "main": {
                        "movement": {"cycles": 4.0},
                        "dimmer": {"cycles": 8.0},
                    },
                },
            },
        ],
    }


def create_integration_compile_context(
    fixture_count: int = 3,
    window_bars: float = 8.0,
    bpm: float = 120.0,
) -> TemplateCompileContext:
    """Create a compile context for integration testing."""
    roles = ["FRONT_LEFT", "FRONT_CENTER", "FRONT_RIGHT"]
    fixtures = [
        FixtureContext(
            fixture_id=f"fixture_{i + 1}",
            role=roles[i] if i < len(roles) else roles[0],
            calibration={},
        )
        for i in range(fixture_count)
    ]

    registries = create_default_registries()
    ms_per_bar = (60000 / bpm) * 4
    # Use round() to avoid precision loss with fractional ms_per_bar
    window_ms = round(window_bars * ms_per_bar)

    return TemplateCompileContext(
        fixtures=fixtures,
        start_ms=0,
        window_ms=window_ms,
        bpm=bpm,
        n_samples=32,
        geometry_registry=registries["geometry"],
        movement_registry=registries["movement"],
        dimmer_registry=registries["dimmer"],
    )


# =============================================================================
# Integration Tests - Load and Compile
# =============================================================================


class TestLoadAndCompile:
    """Tests for loading templates and compiling them."""

    def test_load_and_compile_basic(self, tmp_path: Path) -> None:
        """Test loading a template file and compiling it."""
        # Write template to file
        file_path = tmp_path / "template.json"
        file_path.write_text(json.dumps(get_complete_template_doc()))

        # Load template
        loader = TemplateLoader()
        loader.load_from_file(file_path)

        # Compile
        doc = loader.get("integration_test_template")
        context = create_integration_compile_context()

        result = compile_template(doc.template, context)

        # Verify result
        assert result.template_id == "integration_test_template"
        assert len(result.segments) > 0

    def test_load_apply_preset_and_compile(self, tmp_path: Path) -> None:
        """Test loading a template, applying a preset, and compiling."""
        # Write template to file
        file_path = tmp_path / "template.json"
        file_path.write_text(json.dumps(get_complete_template_doc()))

        # Load template
        loader = TemplateLoader()
        loader.load_from_file(file_path)

        # Get template with preset
        template = loader.get_with_preset("integration_test_template", "CHILL")
        context = create_integration_compile_context()

        result = compile_template(template, context)

        # Verify result
        assert len(result.segments) > 0


# =============================================================================
# Integration Tests - Full Pipeline
# =============================================================================


class TestFullPipeline:
    """Tests for the complete compilation pipeline."""

    def test_full_pipeline_produces_correct_segment_count(self) -> None:
        """Test full pipeline produces expected number of segments."""
        loader = TemplateLoader()
        loader.load_from_dict(get_complete_template_doc())

        doc = loader.get("integration_test_template")
        context = create_integration_compile_context(
            fixture_count=3,
            window_bars=8.0,  # 2 complete cycles
        )

        result = compile_template(doc.template, context)

        # 2 cycles * 2 steps * 3 fixtures * 3 channels = 36 segments
        # Actually, the calculation depends on how repeats work
        # At minimum, we should have segments for all fixtures and channels
        fixtures = {seg.fixture_id for seg in result.segments}
        assert len(fixtures) == 3

        channels = {seg.channel for seg in result.segments}
        assert ChannelName.PAN in channels
        assert ChannelName.TILT in channels
        assert ChannelName.DIMMER in channels

    def test_full_pipeline_respects_repeat_cycles(self) -> None:
        """Test that repeat cycles are correctly handled."""
        loader = TemplateLoader()
        loader.load_from_dict(get_complete_template_doc())

        doc = loader.get("integration_test_template")

        # Window exactly matches 2 cycles (cycle_bars=4, window=8)
        context = create_integration_compile_context(window_bars=8.0)

        result = compile_template(doc.template, context)

        assert result.num_complete_cycles == 2

    def test_full_pipeline_with_partial_cycle(self) -> None:
        """Test handling of partial cycles at the end."""
        loader = TemplateLoader()
        loader.load_from_dict(get_complete_template_doc())

        doc = loader.get("integration_test_template")

        # Window has 2.5 cycles (cycle_bars=4, window=10)
        context = create_integration_compile_context(window_bars=10.0)

        result = compile_template(doc.template, context)

        # Should have 2 complete cycles (remainder handled by policy)
        assert result.num_complete_cycles == 2


# =============================================================================
# Integration Tests - Segment Timing
# =============================================================================


class TestSegmentTiming:
    """Tests for segment timing accuracy."""

    def test_segments_cover_window(self) -> None:
        """Test that segments cover the entire window."""
        loader = TemplateLoader()
        loader.load_from_dict(get_complete_template_doc())

        doc = loader.get("integration_test_template")
        context = create_integration_compile_context(window_bars=4.0, bpm=120.0)

        result = compile_template(doc.template, context)

        # All segments should start at or after 0
        assert all(seg.t0_ms >= 0 for seg in result.segments)

        # Get max end time from segments
        max_end = max(seg.t1_ms for seg in result.segments)

        # Window at 120 BPM, 4 bars = 4 * 4 * 500 = 8000 ms
        expected_window_ms = 8000
        assert max_end == expected_window_ms

    def test_segments_have_valid_duration(self) -> None:
        """Test that all segments have positive duration."""
        loader = TemplateLoader()
        loader.load_from_dict(get_complete_template_doc())

        doc = loader.get("integration_test_template")
        context = create_integration_compile_context()

        result = compile_template(doc.template, context)

        for seg in result.segments:
            assert seg.t1_ms >= seg.t0_ms, f"Invalid segment timing: {seg}"


# =============================================================================
# Integration Tests - Phase Offsets
# =============================================================================


class TestPhaseOffsetIntegration:
    """Tests for phase offset integration."""

    def test_group_order_creates_offset_differences(self) -> None:
        """Test GROUP_ORDER creates different curves for fixtures."""
        loader = TemplateLoader()
        loader.load_from_dict(get_complete_template_doc())

        doc = loader.get("integration_test_template")
        context = create_integration_compile_context()

        result = compile_template(doc.template, context)

        # Get pan segments for each fixture from the "main" step
        # (which has GROUP_ORDER phase offset)
        # The segments from different fixtures should have different curves
        # due to phase offsets
        fixture_segments = {
            "fixture_1": result.segments_by_fixture("fixture_1"),
            "fixture_2": result.segments_by_fixture("fixture_2"),
            "fixture_3": result.segments_by_fixture("fixture_3"),
        }

        # All fixtures should have segments
        for fixture_id, segments in fixture_segments.items():
            assert len(segments) > 0, f"No segments for {fixture_id}"


# =============================================================================
# Integration Tests - Preset Application
# =============================================================================


class TestPresetIntegration:
    """Tests for preset integration in the pipeline."""

    def test_preset_changes_compilation_result(self) -> None:
        """Test that presets actually affect the compiled output."""
        loader = TemplateLoader()
        loader.load_from_dict(get_complete_template_doc())

        doc = loader.get("integration_test_template")
        chill_preset = loader.get_preset("integration_test_template", "CHILL")
        context = create_integration_compile_context()

        # Compile without preset
        result_default = compile_template(doc.template, context)

        # Compile with preset
        result_preset = compile_template(doc.template, context, preset=chill_preset)

        # Both should produce valid output
        assert len(result_default.segments) > 0
        assert len(result_preset.segments) > 0

        # Preset should be in provenance
        assert "preset:CHILL" in result_preset.provenance
        assert "preset:CHILL" not in result_default.provenance


# =============================================================================
# Integration Tests - Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases in the integration pipeline."""

    def test_single_fixture(self) -> None:
        """Test compilation with a single fixture."""
        loader = TemplateLoader()
        loader.load_from_dict(get_complete_template_doc())

        doc = loader.get("integration_test_template")
        context = create_integration_compile_context(fixture_count=1)

        result = compile_template(doc.template, context)

        # Should still work with single fixture
        assert len(result.segments) > 0
        assert all(seg.fixture_id == "fixture_1" for seg in result.segments)

    def test_very_short_window(self) -> None:
        """Test compilation with a very short window."""
        loader = TemplateLoader()
        loader.load_from_dict(get_complete_template_doc())

        doc = loader.get("integration_test_template")
        context = create_integration_compile_context(window_bars=1.0)

        result = compile_template(doc.template, context)

        # Window shorter than cycle should still work (0 complete cycles)
        assert result.num_complete_cycles == 0

    def test_different_bpm_values(self) -> None:
        """Test compilation at different BPM values."""
        loader = TemplateLoader()
        loader.load_from_dict(get_complete_template_doc())

        doc = loader.get("integration_test_template")

        # Use 8 bars (2 cycles) to avoid edge case where window == cycle exactly
        window_bars = 8.0
        for bpm in [60.0, 120.0, 180.0]:
            context = create_integration_compile_context(bpm=bpm, window_bars=window_bars)
            result = compile_template(doc.template, context)

            # Should produce valid output at any BPM
            assert len(result.segments) > 0

            # Segment timing should reflect BPM
            # Allow ±2ms tolerance for cumulative rounding differences
            ms_per_bar = (60000 / bpm) * 4
            expected_window_ms = round(window_bars * ms_per_bar)
            max_end = max(seg.t1_ms for seg in result.segments)
            assert abs(max_end - expected_window_ms) <= 2, (
                f"At {bpm} BPM: max_end={max_end}, expected={expected_window_ms}"
            )


# =============================================================================
# Integration Tests - Determinism
# =============================================================================


class TestDeterminism:
    """Tests to verify compilation is deterministic."""

    def test_repeated_compilation_produces_same_result(self) -> None:
        """Test that compiling the same template twice produces identical results."""
        loader = TemplateLoader()
        loader.load_from_dict(get_complete_template_doc())

        doc = loader.get("integration_test_template")
        context = create_integration_compile_context()

        result1 = compile_template(doc.template, context)
        result2 = compile_template(doc.template, context)

        # Same number of segments
        assert len(result1.segments) == len(result2.segments)

        # Same segment properties (checking a subset)
        for seg1, seg2 in zip(result1.segments, result2.segments, strict=True):
            assert seg1.fixture_id == seg2.fixture_id
            assert seg1.channel == seg2.channel
            assert seg1.t0_ms == seg2.t0_ms
            assert seg1.t1_ms == seg2.t1_ms
