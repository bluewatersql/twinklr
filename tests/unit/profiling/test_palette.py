"""Unit tests for color palette parser/classifier."""

from __future__ import annotations

from twinklr.core.formats.xlights.sequence.models.xsq import ColorPalette, SequenceHead, XSequence
from twinklr.core.profiling.effects.palette import parse_color_palettes


def _base_sequence(palettes: list[ColorPalette]) -> XSequence:
    return XSequence(
        head=SequenceHead(version="2025.1", media_file="song.mp3", sequence_duration_ms=10_000),
        color_palettes=palettes,
    )


def test_parse_color_palettes_empty_sequence() -> None:
    profile = parse_color_palettes(_base_sequence([]))
    assert profile.unique_colors == ()
    assert profile.single_colors == ()
    assert profile.color_palettes == ()


def test_parse_color_palettes_single_color_warm() -> None:
    seq = _base_sequence([ColorPalette(settings="C_BUTTON_Palette1=#FF0000,C_CHECKBOX_Palette1=1")])
    profile = parse_color_palettes(seq)
    assert profile.unique_colors == ("#FF0000",)
    assert len(profile.classifications.warm) >= 1


def test_parse_color_palettes_color_curve() -> None:
    curve = "Active=TRUE|Values=x=0.190^c=#c8102e;x=0.240^c=#000000;|"
    seq = _base_sequence(
        [ColorPalette(settings=f"C_BUTTON_Palette1={curve},C_CHECKBOX_Palette1=1")]
    )
    profile = parse_color_palettes(seq)
    assert "#C8102E" in profile.unique_colors
    assert "#000000" in profile.unique_colors


def test_parse_color_palettes_disabled_slot_ignored() -> None:
    seq = _base_sequence([ColorPalette(settings="C_BUTTON_Palette1=#00FF00,C_CHECKBOX_Palette1=0")])
    profile = parse_color_palettes(seq)
    assert profile.unique_colors == ()
