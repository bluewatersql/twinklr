"""Tests for group template enums."""

from twinklr.core.sequencer.templates.group.enums import (
    AssetSlotType,
    ColorMode,
    GroupTemplateType,
    GroupVisualIntent,
    LayerRole,
    MotionVerb,
    ProjectionIntent,
    WarpHint,
)


class TestGroupTemplateType:
    """Test GroupTemplateType enum."""

    def test_all_values_present(self):
        """Test all expected template types are defined."""
        expected = {"BASE", "RHYTHM", "ACCENT", "TRANSITION", "SPECIAL"}
        actual = {t.value for t in GroupTemplateType}
        assert actual == expected

    def test_values_are_strings(self):
        """Test enum values are strings."""
        for template_type in GroupTemplateType:
            assert isinstance(template_type.value, str)

    def test_enum_comparison(self):
        """Test enum comparison works correctly."""
        assert GroupTemplateType.BASE == GroupTemplateType.BASE
        assert GroupTemplateType.BASE != GroupTemplateType.RHYTHM


class TestGroupVisualIntent:
    """Test GroupVisualIntent enum."""

    def test_all_values_present(self):
        """Test all expected visual intents are defined."""
        expected = {"ABSTRACT", "IMAGERY", "HYBRID", "TEXTURE", "GEOMETRIC", "ORGANIC"}
        actual = {v.value for v in GroupVisualIntent}
        assert actual == expected

    def test_values_are_strings(self):
        """Test enum values are strings."""
        for intent in GroupVisualIntent:
            assert isinstance(intent.value, str)


class TestMotionVerb:
    """Test MotionVerb enum."""

    def test_all_values_present(self):
        """Test all expected motion verbs are defined."""
        expected = {
            "NONE",
            "PULSE",
            "SWEEP",
            "WAVE",
            "RIPPLE",
            "CHASE",
            "STROBE",
            "BOUNCE",
            "SPARKLE",
            "FADE",
            "WIPE",
            "TWINKLE",
            "SHIMMER",
            "ROLL",
            "FLIP",
        }
        actual = {m.value for m in MotionVerb}
        assert actual == expected

    def test_values_are_strings(self):
        """Test enum values are strings."""
        for verb in MotionVerb:
            assert isinstance(verb.value, str)

    def test_none_motion(self):
        """Test NONE motion exists for static content."""
        assert MotionVerb.NONE.value == "NONE"


class TestLayerRole:
    """Test LayerRole enum."""

    def test_all_values_present(self):
        """Test all expected layer roles are defined."""
        expected = {"BACKGROUND", "MIDGROUND", "FOREGROUND", "ACCENT", "TEXTURE"}
        actual = {r.value for r in LayerRole}
        assert actual == expected

    def test_values_are_strings(self):
        """Test enum values are strings."""
        for role in LayerRole:
            assert isinstance(role.value, str)


class TestProjectionIntent:
    """Test ProjectionIntent enum."""

    def test_all_values_present(self):
        """Test all expected projection intents are defined."""
        expected = {"FLAT", "POLAR", "PERSPECTIVE", "CYLINDRICAL", "SPHERICAL"}
        actual = {p.value for p in ProjectionIntent}
        assert actual == expected

    def test_values_are_strings(self):
        """Test enum values are strings."""
        for intent in ProjectionIntent:
            assert isinstance(intent.value, str)


class TestWarpHint:
    """Test WarpHint enum."""

    def test_all_values_present(self):
        """Test all expected warp hints are defined."""
        expected = {"SEAM_SAFE", "RADIAL_SYMMETRY", "TILE_X", "TILE_Y", "TILE_XY"}
        actual = {w.value for w in WarpHint}
        assert actual == expected

    def test_values_are_strings(self):
        """Test enum values are strings."""
        for hint in WarpHint:
            assert isinstance(hint.value, str)


class TestAssetSlotType:
    """Test AssetSlotType enum."""

    def test_all_values_present(self):
        """Test all expected asset slot types are defined."""
        expected = {"PNG_OPAQUE", "PNG_TRANSPARENT", "PNG_TILE", "GIF_OVERLAY"}
        actual = {a.value for a in AssetSlotType}
        assert actual == expected

    def test_values_are_strings(self):
        """Test enum values are strings."""
        for slot_type in AssetSlotType:
            assert isinstance(slot_type.value, str)


class TestColorMode:
    """Test ColorMode enum."""

    def test_all_values_present(self):
        """Test all expected color modes are defined."""
        expected = {"MONOCHROME", "DICHROME", "TRIAD", "ANALOGOUS", "FULL_SPECTRUM"}
        actual = {c.value for c in ColorMode}
        assert actual == expected

    def test_values_are_strings(self):
        """Test enum values are strings."""
        for mode in ColorMode:
            assert isinstance(mode.value, str)
