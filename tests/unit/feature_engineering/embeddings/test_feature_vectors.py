"""Tests for SequenceFeatureVectorBuilder."""

from __future__ import annotations

from twinklr.core.feature_engineering.embeddings.feature_vectors import (
    SequenceFeatureVectorBuilder,
)
from twinklr.core.feature_engineering.models.bundle import (
    AudioDiscoveryResult,
    FeatureBundle,
)
from twinklr.core.feature_engineering.models.phrases import EffectPhrase
from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
    TargetRoleAssignment,
)


def _make_phrase(phrase_id: str, effect_family: str = "CHASE", **kwargs: object) -> EffectPhrase:
    defaults: dict[str, object] = {
        "schema_version": "1.0",
        "phrase_id": phrase_id,
        "package_id": "pkg",
        "sequence_file_id": "seq",
        "effect_event_id": f"evt_{phrase_id}",
        "effect_type": "chase",
        "effect_family": effect_family,
        "motion_class": "sweep",
        "color_class": "mono",
        "energy_class": "mid",
        "continuity_class": "sustained",
        "spatial_class": "single_target",
        "source": "effect_type_map",
        "map_confidence": 0.9,
        "target_name": "Arch1",
        "layer_index": 0,
        "start_ms": 0,
        "end_ms": 1000,
        "duration_ms": 1000,
        "param_signature": "chase::sweep",
    }
    defaults.update(kwargs)
    return EffectPhrase(**defaults)  # type: ignore[arg-type]


def _make_bundle() -> FeatureBundle:
    return FeatureBundle(
        schema_version="1.0",
        source_profile_path="/test",
        package_id="pkg",
        sequence_file_id="seq",
        sequence_sha256="abc123",
        song="Test",
        artist="Test",
        audio=AudioDiscoveryResult(audio_path=None, audio_status="missing"),
    )


def _make_taxonomy_record(phrase_id: str) -> PhraseTaxonomyRecord:
    return PhraseTaxonomyRecord(
        schema_version="1.0",
        classifier_version="1.0",
        phrase_id=phrase_id,
        package_id="pkg",
        sequence_file_id="seq",
        effect_event_id=f"evt_{phrase_id}",
    )


def _make_target_role(target_id: str, role: str = "lead") -> TargetRoleAssignment:
    return TargetRoleAssignment(
        schema_version="1.0",
        role_engine_version="1.0",
        package_id="pkg",
        sequence_file_id="seq",
        target_id=target_id,
        target_name=f"Target_{target_id}",
        target_kind="fixture",
        role=role,
        role_confidence=0.9,
        event_count=5,
        active_duration_ms=3000,
        role_binding_key=f"pkg::seq::{target_id}",
    )


class TestSequenceFeatureVectorBuilder:
    def setup_method(self) -> None:
        self.builder = SequenceFeatureVectorBuilder()
        self.bundle = _make_bundle()
        self.empty_taxonomy: tuple[PhraseTaxonomyRecord, ...] = ()
        self.empty_roles: tuple[TargetRoleAssignment, ...] = ()

    def test_build_from_valid_phrases(self) -> None:
        """Build from 3 phrases with known classes produces valid vector."""
        phrases = (
            _make_phrase("p1", effect_family="CHASE"),
            _make_phrase("p2", effect_family="STROBE", motion_class="pulse"),
            _make_phrase("p3", effect_family="COLOR", energy_class="high"),
        )
        taxonomy = tuple(_make_taxonomy_record(f"p{i}") for i in range(1, 4))
        vec = self.builder.build(phrases, taxonomy, self.empty_roles, self.bundle)

        assert vec.dimensionality > 0
        assert len(vec.feature_names) == len(vec.values)
        assert vec.dimensionality == len(vec.values)
        assert vec.package_id == "pkg"
        assert vec.sequence_file_id == "seq"

    def test_feature_names_match_values_length(self) -> None:
        """Feature names and values are always the same length."""
        phrases = (_make_phrase("p1"),)
        vec = self.builder.build(phrases, self.empty_taxonomy, self.empty_roles, self.bundle)
        assert len(vec.feature_names) == len(vec.values)

    def test_empty_phrases_zero_filled(self) -> None:
        """Empty phrase tuple produces zero-filled temporal and frequency slots."""
        vec = self.builder.build((), self.empty_taxonomy, self.empty_roles, self.bundle)

        idx = {name: i for i, name in enumerate(vec.feature_names)}
        assert vec.values[idx["duration_mean"]] == 0.0
        assert vec.values[idx["duration_std"]] == 0.0
        assert vec.values[idx["duration_min"]] == 0.0
        assert vec.values[idx["duration_max"]] == 0.0
        assert vec.values[idx["phrase_count"]] == 0.0
        assert vec.values[idx["total_active_ms"]] == 0.0
        # All family frequencies should be zero when no phrases
        for fam in SequenceFeatureVectorBuilder._KNOWN_FAMILIES:
            assert vec.values[idx[f"family_freq_{fam}"]] == 0.0

    def test_consistent_dimensionality(self) -> None:
        """Two different phrase sets produce the same dimensionality."""
        phrases_a = (_make_phrase("p1", effect_family="CHASE"),)
        phrases_b = (
            _make_phrase("p2", effect_family="STROBE"),
            _make_phrase("p3", effect_family="BARS"),
        )
        vec_a = self.builder.build(phrases_a, self.empty_taxonomy, self.empty_roles, self.bundle)
        vec_b = self.builder.build(phrases_b, self.empty_taxonomy, self.empty_roles, self.bundle)

        assert vec_a.dimensionality == vec_b.dimensionality

    def test_known_phrase_distribution_correct(self) -> None:
        """2 CHASE + 1 STATIC phrases produce correct family frequency ratios."""
        phrases = (
            _make_phrase("p1", effect_family="CHASE"),
            _make_phrase("p2", effect_family="CHASE"),
            _make_phrase("p3", effect_family="STATIC"),
        )
        vec = self.builder.build(phrases, self.empty_taxonomy, self.empty_roles, self.bundle)
        idx = {name: i for i, name in enumerate(vec.feature_names)}

        chase_freq = vec.values[idx["family_freq_CHASE"]]
        static_freq = vec.values[idx["family_freq_STATIC"]]

        assert abs(chase_freq - 2 / 3) < 1e-9
        assert abs(static_freq - 1 / 3) < 1e-9
