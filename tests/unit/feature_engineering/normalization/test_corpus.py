"""Tests for UnknownEffectCorpusBuilder."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from twinklr.core.feature_engineering.normalization.corpus import UnknownEffectCorpusBuilder

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_diagnostics(path: Path, data: dict) -> Path:
    p = path / "unknown_diagnostics.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _minimal_diagnostics(top_unknown: list | None = None) -> dict:
    return {
        "schema_version": "v1.0.0",
        "total_phrase_count": 100,
        "unknown_effect_family_count": 5,
        "unknown_effect_family_ratio": 0.05,
        "unknown_motion_count": 3,
        "unknown_motion_ratio": 0.03,
        "top_unknown_effect_types": top_unknown or [],
        "alias_candidate_groups": [],
    }


def _make_entry(effect_type: str, count: int, sample_rows: list | None = None) -> dict:
    return {
        "effect_type": effect_type,
        "normalized_key": effect_type.lower(),
        "count": count,
        "distinct_package_count": 1,
        "distinct_sequence_count": 1,
        "sample_rows": sample_rows or [],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParseValidDiagnostics:
    """test_parse_valid_diagnostics: parsing produces correct entry count and fields."""

    def test_entry_count_matches_top_unknown(self, tmp_path: Path) -> None:
        data = _minimal_diagnostics(
            top_unknown=[
                _make_entry("Chase", 10),
                _make_entry("Strobe", 5),
            ]
        )
        path = _write_diagnostics(tmp_path, data)
        corpus = UnknownEffectCorpusBuilder().build(path)
        assert len(corpus.entries) == 2

    def test_entry_fields_populated(self, tmp_path: Path) -> None:
        sample_row = {"phrase_id": "ph-1", "package_id": "pkg-1"}
        data = _minimal_diagnostics(
            top_unknown=[_make_entry("Chase", 10, sample_rows=[sample_row])]
        )
        path = _write_diagnostics(tmp_path, data)
        corpus = UnknownEffectCorpusBuilder().build(path)
        entry = corpus.entries[0]
        assert entry.effect_type == "Chase"
        assert entry.normalized_key == "chase"
        assert entry.count == 10
        assert len(entry.sample_params) == 1
        assert entry.sample_params[0] == sample_row

    def test_corpus_ratios_match_diagnostics(self, tmp_path: Path) -> None:
        data = _minimal_diagnostics()
        path = _write_diagnostics(tmp_path, data)
        corpus = UnknownEffectCorpusBuilder().build(path)
        assert corpus.unknown_effect_family_ratio == pytest.approx(0.05)
        assert corpus.unknown_motion_ratio == pytest.approx(0.03)
        assert corpus.total_unknown_phrases == 5


class TestContextTextIncludesEffectNameAndParams:
    """test_context_text_includes_effect_name_and_params."""

    def test_context_text_contains_effect_type(self, tmp_path: Path) -> None:
        data = _minimal_diagnostics(top_unknown=[_make_entry("Chase", 10)])
        path = _write_diagnostics(tmp_path, data)
        corpus = UnknownEffectCorpusBuilder().build(path)
        assert "Chase" in corpus.entries[0].context_text

    def test_context_text_is_nonempty(self, tmp_path: Path) -> None:
        data = _minimal_diagnostics(top_unknown=[_make_entry("Morph", 3)])
        path = _write_diagnostics(tmp_path, data)
        corpus = UnknownEffectCorpusBuilder().build(path)
        assert corpus.entries[0].context_text != ""

    def test_context_text_includes_sample_row_values(self, tmp_path: Path) -> None:
        sample_row = {"phrase_id": "ph-42", "package_id": "pkg-99"}
        data = _minimal_diagnostics(
            top_unknown=[_make_entry("Chase", 10, sample_rows=[sample_row])]
        )
        path = _write_diagnostics(tmp_path, data)
        corpus = UnknownEffectCorpusBuilder().build(path)
        ctx = corpus.entries[0].context_text
        assert "ph-42" in ctx
        assert "pkg-99" in ctx


class TestEmptyDiagnosticsReturnsEmptyCorpus:
    """test_empty_diagnostics_returns_empty_corpus."""

    def test_zero_entries_when_top_unknown_empty(self, tmp_path: Path) -> None:
        data = _minimal_diagnostics(top_unknown=[])
        path = _write_diagnostics(tmp_path, data)
        corpus = UnknownEffectCorpusBuilder().build(path)
        assert len(corpus.entries) == 0

    def test_corpus_schema_version_default(self, tmp_path: Path) -> None:
        data = _minimal_diagnostics(top_unknown=[])
        path = _write_diagnostics(tmp_path, data)
        corpus = UnknownEffectCorpusBuilder().build(path)
        assert corpus.schema_version == "1.0.0"


class TestEntriesSortedByCountDescending:
    """test_entries_sorted_by_count_descending."""

    def test_highest_count_first(self, tmp_path: Path) -> None:
        data = _minimal_diagnostics(
            top_unknown=[
                _make_entry("Slow", 2),
                _make_entry("Fast", 20),
                _make_entry("Mid", 10),
            ]
        )
        path = _write_diagnostics(tmp_path, data)
        corpus = UnknownEffectCorpusBuilder().build(path)
        counts = [e.count for e in corpus.entries]
        assert counts == sorted(counts, reverse=True)
        assert corpus.entries[0].effect_type == "Fast"
