"""Tests for corpus_artifacts.load_profile_artifacts's parquet/jsonl reader."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import sys
import types
from typing import TYPE_CHECKING

from twinklr.core.feature_engineering.corpus_artifacts import load_profile_artifacts

if TYPE_CHECKING:
    import pytest

_LOGGER_NAME = "twinklr.core.feature_engineering.corpus_artifacts"


def _effect_phrase_dict(phrase_id: str = "p1") -> dict:
    """Minimal valid EffectPhrase row."""
    return {
        "schema_version": "1.0",
        "phrase_id": phrase_id,
        "package_id": "pkg1",
        "sequence_file_id": "seq1",
        "effect_event_id": "evt1",
        "effect_type": "Twinkle",
        "effect_family": "twinkle",
        "motion_class": "static",
        "color_class": "mono",
        "energy_class": "low",
        "continuity_class": "sustained",
        "spatial_class": "single_target",
        "source": "fallback",
        "map_confidence": 0.5,
        "target_name": "Group1",
        "layer_index": 0,
        "start_ms": 0,
        "end_ms": 1000,
        "duration_ms": 1000,
        "param_signature": "sig1",
    }


def test_read_models_logs_warning_on_parquet_corruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A genuine parquet-read exception is logged as a warning, not swallowed."""
    (tmp_path / "effect_phrases.parquet").write_bytes(b"not a real parquet file")
    (tmp_path / "effect_phrases.jsonl").write_text(
        json.dumps(_effect_phrase_dict()) + "\n", encoding="utf-8"
    )

    fake_pq = types.ModuleType("pyarrow.parquet")

    def _raise_corruption(_path: Path) -> object:
        raise ValueError("corrupt parquet file")

    fake_pq.read_table = _raise_corruption  # type: ignore[attr-defined]
    fake_pyarrow = types.ModuleType("pyarrow")
    fake_pyarrow.parquet = fake_pq  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "pyarrow", fake_pyarrow)
    monkeypatch.setitem(sys.modules, "pyarrow.parquet", fake_pq)

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        result = load_profile_artifacts(tmp_path)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("Parquet read failed" in r.message for r in warnings)
    assert any("effect_phrases" in r.message for r in warnings)

    # Falls through to the jsonl sibling unchanged — data is still loaded.
    assert result is not None
    phrases, _taxonomy, _roles = result
    assert len(phrases) == 1
    assert phrases[0].phrase_id == "p1"


def test_read_models_silent_on_missing_pyarrow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """ImportError (pyarrow not installed) falls through to jsonl without a warning."""
    (tmp_path / "effect_phrases.parquet").write_bytes(b"irrelevant - import fails first")
    (tmp_path / "effect_phrases.jsonl").write_text(
        json.dumps(_effect_phrase_dict()) + "\n", encoding="utf-8"
    )

    monkeypatch.setitem(sys.modules, "pyarrow", None)
    monkeypatch.setitem(sys.modules, "pyarrow.parquet", None)

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        result = load_profile_artifacts(tmp_path)

    assert not any("Parquet read failed" in r.message for r in caplog.records)

    assert result is not None
    phrases, _taxonomy, _roles = result
    assert len(phrases) == 1
