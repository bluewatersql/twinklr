"""Tests for FeatureEngineeringPipelineOptions corpus-root validation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from twinklr.core.feature_engineering.config import (
    FeatureEngineeringPipelineOptions,
    warn_missing_corpus_roots,
)

if TYPE_CHECKING:
    import pytest

_LOGGER_NAME = "twinklr.core.feature_engineering.config"


def test_missing_corpus_root_logs_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """A nonexistent extracted_search_roots/music_repo_roots entry logs a warning
    naming the missing path, without raising."""
    missing_extracted = tmp_path / "does_not_exist_vendor_packages"
    missing_music = tmp_path / "does_not_exist_music"
    options = FeatureEngineeringPipelineOptions(
        extracted_search_roots=(missing_extracted,),
        music_repo_roots=(missing_music,),
    )

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        warn_missing_corpus_roots(options)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert str(missing_extracted) in warnings[0].message
    assert str(missing_music) in warnings[0].message


def test_existing_corpus_root_does_not_warn(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Corpus roots that exist on disk produce no warning."""
    options = FeatureEngineeringPipelineOptions(
        extracted_search_roots=(tmp_path,),
        music_repo_roots=(tmp_path,),
    )

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        warn_missing_corpus_roots(options)

    assert not [r for r in caplog.records if r.levelno == logging.WARNING]


def test_missing_corpus_root_does_not_raise(tmp_path: Path) -> None:
    """Missing corpus roots are a warning, not a fail-fast error."""
    options = FeatureEngineeringPipelineOptions(
        extracted_search_roots=(tmp_path / "missing",),
    )
    warn_missing_corpus_roots(options)  # must not raise
