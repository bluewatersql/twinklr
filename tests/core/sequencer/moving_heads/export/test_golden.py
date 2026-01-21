"""Golden Tests for End-to-End Export Pipeline.

These tests verify that the complete pipeline (template -> compile -> export)
produces consistent, deterministic output. Golden tests catch unexpected
changes in output format or behavior.
"""

import json
from pathlib import Path

import pytest

from blinkb0t.core.sequencer.moving_heads.compile.loader import TemplateLoader
from blinkb0t.core.sequencer.moving_heads.compile.template_compiler import (
    FixtureContext,
    TemplateCompileContext,
    compile_template,
)
from blinkb0t.core.sequencer.moving_heads.export.xlights_exporter import (
    XLightsExporter,
    compile_result_to_sequence,
)
from blinkb0t.core.sequencer.moving_heads.export.xlights_models import (
    SequenceHead,
)
from blinkb0t.core.sequencer.moving_heads.handlers.defaults import (
    create_default_registries,
)
from blinkb0t.core.sequencer.moving_heads.models.channel import ChannelName

# =============================================================================
# Golden Test Template
# =============================================================================


def get_golden_template_doc() -> dict:
    """Get a complete template doc for golden testing.

    This template exercises key features:
    - Multiple steps
    - Phase offsets
    - Different channel types
    - Repeat cycle
    """
    return {
        "template": {
            "template_id": "golden_test",
            "version": 1,
            "name": "Golden Test Template",
            "category": "test",
            "roles": ["FRONT_LEFT", "FRONT_RIGHT"],
            "groups": {
                "all": ["FRONT_LEFT", "FRONT_RIGHT"],
            },
            "repeat": {
                "repeatable": True,
                "mode": "JOINER",
                "cycle_bars": 4.0,
                "loop_step_ids": ["step1", "step2"],
                "remainder_policy": "HOLD_LAST_POSE",
            },
            "defaults": {},
            "steps": [
                {
                    "step_id": "step1",
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
                    "step_id": "step2",
                    "target": "all",
                    "timing": {
                        "base_timing": {
                            "start_offset_bars": 2.0,
                            "duration_bars": 2.0,
                        },
                        "phase_offset": {
                            "mode": "GROUP_ORDER",
                            "group": "all",
                            "spread_bars": 0.25,
                        },
                    },
                    "geometry": {
                        "geometry_id": "ROLE_POSE",
                        "pan_pose_by_role": {
                            "FRONT_LEFT": "CENTER",
                            "FRONT_RIGHT": "CENTER",
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
        },
        "presets": [],
    }


def create_golden_compile_context(
    bpm: float = 120.0,
    window_bars: float = 8.0,
) -> TemplateCompileContext:
    """Create a compile context for golden testing."""
    fixtures = [
        FixtureContext(fixture_id="MH_1", role="FRONT_LEFT", calibration={}),
        FixtureContext(fixture_id="MH_2", role="FRONT_RIGHT", calibration={}),
    ]

    registries = create_default_registries()
    ms_per_bar = (60000 / bpm) * 4
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


def get_golden_channel_map() -> dict[str, dict[ChannelName, int]]:
    """Get channel map for golden test fixtures."""
    return {
        "MH_1": {
            ChannelName.PAN: 11,
            ChannelName.TILT: 12,
            ChannelName.DIMMER: 13,
        },
        "MH_2": {
            ChannelName.PAN: 21,
            ChannelName.TILT: 22,
            ChannelName.DIMMER: 23,
        },
    }


# =============================================================================
# Golden Tests
# =============================================================================


class TestGoldenPipeline:
    """Golden tests for the complete export pipeline."""

    def test_compile_produces_segments(self) -> None:
        """Test that template compiles to segments."""
        loader = TemplateLoader()
        loader.load_from_dict(get_golden_template_doc())

        doc = loader.get("golden_test")
        context = create_golden_compile_context()

        result = compile_template(doc.template, context)

        # Should have segments for both fixtures, all channels
        assert len(result.segments) > 0

        fixture_ids = {seg.fixture_id for seg in result.segments}
        assert "MH_1" in fixture_ids
        assert "MH_2" in fixture_ids

        channels = {seg.channel for seg in result.segments}
        assert ChannelName.PAN in channels
        assert ChannelName.TILT in channels
        assert ChannelName.DIMMER in channels

    def test_compile_result_converts_to_sequence(self) -> None:
        """Test that compile result converts to XLightsSequence."""
        loader = TemplateLoader()
        loader.load_from_dict(get_golden_template_doc())

        doc = loader.get("golden_test")
        context = create_golden_compile_context()

        result = compile_template(doc.template, context)

        head = SequenceHead(
            version="2024.1",
            media_file="test_song.mp3",
            sequence_duration_ms=context.window_ms,
        )
        channel_map = get_golden_channel_map()

        sequence = compile_result_to_sequence(result, head, channel_map)

        assert len(sequence.elements) == 2
        element_names = {e.element_name for e in sequence.elements}
        assert "MH_1" in element_names
        assert "MH_2" in element_names

    def test_export_produces_valid_xml(self, tmp_path: Path) -> None:
        """Test that export produces valid XML file."""
        # Compile
        loader = TemplateLoader()
        loader.load_from_dict(get_golden_template_doc())

        doc = loader.get("golden_test")
        context = create_golden_compile_context()
        result = compile_template(doc.template, context)

        # Convert
        head = SequenceHead(
            version="2024.1",
            media_file="test_song.mp3",
            sequence_duration_ms=context.window_ms,
        )
        channel_map = get_golden_channel_map()
        sequence = compile_result_to_sequence(result, head, channel_map)

        # Export
        exporter = XLightsExporter()
        output_path = tmp_path / "golden_test.xsq"
        exporter.export(sequence, output_path)

        # Verify
        assert output_path.exists()
        content = output_path.read_text()

        # Check for expected content
        assert "xsequence" in content
        assert "MH_1" in content
        assert "MH_2" in content
        assert "DMX" in content
        assert "Type=Custom" in content

    def test_pipeline_is_deterministic(self, tmp_path: Path) -> None:
        """Test that the complete pipeline is deterministic."""

        def run_pipeline() -> str:
            loader = TemplateLoader()
            loader.load_from_dict(get_golden_template_doc())

            doc = loader.get("golden_test")
            context = create_golden_compile_context()
            result = compile_template(doc.template, context)

            head = SequenceHead(
                version="2024.1",
                media_file="test_song.mp3",
                sequence_duration_ms=context.window_ms,
            )
            channel_map = get_golden_channel_map()
            sequence = compile_result_to_sequence(result, head, channel_map)

            exporter = XLightsExporter()
            output_path = tmp_path / "determinism_test.xsq"
            exporter.export(sequence, output_path)

            return output_path.read_text()

        # Run pipeline twice
        output1 = run_pipeline()
        output2 = run_pipeline()

        # Should produce identical output
        assert output1 == output2


class TestGoldenProperties:
    """Tests for specific properties of golden output."""

    def test_segments_have_correct_timing(self) -> None:
        """Test that segments have correct time ranges."""
        loader = TemplateLoader()
        loader.load_from_dict(get_golden_template_doc())

        doc = loader.get("golden_test")
        context = create_golden_compile_context(bpm=120.0, window_bars=8.0)

        result = compile_template(doc.template, context)

        # At 120 BPM: 1 bar = 2000ms, 8 bars = 16000ms
        expected_window_ms = 16000

        # All segments should start at or after 0
        assert all(seg.t0_ms >= 0 for seg in result.segments)

        # Max end time should match window
        max_end = max(seg.t1_ms for seg in result.segments)
        assert max_end == expected_window_ms

    def test_num_cycles_calculated_correctly(self) -> None:
        """Test that cycle count is calculated correctly."""
        loader = TemplateLoader()
        loader.load_from_dict(get_golden_template_doc())

        doc = loader.get("golden_test")

        # cycle_bars = 4.0, window_bars = 8.0 -> 2 cycles
        context = create_golden_compile_context(window_bars=8.0)
        result = compile_template(doc.template, context)

        assert result.num_complete_cycles == 2

    def test_effects_have_value_curves(self) -> None:
        """Test that effects include value curves."""
        loader = TemplateLoader()
        loader.load_from_dict(get_golden_template_doc())

        doc = loader.get("golden_test")
        context = create_golden_compile_context()
        result = compile_template(doc.template, context)

        head = SequenceHead(
            version="2024.1",
            media_file="test_song.mp3",
            sequence_duration_ms=context.window_ms,
        )
        channel_map = get_golden_channel_map()
        sequence = compile_result_to_sequence(result, head, channel_map)

        # Check that effects have value curves
        for element in sequence.elements:
            for layer in element.layers:
                for effect in layer.effects:
                    assert len(effect.value_curves) > 0


# =============================================================================
# Golden Reference Snapshot Test
# =============================================================================


class TestGoldenSnapshot:
    """Snapshot test against golden reference.

    This test compares output against a stored golden reference.
    If the golden file doesn't exist, it creates it.
    """

    GOLDEN_FILE = Path(__file__).parent / "golden" / "golden_test_output.json"

    def _get_golden_output_data(self) -> dict:
        """Generate the data structure that represents golden output."""
        loader = TemplateLoader()
        loader.load_from_dict(get_golden_template_doc())

        doc = loader.get("golden_test")
        context = create_golden_compile_context()
        result = compile_template(doc.template, context)

        return {
            "template_id": result.template_id,
            "num_complete_cycles": result.num_complete_cycles,
            "num_segments": len(result.segments),
            "fixtures": sorted({seg.fixture_id for seg in result.segments}),
            "channels": sorted([str(ch) for ch in {seg.channel for seg in result.segments}]),
            "provenance": result.provenance,
        }

    def test_golden_snapshot(self) -> None:
        """Test output matches golden snapshot."""
        output_data = self._get_golden_output_data()

        if not self.GOLDEN_FILE.exists():
            # Create golden directory and file
            self.GOLDEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.GOLDEN_FILE.write_text(json.dumps(output_data, indent=2))
            pytest.skip("Created golden file, run test again to verify")

        # Load golden reference
        golden_data = json.loads(self.GOLDEN_FILE.read_text())

        # Compare
        assert output_data == golden_data, (
            f"Output does not match golden reference.\nExpected: {golden_data}\nGot: {output_data}"
        )
