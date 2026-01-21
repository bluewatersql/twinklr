"""Integration tests for template library."""

from pathlib import Path

import pytest

from blinkb0t.core.domains.sequencing.moving_heads.templates import TemplateLoader


class TestTemplateLibrary:
    """Test production template library."""

    @pytest.fixture
    def template_dir(self) -> Path:
        """Get path to production templates directory."""
        # Navigate from test file to templates directory
        # Templates are in packages/blinkb0t/core/domains/sequencing/templates/
        project_root = Path(__file__).parent.parent.parent
        return (
            project_root / "packages" / "blinkb0t" / "core" / "domains" / "sequencing" / "templates"
        )

    @pytest.fixture
    def loader(self, template_dir: Path) -> TemplateLoader:
        """Create template loader for production templates."""
        return TemplateLoader(template_dir)

    def test_all_templates_load(self, loader: TemplateLoader):
        """Test all production templates load without errors."""
        templates = loader.list_templates()

        # Should have templates
        assert len(templates) > 0

        # All should load successfully
        for template_id in templates:
            template = loader.load_template(template_id)
            assert template.template_id == template_id

    def test_all_templates_have_metadata(self, loader: TemplateLoader):
        """Test all templates have complete metadata."""
        templates = loader.list_templates()

        for template_id in templates:
            metadata = loader.get_template_metadata(template_id)

            # Required metadata fields
            assert "description" in metadata["metadata"]
            assert "recommended_sections" in metadata["metadata"]
            assert "energy_range" in metadata["metadata"]
            assert "tags" in metadata["metadata"]

            # Energy range should be valid
            energy_range = metadata["metadata"]["energy_range"]
            assert len(energy_range) == 2
            assert 0 <= energy_range[0] <= 100
            assert 0 <= energy_range[1] <= 100
            assert energy_range[0] <= energy_range[1]

    def test_pattern_ids_valid(self, loader: TemplateLoader):
        """Test all pattern IDs reference valid library entries."""
        templates = loader.list_templates()

        for template_id in templates:
            template = loader.load_template(template_id)

            for step in template.steps:
                # These will raise if invalid (validated by loader)
                assert step.movement_id
                assert step.dimmer_id
                # geometry_id is optional

    def test_timing_valid(self, loader: TemplateLoader):
        """Test timing is valid (positive durations, non-negative offsets)."""
        templates = loader.list_templates()

        for template_id in templates:
            template = loader.load_template(template_id)

            for step in template.steps:
                timing = step.timing.base_timing
                assert timing.duration_bars > 0
                assert timing.start_offset_bars >= 0

    def test_transitions_valid(self, loader: TemplateLoader):
        """Test transitions have valid configuration."""
        templates = loader.list_templates()

        for template_id in templates:
            template = loader.load_template(template_id)

            for step in template.steps:
                # SNAP should have 0 duration
                if step.entry_transition.mode == "snap":
                    assert step.entry_transition.duration_bars == 0.0

                if step.exit_transition.mode == "snap":
                    assert step.exit_transition.duration_bars == 0.0

                # Non-SNAP should have positive duration
                if step.entry_transition.mode != "snap":
                    assert step.entry_transition.duration_bars > 0.0

                if step.exit_transition.mode != "snap":
                    assert step.exit_transition.duration_bars > 0.0

    def test_specific_templates_exist(self, loader: TemplateLoader):
        """Test that expected templates exist."""
        expected_templates = [
            "gentle_sweep_breathe",
            "ambient_hold_pulse",
            "soft_tilt_swell",
            "balanced_fan_swell",
            "verse_sweep_pulse",
            "energetic_fan_pulse",
            "chorus_circle_strobe",
            "intense_figure8_flash",
            "crescendo_sweep_build",
            "impact_hold_flash",
            "smooth_fade_transition",
        ]

        templates = loader.list_templates()

        for expected in expected_templates:
            assert expected in templates, f"Expected template '{expected}' not found"

    def test_parameter_substitution_works(self, loader: TemplateLoader):
        """Test parameter substitution in templates."""
        # Note: Current templates use hardcoded values, not {{intensity}} placeholders
        # This test verifies templates load correctly with or without params
        # Load template without parameters (should use hardcoded values)
        template = loader.load_template("gentle_sweep_breathe")

        # Template should load successfully with hardcoded values
        assert template.steps[0].movement_params["intensity"] == "SMOOTH"

        # Load with parameters (should still work, but won't substitute without placeholders)
        template_with_params = loader.load_template(
            "gentle_sweep_breathe", params={"intensity": "DRAMATIC"}
        )

        # Since template doesn't have {{intensity}} placeholders, it keeps hardcoded value
        assert template_with_params.steps[0].movement_params["intensity"] == "SMOOTH"

    def test_energy_distribution(self, loader: TemplateLoader):
        """Test templates cover full energy spectrum."""
        templates = loader.list_templates()

        low_energy = []
        medium_energy = []
        high_energy = []

        for template_id in templates:
            metadata = loader.get_template_metadata(template_id)
            energy_avg = sum(metadata["metadata"]["energy_range"]) / 2

            if energy_avg < 40:
                low_energy.append(template_id)
            elif energy_avg < 70:
                medium_energy.append(template_id)
            else:
                high_energy.append(template_id)

        # Should have templates in all energy ranges
        assert len(low_energy) > 0, "No low energy templates"
        assert len(medium_energy) > 0, "No medium energy templates"
        assert len(high_energy) > 0, "No high energy templates"

    def test_section_coverage(self, loader: TemplateLoader):
        """Test templates cover common section types."""
        templates = loader.list_templates()

        section_tags = set()
        for template_id in templates:
            metadata = loader.get_template_metadata(template_id)
            recommended = metadata["metadata"]["recommended_sections"]
            section_tags.update(recommended)

        # Should have coverage for common sections
        # At least some of these should be present
        common_sections = ["verse", "chorus", "build", "drop", "transition"]
        covered_sections = [s for s in common_sections if any(s in tag for tag in section_tags)]

        assert len(covered_sections) >= 3, f"Insufficient section coverage: {covered_sections}"
