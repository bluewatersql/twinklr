"""Unit tests for layout classifier helpers."""

from __future__ import annotations

from twinklr.core.profiling.layout.classifier import (
    classify_model_category,
    classify_semantic_size,
    classify_semantic_tags,
)
from twinklr.core.profiling.models.enums import ModelCategory, SemanticSize


def test_classify_semantic_tags_arch() -> None:
    assert classify_semantic_tags("Arch 1") == frozenset({"arch"})


def test_classify_semantic_size_mega_tree() -> None:
    assert classify_semantic_tags("MegaTree Left") == frozenset({"tree"})
    assert classify_semantic_size("MegaTree Left") is SemanticSize.MEGA


def test_classify_semantic_tags_fallback_display_as() -> None:
    assert classify_semantic_tags("", display_as="dmxmovinghead") == frozenset({"moving_head"})


def test_classify_model_category_dmx_fixture() -> None:
    assert classify_model_category("", "dmxmovingheadadv", True) is ModelCategory.DMX_FIXTURE


def test_classify_model_category_auxiliary() -> None:
    assert classify_model_category("dmx pan", "single line", True) is ModelCategory.AUXILIARY


def test_classify_model_category_inactive() -> None:
    assert classify_model_category("Arch", "Arches", False) is ModelCategory.INACTIVE
