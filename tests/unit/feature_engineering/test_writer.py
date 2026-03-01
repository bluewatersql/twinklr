"""Unit tests for FeatureEngineeringWriter dataset write methods.

Covers CQ-03 (ImportError specificity) and CQ-04 (deduplicated _write_dataset).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from twinklr.core.feature_engineering.datasets.writer import FeatureEngineeringWriter
from twinklr.core.feature_engineering.models import AlignedEffectEvent, AlignmentStatus
from twinklr.core.feature_engineering.models.layering import LayeringFeatureRow

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_aligned_event() -> AlignedEffectEvent:
    """Return a minimal valid AlignedEffectEvent."""
    return AlignedEffectEvent(
        schema_version="v1",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id="evt-1",
        target_name="Tree",
        layer_index=0,
        effect_type="On",
        start_ms=0,
        end_ms=1000,
        duration_ms=1000,
        start_s=0.0,
        end_s=1.0,
        alignment_status=AlignmentStatus.ALIGNED,
    )


def _make_layering_row() -> LayeringFeatureRow:
    """Return a minimal valid LayeringFeatureRow."""
    return LayeringFeatureRow(
        schema_version="v1",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        phrase_count=1,
        max_concurrent_layers=1,
        mean_concurrent_layers=1.0,
        hierarchy_transitions=0,
        overlap_pairs=0,
        same_target_overlap_pairs=0,
        collision_score=0.0,
    )


# ---------------------------------------------------------------------------
# _write_dataset: parquet path (pyarrow present)
# ---------------------------------------------------------------------------


def test_write_dataset_parquet_when_pyarrow_available(tmp_path: Path) -> None:
    """_write_dataset writes a .parquet file when pyarrow is importable."""
    writer = FeatureEngineeringWriter()
    rows: list[dict[str, Any]] = [{"x": 1, "y": "hello"}]

    # Ensure _HAS_PYARROW is True in the module under test.
    import twinklr.core.feature_engineering.datasets.writer as writer_mod

    if not writer_mod._HAS_PYARROW:
        pytest.skip("pyarrow not installed in this environment")

    result = writer._write_dataset(tmp_path, "test_stem", rows)

    assert result == tmp_path / "test_stem.parquet"
    assert result.exists()
    assert result.suffix == ".parquet"


# ---------------------------------------------------------------------------
# _write_dataset: JSONL fallback path (pyarrow absent)
# ---------------------------------------------------------------------------


def test_write_dataset_jsonl_fallback_when_pyarrow_absent(tmp_path: Path) -> None:
    """_write_dataset falls back to .jsonl when _HAS_PYARROW is False."""
    import twinklr.core.feature_engineering.datasets.writer as writer_mod

    rows: list[dict[str, Any]] = [{"a": 1}, {"a": 2}]
    writer = FeatureEngineeringWriter()

    with patch.object(writer_mod, "_HAS_PYARROW", False):
        result = writer._write_dataset(tmp_path, "test_stem", rows)

    assert result == tmp_path / "test_stem.jsonl"
    assert result.exists()
    lines = result.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"a": 1}
    assert json.loads(lines[1]) == {"a": 2}


# ---------------------------------------------------------------------------
# _write_dataset: non-ImportError from pyarrow must NOT be swallowed (CQ-03)
# ---------------------------------------------------------------------------


def test_write_dataset_non_import_error_propagates(tmp_path: Path) -> None:
    """A RuntimeError raised inside _write_dataset must propagate, not be swallowed."""
    import twinklr.core.feature_engineering.datasets.writer as writer_mod

    writer = FeatureEngineeringWriter()
    rows: list[dict[str, Any]] = [{"x": 1}]

    if not writer_mod._HAS_PYARROW:
        pytest.skip("pyarrow not installed; cannot test non-ImportError propagation path")

    # Patch pa.Table.from_pylist to raise a non-ImportError.
    import pyarrow as pa

    with (
        patch.object(pa.Table, "from_pylist", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError, match="boom"),
    ):
        writer._write_dataset(tmp_path, "test_stem", rows)


# ---------------------------------------------------------------------------
# Public write methods: 2-line wrapper shape
# ---------------------------------------------------------------------------


def test_write_aligned_events_parquet(tmp_path: Path) -> None:
    """write_aligned_events delegates to _write_dataset and returns the path."""
    import twinklr.core.feature_engineering.datasets.writer as writer_mod

    if not writer_mod._HAS_PYARROW:
        pytest.skip("pyarrow not installed")

    writer = FeatureEngineeringWriter()
    event = _make_aligned_event()
    result = writer.write_aligned_events(tmp_path, (event,))

    assert result == tmp_path / "aligned_events.parquet"
    assert result.exists()


def test_write_aligned_events_jsonl_fallback(tmp_path: Path) -> None:
    """write_aligned_events writes JSONL when _HAS_PYARROW is False."""
    import twinklr.core.feature_engineering.datasets.writer as writer_mod

    writer = FeatureEngineeringWriter()
    event = _make_aligned_event()

    with patch.object(writer_mod, "_HAS_PYARROW", False):
        result = writer.write_aligned_events(tmp_path, (event,))

    assert result == tmp_path / "aligned_events.jsonl"
    assert result.exists()
    data = json.loads(result.read_text(encoding="utf-8").splitlines()[0])
    assert data["effect_event_id"] == "evt-1"


def test_write_layering_features_jsonl_fallback(tmp_path: Path) -> None:
    """write_layering_features falls back to JSONL when _HAS_PYARROW is False."""
    import twinklr.core.feature_engineering.datasets.writer as writer_mod

    writer = FeatureEngineeringWriter()
    row = _make_layering_row()

    with patch.object(writer_mod, "_HAS_PYARROW", False):
        result = writer.write_layering_features(tmp_path, (row,))

    assert result == tmp_path / "layering_features.jsonl"
    assert result.exists()
    data = json.loads(result.read_text(encoding="utf-8").splitlines()[0])
    assert data["package_id"] == "pkg-1"


# ---------------------------------------------------------------------------
# Module-level _HAS_PYARROW flag (CQ-03)
# ---------------------------------------------------------------------------


def test_has_pyarrow_flag_is_bool() -> None:
    """_HAS_PYARROW must be a plain bool at module level."""
    import twinklr.core.feature_engineering.datasets.writer as writer_mod

    assert isinstance(writer_mod._HAS_PYARROW, bool)
