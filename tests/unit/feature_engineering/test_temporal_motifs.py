"""Tests for temporal (ordered) motif mining — Spec 03."""

from __future__ import annotations

from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.models.templates import (
    TemplateAssignment,
    TemplateCatalog,
    TemplateKind,
)
from twinklr.core.feature_engineering.models.temporal_motifs import (
    TemporalMotifCatalog,
)
from twinklr.core.feature_engineering.motifs import MotifMiner, MotifMinerOptions

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _phrase(
    phrase_id: str,
    package_id: str,
    sequence_file_id: str,
    target_name: str,
    start_ms: int,
    end_ms: int,
    effect_family: str,
    energy_class: EnergyClass = EnergyClass.MID,
    motion_class: MotionClass = MotionClass.SWEEP,
) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.2.0",
        phrase_id=phrase_id,
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        effect_event_id=f"evt-{phrase_id}",
        effect_type=effect_family,
        effect_family=effect_family,
        motion_class=motion_class,
        color_class=ColorClass.PALETTE,
        energy_class=energy_class,
        continuity_class=ContinuityClass.RHYTHMIC,
        spatial_class=SpatialClass.GROUP,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=1.0,
        target_name=target_name,
        layer_index=0,
        start_ms=start_ms,
        end_ms=end_ms,
        duration_ms=end_ms - start_ms,
        start_beat_index=None,
        end_beat_index=None,
        section_label="verse",
        onset_sync_score=0.8,
        param_signature="sig",
    )


def _catalogs(
    assignments: tuple[TemplateAssignment, ...],
    total: int,
) -> tuple[TemplateCatalog, TemplateCatalog]:
    content = TemplateCatalog(
        schema_version="v1.5.0",
        miner_version="test",
        template_kind=TemplateKind.CONTENT,
        total_phrase_count=total,
        assigned_phrase_count=total,
        assignment_coverage=1.0,
        min_instance_count=1,
        min_distinct_pack_count=1,
        templates=(),
        assignments=assignments,
    )
    orch = content.model_copy(
        update={
            "template_kind": TemplateKind.ORCHESTRATION,
            "assignments": (),
            "assigned_phrase_count": 0,
            "assignment_coverage": 0.0,
        }
    )
    return content, orch


def _assignment(
    package_id: str,
    sequence_file_id: str,
    phrase_id: str,
    template_id: str,
) -> TemplateAssignment:
    return TemplateAssignment(
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        phrase_id=phrase_id,
        effect_event_id=f"evt-{phrase_id}",
        template_id=template_id,
    )


# ---------------------------------------------------------------------------
# 1. Bigram discovery
# ---------------------------------------------------------------------------


def test_bigram_discovery() -> None:
    """Two sequences each with [color_wash -> single_strand] -> support=2."""
    phrases = (
        # Sequence 1, target Tree
        _phrase("p1", "pkg-a", "seq-1", "Tree", 0, 500, "color_wash"),
        _phrase("p2", "pkg-a", "seq-1", "Tree", 550, 1050, "single_strand"),
        # Sequence 2, target Tree
        _phrase("p3", "pkg-b", "seq-2", "Tree", 0, 500, "color_wash"),
        _phrase("p4", "pkg-b", "seq-2", "Tree", 550, 1050, "single_strand"),
    )
    assignments = tuple(
        _assignment(p.package_id, p.sequence_file_id, p.phrase_id, f"t-{p.effect_family}")
        for p in phrases
    )
    content, orch = _catalogs(assignments, len(phrases))

    miner = MotifMiner(MotifMinerOptions(min_support_count=2, min_distinct_sequence_count=2))
    catalog = miner.mine_temporal(
        phrases=phrases,
        content_catalog=content,
        orchestration_catalog=orch,
    )

    assert isinstance(catalog, TemporalMotifCatalog)
    assert catalog.total_temporal_motifs >= 1

    # Find the bigram motif
    bigrams = [m for m in catalog.motifs if m.sequence_length == 2]
    assert len(bigrams) >= 1
    motif = bigrams[0]
    assert motif.support_count >= 2
    assert motif.distinct_sequence_count >= 2
    assert len(motif.steps) == 2
    assert motif.steps[0].position == 0
    assert motif.steps[1].position == 1
    assert motif.steps[0].gap_from_previous_ms is None
    assert motif.steps[1].gap_from_previous_ms is not None


# ---------------------------------------------------------------------------
# 2. Trigram discovery
# ---------------------------------------------------------------------------


def test_trigram_discovery() -> None:
    """Three sequences with [fill -> bars -> shockwave] -> discovered."""
    seqs = [("pkg-a", "seq-1"), ("pkg-b", "seq-2"), ("pkg-c", "seq-3")]
    phrases_list: list[EffectPhrase] = []
    assignments_list: list[TemplateAssignment] = []
    for i, (pkg, seq) in enumerate(seqs):
        for j, (fam, tmpl) in enumerate(
            [("fill", "t-fill"), ("bars", "t-bars"), ("shockwave", "t-shock")]
        ):
            pid = f"p{i * 3 + j}"
            start = j * 600
            phrases_list.append(_phrase(pid, pkg, seq, "Tree", start, start + 500, fam))
            assignments_list.append(_assignment(pkg, seq, pid, tmpl))

    phrases = tuple(phrases_list)
    content, orch = _catalogs(tuple(assignments_list), len(phrases))

    miner = MotifMiner(MotifMinerOptions(min_support_count=2, min_distinct_sequence_count=2))
    catalog = miner.mine_temporal(
        phrases=phrases,
        content_catalog=content,
        orchestration_catalog=orch,
    )

    trigrams = [m for m in catalog.motifs if m.sequence_length == 3]
    assert len(trigrams) >= 1
    tri = trigrams[0]
    assert tri.support_count >= 3
    assert len(tri.steps) == 3


# ---------------------------------------------------------------------------
# 3. Ordering matters
# ---------------------------------------------------------------------------


def test_ordering_matters() -> None:
    """[A->B] and [B->A] produce different temporal signatures."""
    # Sequence 1: color_wash -> bars (A->B)
    # Sequence 2: bars -> color_wash (B->A)
    phrases = (
        _phrase("p1", "pkg-a", "seq-1", "Tree", 0, 500, "color_wash"),
        _phrase("p2", "pkg-a", "seq-1", "Tree", 550, 1050, "bars"),
        _phrase("p3", "pkg-b", "seq-2", "Tree", 0, 500, "bars"),
        _phrase("p4", "pkg-b", "seq-2", "Tree", 550, 1050, "color_wash"),
    )
    assignments = tuple(
        _assignment(p.package_id, p.sequence_file_id, p.phrase_id, f"t-{p.effect_family}")
        for p in phrases
    )
    content, orch = _catalogs(assignments, len(phrases))

    # Use min_support=1 and min_distinct_sequence_count=1 to see both
    miner = MotifMiner(MotifMinerOptions(min_support_count=1, min_distinct_sequence_count=1))
    catalog = miner.mine_temporal(
        phrases=phrases,
        content_catalog=content,
        orchestration_catalog=orch,
    )

    bigrams = [m for m in catalog.motifs if m.sequence_length == 2]
    signatures = {m.temporal_signature for m in bigrams}
    # We should have at least 2 different signatures (A->B != B->A)
    assert len(signatures) >= 2


# ---------------------------------------------------------------------------
# 4. Gap bucketing
# ---------------------------------------------------------------------------


def test_gap_bucketing() -> None:
    """50ms->immediate, 300ms->short, 1000ms->medium, 3000ms->long."""
    gap_cases = [
        (50, "immediate"),
        (300, "short"),
        (1000, "medium"),
        (3000, "long"),
    ]
    for gap_ms, expected_bucket in gap_cases:
        phrases = (
            _phrase("p1", "pkg-a", "seq-1", "Tree", 0, 100, "color_wash"),
            _phrase(
                "p2",
                "pkg-a",
                "seq-1",
                "Tree",
                100 + gap_ms,
                100 + gap_ms + 500,
                "bars",
            ),
            _phrase("p3", "pkg-b", "seq-2", "Tree", 0, 100, "color_wash"),
            _phrase(
                "p4",
                "pkg-b",
                "seq-2",
                "Tree",
                100 + gap_ms,
                100 + gap_ms + 500,
                "bars",
            ),
        )
        assignments = tuple(
            _assignment(p.package_id, p.sequence_file_id, p.phrase_id, f"t-{p.effect_family}")
            for p in phrases
        )
        content, orch = _catalogs(assignments, len(phrases))

        miner = MotifMiner(MotifMinerOptions(min_support_count=2, min_distinct_sequence_count=2))
        catalog = miner.mine_temporal(
            phrases=phrases,
            content_catalog=content,
            orchestration_catalog=orch,
        )
        bigrams = [m for m in catalog.motifs if m.sequence_length == 2]
        assert len(bigrams) >= 1, f"No bigrams for gap={gap_ms}ms"
        sig = bigrams[0].temporal_signature
        assert expected_bucket in sig, (
            f"Expected '{expected_bucket}' in signature for gap={gap_ms}ms, got: {sig}"
        )


# ---------------------------------------------------------------------------
# 5. Pattern naming
# ---------------------------------------------------------------------------


def test_pattern_naming() -> None:
    """low->high='build', high->low='drop'."""
    # Build pattern: low -> high
    build_phrases = (
        _phrase(
            "p1",
            "pkg-a",
            "seq-1",
            "Tree",
            0,
            500,
            "color_wash",
            energy_class=EnergyClass.LOW,
        ),
        _phrase(
            "p2",
            "pkg-a",
            "seq-1",
            "Tree",
            550,
            1050,
            "bars",
            energy_class=EnergyClass.HIGH,
        ),
        _phrase(
            "p3",
            "pkg-b",
            "seq-2",
            "Tree",
            0,
            500,
            "color_wash",
            energy_class=EnergyClass.LOW,
        ),
        _phrase(
            "p4",
            "pkg-b",
            "seq-2",
            "Tree",
            550,
            1050,
            "bars",
            energy_class=EnergyClass.HIGH,
        ),
    )
    build_assignments = tuple(
        _assignment(p.package_id, p.sequence_file_id, p.phrase_id, f"t-{p.effect_family}")
        for p in build_phrases
    )
    content, orch = _catalogs(build_assignments, len(build_phrases))

    miner = MotifMiner(MotifMinerOptions(min_support_count=2, min_distinct_sequence_count=2))
    catalog = miner.mine_temporal(
        phrases=build_phrases,
        content_catalog=content,
        orchestration_catalog=orch,
    )
    bigrams = [m for m in catalog.motifs if m.sequence_length == 2]
    assert any(m.pattern_name == "build" for m in bigrams), (
        f"Expected 'build' pattern, got: {[m.pattern_name for m in bigrams]}"
    )

    # Drop pattern: high -> low
    drop_phrases = (
        _phrase(
            "p5",
            "pkg-c",
            "seq-3",
            "Tree",
            0,
            500,
            "bars",
            energy_class=EnergyClass.HIGH,
        ),
        _phrase(
            "p6",
            "pkg-c",
            "seq-3",
            "Tree",
            550,
            1050,
            "color_wash",
            energy_class=EnergyClass.LOW,
        ),
        _phrase(
            "p7",
            "pkg-d",
            "seq-4",
            "Tree",
            0,
            500,
            "bars",
            energy_class=EnergyClass.HIGH,
        ),
        _phrase(
            "p8",
            "pkg-d",
            "seq-4",
            "Tree",
            550,
            1050,
            "color_wash",
            energy_class=EnergyClass.LOW,
        ),
    )
    drop_assignments = tuple(
        _assignment(p.package_id, p.sequence_file_id, p.phrase_id, f"t-{p.effect_family}")
        for p in drop_phrases
    )
    content2, orch2 = _catalogs(drop_assignments, len(drop_phrases))

    catalog2 = miner.mine_temporal(
        phrases=drop_phrases,
        content_catalog=content2,
        orchestration_catalog=orch2,
    )
    bigrams2 = [m for m in catalog2.motifs if m.sequence_length == 2]
    assert any(m.pattern_name == "drop" for m in bigrams2), (
        f"Expected 'drop' pattern, got: {[m.pattern_name for m in bigrams2]}"
    )


# ---------------------------------------------------------------------------
# 6. Support filtering
# ---------------------------------------------------------------------------


def test_support_filtering() -> None:
    """Below-threshold motifs not in catalog."""
    # Only one sequence so distinct_sequence_count=1 < required 2
    phrases = (
        _phrase("p1", "pkg-a", "seq-1", "Tree", 0, 500, "color_wash"),
        _phrase("p2", "pkg-a", "seq-1", "Tree", 550, 1050, "bars"),
    )
    assignments = tuple(
        _assignment(p.package_id, p.sequence_file_id, p.phrase_id, f"t-{p.effect_family}")
        for p in phrases
    )
    content, orch = _catalogs(assignments, len(phrases))

    miner = MotifMiner(MotifMinerOptions(min_support_count=2, min_distinct_sequence_count=2))
    catalog = miner.mine_temporal(
        phrases=phrases,
        content_catalog=content,
        orchestration_catalog=orch,
    )
    assert catalog.total_temporal_motifs == 0
    assert len(catalog.motifs) == 0


# ---------------------------------------------------------------------------
# 7. Edge cases
# ---------------------------------------------------------------------------


def test_single_phrase_stream_no_motifs() -> None:
    """Single-phrase streams cannot form n-grams."""
    phrases = (
        _phrase("p1", "pkg-a", "seq-1", "Tree", 0, 500, "color_wash"),
        _phrase("p2", "pkg-b", "seq-2", "Tree", 0, 500, "bars"),
    )
    assignments = tuple(
        _assignment(p.package_id, p.sequence_file_id, p.phrase_id, f"t-{p.effect_family}")
        for p in phrases
    )
    content, orch = _catalogs(assignments, len(phrases))

    miner = MotifMiner(MotifMinerOptions(min_support_count=1, min_distinct_sequence_count=1))
    catalog = miner.mine_temporal(
        phrases=phrases,
        content_catalog=content,
        orchestration_catalog=orch,
    )
    assert catalog.total_temporal_motifs == 0


def test_empty_phrases_empty_catalog() -> None:
    """Empty input produces empty catalog."""
    content, orch = _catalogs((), 0)

    miner = MotifMiner()
    catalog = miner.mine_temporal(
        phrases=(),
        content_catalog=content,
        orchestration_catalog=orch,
    )
    assert isinstance(catalog, TemporalMotifCatalog)
    assert catalog.total_temporal_motifs == 0
    assert catalog.total_sequences == 0
    assert len(catalog.motifs) == 0
