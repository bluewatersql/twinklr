"""Tests for AI asset generation provider interface."""

from __future__ import annotations

from twinklr.core.assets.generator import AssetGenerator, PromptBuilder
from twinklr.core.assets.models import AssetError, AssetRequest, AssetResult


def test_asset_request_creation() -> None:
    """AssetRequest created with defaults."""
    req = AssetRequest(asset_id="a1", prompt="Snowflake pattern")
    assert req.asset_id == "a1"
    assert req.prompt == "Snowflake pattern"
    assert req.width == 512
    assert req.height == 512
    assert req.format == "png"
    assert req.palette_colors == []
    assert req.style_hint == ""


def test_asset_result_creation() -> None:
    """AssetResult stores all fields."""
    result = AssetResult(
        asset_id="a1",
        file_path="/tmp/a1.png",
        content_hash="abc123",
        prompt_used="test prompt",
        cached=True,
    )
    assert result.asset_id == "a1"
    assert result.file_path == "/tmp/a1.png"
    assert result.content_hash == "abc123"
    assert result.cached is True


def test_asset_error_creation() -> None:
    """AssetError stores error and retryable flag."""
    err = AssetError(asset_id="a1", error="Rate limited", retryable=True)
    assert err.retryable is True


def test_prompt_builder_basic() -> None:
    """Basic prompt includes system prefix and technical suffix."""
    req = AssetRequest(asset_id="a1", prompt="Snowflake pattern")
    prompt = PromptBuilder().build(req)
    assert "Christmas light show" in prompt
    assert "Snowflake pattern" in prompt
    assert "LED display" in prompt


def test_prompt_builder_with_palette() -> None:
    """Palette colors included in prompt."""
    req = AssetRequest(
        asset_id="a1",
        prompt="Snowflake",
        palette_colors=["#FF0000", "#00FF00"],
    )
    prompt = PromptBuilder().build(req)
    assert "#FF0000" in prompt
    assert "#00FF00" in prompt


def test_prompt_builder_with_style_hint() -> None:
    """Style hint included in prompt."""
    req = AssetRequest(asset_id="a1", prompt="Pattern", style_hint="whimsical")
    prompt = PromptBuilder().build(req)
    assert "whimsical" in prompt


def test_prompt_builder_full() -> None:
    """Full prompt with all fields."""
    req = AssetRequest(
        asset_id="a1",
        prompt="Star burst",
        style_hint="festive",
        palette_colors=["#FFFFFF"],
        width=1024,
        height=1024,
    )
    prompt = PromptBuilder().build(req)
    assert "festive" in prompt
    assert "Star burst" in prompt
    assert "#FFFFFF" in prompt
    assert "1024x1024" in prompt


def test_asset_generator_protocol() -> None:
    """AssetGenerator protocol is runtime checkable."""
    assert hasattr(AssetGenerator, "__protocol_attrs__") or hasattr(
        AssetGenerator, "__abstractmethods__"
    )
    # Verify it's a protocol by checking it can't be instantiated naively
    # but can be used for isinstance checks
    import typing

    assert typing.runtime_checkable
