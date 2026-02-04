"""Tests for asset template enums."""

from twinklr.core.sequencer.vocabulary import (
    AssetTemplateType,
    BackgroundMode,
    MatrixAspect,
    TemplateProjectionHint,
)


class TestAssetTemplateType:
    """Test AssetTemplateType enum."""

    def test_all_values_present(self):
        """Test all expected asset template types are defined."""
        expected = {"PNG_OPAQUE", "PNG_TRANSPARENT", "PNG_TILE", "GIF_OVERLAY"}
        actual = {t.value for t in AssetTemplateType}
        assert actual == expected

    def test_values_are_strings(self):
        """Test enum values are strings."""
        for template_type in AssetTemplateType:
            assert isinstance(template_type.value, str)

    def test_png_types_distinct(self):
        """Test PNG types are distinct."""
        assert AssetTemplateType.PNG_OPAQUE != AssetTemplateType.PNG_TRANSPARENT
        assert AssetTemplateType.PNG_OPAQUE != AssetTemplateType.PNG_TILE


class TestBackgroundMode:
    """Test BackgroundMode enum."""

    def test_all_values_present(self):
        """Test all expected background modes are defined."""
        expected = {"transparent", "opaque"}
        actual = {m.value for m in BackgroundMode}
        assert actual == expected

    def test_values_are_lowercase(self):
        """Test enum values are lowercase strings."""
        for mode in BackgroundMode:
            assert isinstance(mode.value, str)
            assert mode.value == mode.value.lower()


class TestMatrixAspect:
    """Test MatrixAspect enum."""

    def test_all_values_present(self):
        """Test all expected aspect ratios are defined."""
        expected = {"1:1", "2:1", "1:2", "16:9", "4:3"}
        actual = {a.value for a in MatrixAspect}
        assert actual == expected

    def test_values_are_ratio_strings(self):
        """Test enum values are ratio strings."""
        for aspect in MatrixAspect:
            assert isinstance(aspect.value, str)
            assert ":" in aspect.value

    def test_square_aspect(self):
        """Test square aspect ratio."""
        assert MatrixAspect.SQUARE.value == "1:1"

    def test_hd_aspect(self):
        """Test HD aspect ratio."""
        assert MatrixAspect.HD.value == "16:9"


class TestTemplateProjectionHint:
    """Test TemplateProjectionHint enum."""

    def test_all_values_present(self):
        """Test all expected projection hints are defined."""
        expected = {"FLAT", "POLAR_CONE", "POLAR_CYLINDER"}
        actual = {h.value for h in TemplateProjectionHint}
        assert actual == expected

    def test_values_are_strings(self):
        """Test enum values are strings."""
        for hint in TemplateProjectionHint:
            assert isinstance(hint.value, str)

    def test_flat_projection(self):
        """Test flat projection exists."""
        assert TemplateProjectionHint.FLAT.value == "FLAT"
