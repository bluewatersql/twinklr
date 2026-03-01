"""Tests for V2 taxonomy expansion (6 new labels, 12 total)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.models.taxonomy import TaxonomyLabel
from twinklr.core.feature_engineering.taxonomy.classifier import (
    TaxonomyClassifier,
    TaxonomyClassifierOptions,
)

_V1_RULES = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "twinklr"
    / "core"
    / "feature_engineering"
    / "taxonomy"
    / "config"
    / "effect_function_v1.json"
)

_V2_RULES = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "twinklr"
    / "core"
    / "feature_engineering"
    / "taxonomy"
    / "config"
    / "effect_function_v2.json"
)

_ALL_V2_LABELS = {
    "rhythm_driver",
    "accent_hit",
    "sustainer",
    "transition",
    "texture_bed",
    "motion_driver",
    "fill_wash",
    "sparkle_overlay",
    "chase_pattern",
    "burst_impact",
    "layer_base",
    "layer_accent",
}

_EFFECT_PHRASE_FIELDS = {name for name in EffectPhrase.model_fields}


def _phrase(
    *,
    effect_family: str = "pattern_bars",
    motion_class: MotionClass = MotionClass.SWEEP,
    color_class: ColorClass = ColorClass.PALETTE,
    energy_class: EnergyClass = EnergyClass.HIGH,
    continuity_class: ContinuityClass = ContinuityClass.RHYTHMIC,
    spatial_class: SpatialClass = SpatialClass.MULTI_TARGET,
    duration_ms: int = 500,
    layer_index: int = 0,
    onset_sync_score: float | None = 0.9,
    blend_mode: str | None = None,
    mix: float | None = None,
    section_label: str | None = None,
) -> EffectPhrase:
    """Build a test phrase with sensible defaults and overridable fields."""
    return EffectPhrase(
        schema_version="v1.2.0",
        phrase_id="phrase-test",
        package_id="pkg-test",
        sequence_file_id="seq-test",
        effect_event_id="evt-test",
        effect_type="Bars",
        effect_family=effect_family,
        motion_class=motion_class,
        color_class=color_class,
        energy_class=energy_class,
        continuity_class=continuity_class,
        spatial_class=spatial_class,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=1.0,
        target_name="Tree",
        layer_index=layer_index,
        start_ms=0,
        end_ms=duration_ms,
        duration_ms=duration_ms,
        onset_sync_score=onset_sync_score,
        param_signature="abc",
        section_label=section_label,
    )


def _classify_one(phrase: EffectPhrase) -> set[str]:
    """Classify a single phrase and return the set of label value strings."""
    classifier = TaxonomyClassifier()
    rows = classifier.classify(
        phrases=(phrase,),
        package_id="pkg-test",
        sequence_file_id="seq-test",
    )
    assert len(rows) == 1
    return {label.value for label in rows[0].labels}


# ---------------------------------------------------------------------------
# Test 1: V2 rules file validates against expected schema (12 labels)
# ---------------------------------------------------------------------------


class TestV2RulesSchema:
    """Validate structure and completeness of the V2 rules file."""

    def test_v2_rules_file_has_12_labels(self) -> None:
        config = json.loads(_V2_RULES.read_text(encoding="utf-8"))
        labels = config["labels"]
        assert set(labels.keys()) == _ALL_V2_LABELS

    def test_each_label_has_required_keys(self) -> None:
        config = json.loads(_V2_RULES.read_text(encoding="utf-8"))
        for label_name, spec in config["labels"].items():
            assert "base" in spec, f"{label_name} missing 'base'"
            assert "min_confidence" in spec, f"{label_name} missing 'min_confidence'"
            assert "rules" in spec, f"{label_name} missing 'rules'"
            assert isinstance(spec["rules"], list), f"{label_name} rules not a list"

    def test_each_rule_has_required_keys(self) -> None:
        config = json.loads(_V2_RULES.read_text(encoding="utf-8"))
        for label_name, spec in config["labels"].items():
            for rule in spec["rules"]:
                assert "id" in rule, f"{label_name} rule missing 'id'"
                assert "weight" in rule, f"{label_name} rule missing 'weight'"
                assert "when" in rule, f"{label_name} rule missing 'when'"

    def test_when_fields_exist_on_effect_phrase(self) -> None:
        config = json.loads(_V2_RULES.read_text(encoding="utf-8"))
        for label_name, spec in config["labels"].items():
            for rule in spec["rules"]:
                for field_name in rule["when"]:
                    assert field_name in _EFFECT_PHRASE_FIELDS, (
                        f"{label_name} rule '{rule['id']}' references unknown field '{field_name}'"
                    )

    def test_schema_version_is_v2(self) -> None:
        config = json.loads(_V2_RULES.read_text(encoding="utf-8"))
        assert config["schema_version"] == "v2.0.0"
        assert config["classifier_version"] == "effect_function_v2"

    def test_all_label_names_in_taxonomy_enum(self) -> None:
        config = json.loads(_V2_RULES.read_text(encoding="utf-8"))
        enum_values = {member.value for member in TaxonomyLabel}
        for label_name in config["labels"]:
            assert label_name in enum_values, f"Label '{label_name}' not in TaxonomyLabel enum"


# ---------------------------------------------------------------------------
# Test 2: New labels fire on expected phrases
# ---------------------------------------------------------------------------


class TestNewLabelsFire:
    """Each new V2 label fires on a phrase with the expected features."""

    def test_fill_wash_fires(self) -> None:
        phrase = _phrase(
            effect_family="color_wash",
            motion_class=MotionClass.STATIC,
            spatial_class=SpatialClass.MULTI_TARGET,
            energy_class=EnergyClass.LOW,
            continuity_class=ContinuityClass.SUSTAINED,
            duration_ms=3000,
            onset_sync_score=None,
        )
        labels = _classify_one(phrase)
        assert "fill_wash" in labels

    def test_sparkle_overlay_fires(self) -> None:
        phrase = _phrase(
            effect_family="twinkle",
            motion_class=MotionClass.SPARKLE,
            energy_class=EnergyClass.LOW,
            continuity_class=ContinuityClass.SUSTAINED,
            duration_ms=2000,
            onset_sync_score=None,
        )
        labels = _classify_one(phrase)
        assert "sparkle_overlay" in labels

    def test_chase_pattern_fires(self) -> None:
        phrase = _phrase(
            effect_family="single_strand",
            motion_class=MotionClass.SWEEP,
            continuity_class=ContinuityClass.RHYTHMIC,
            duration_ms=800,
        )
        labels = _classify_one(phrase)
        assert "chase_pattern" in labels

    def test_burst_impact_fires(self) -> None:
        phrase = _phrase(
            energy_class=EnergyClass.BURST,
            duration_ms=200,
            continuity_class=ContinuityClass.RHYTHMIC,
        )
        labels = _classify_one(phrase)
        assert "burst_impact" in labels

    def test_layer_base_fires(self) -> None:
        phrase = _phrase(
            layer_index=0,
            energy_class=EnergyClass.LOW,
            continuity_class=ContinuityClass.SUSTAINED,
            duration_ms=3000,
            onset_sync_score=None,
        )
        labels = _classify_one(phrase)
        assert "layer_base" in labels

    def test_layer_accent_fires(self) -> None:
        phrase = _phrase(
            layer_index=2,
            energy_class=EnergyClass.MID,
            continuity_class=ContinuityClass.SUSTAINED,
            duration_ms=1500,
            onset_sync_score=None,
        )
        labels = _classify_one(phrase)
        assert "layer_accent" in labels


# ---------------------------------------------------------------------------
# Test 3: Existing V1 labels still fire identically
# ---------------------------------------------------------------------------


class TestV1LabelsIdentical:
    """V1 labels produce identical results under V2 rules."""

    def test_v1_labels_match_with_v2_rules(self) -> None:
        """V1 test fixtures produce the same V1-label results under both configs."""
        v1_classifier = TaxonomyClassifier(TaxonomyClassifierOptions(rules_path=_V1_RULES))
        v2_classifier = TaxonomyClassifier()

        v1_label_values = {
            "rhythm_driver",
            "accent_hit",
            "sustainer",
            "transition",
            "texture_bed",
            "motion_driver",
        }

        phrases = (
            _phrase(
                duration_ms=300,
                continuity_class=ContinuityClass.RHYTHMIC,
                energy_class=EnergyClass.BURST,
                onset_sync_score=0.95,
            ),
            _phrase(
                duration_ms=2400,
                continuity_class=ContinuityClass.SUSTAINED,
                energy_class=EnergyClass.LOW,
                onset_sync_score=0.3,
            ),
        )

        for phrase in phrases:
            v1_rows = v1_classifier.classify(
                phrases=(phrase,),
                package_id="pkg-test",
                sequence_file_id="seq-test",
            )
            v2_rows = v2_classifier.classify(
                phrases=(phrase,),
                package_id="pkg-test",
                sequence_file_id="seq-test",
            )
            assert len(v1_rows) == len(v2_rows) == 1

            v1_result = v1_rows[0]
            v2_result = v2_rows[0]

            # Filter V2 results to only V1 labels for comparison
            v2_v1_labels = tuple(
                label for label in v2_result.labels if label.value in v1_label_values
            )
            v2_v1_scores = tuple(
                score for score in v2_result.label_scores if score.label.value in v1_label_values
            )

            assert v1_result.labels == v2_v1_labels
            for v1_score, v2_score in zip(v1_result.label_scores, v2_v1_scores, strict=True):
                assert v1_score.label == v2_score.label
                assert v1_score.confidence == pytest.approx(v2_score.confidence)
                assert v1_score.rule_hits == v2_score.rule_hits


# ---------------------------------------------------------------------------
# Test 4: Multi-label assignment works
# ---------------------------------------------------------------------------


class TestMultiLabelAssignment:
    """A phrase can receive labels from both V1 and V2 label sets."""

    def test_rhythm_driver_and_chase_pattern(self) -> None:
        phrase = _phrase(
            effect_family="single_strand",
            motion_class=MotionClass.SWEEP,
            continuity_class=ContinuityClass.RHYTHMIC,
            duration_ms=800,
            onset_sync_score=0.8,
            spatial_class=SpatialClass.MULTI_TARGET,
        )
        labels = _classify_one(phrase)
        assert "rhythm_driver" in labels
        assert "chase_pattern" in labels

    def test_texture_bed_and_fill_wash(self) -> None:
        phrase = _phrase(
            effect_family="color_wash",
            motion_class=MotionClass.STATIC,
            color_class=ColorClass.PALETTE,
            energy_class=EnergyClass.LOW,
            continuity_class=ContinuityClass.SUSTAINED,
            spatial_class=SpatialClass.MULTI_TARGET,
            duration_ms=3000,
            onset_sync_score=None,
        )
        labels = _classify_one(phrase)
        assert "texture_bed" in labels
        assert "fill_wash" in labels


# ---------------------------------------------------------------------------
# Test 5: Backward compatibility with V1 rules path
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """V1 rules path still works when explicitly specified."""

    def test_v1_rules_path_still_works(self) -> None:
        classifier = TaxonomyClassifier(TaxonomyClassifierOptions(rules_path=_V1_RULES))
        phrase = _phrase(
            duration_ms=300,
            continuity_class=ContinuityClass.RHYTHMIC,
            energy_class=EnergyClass.BURST,
            onset_sync_score=0.95,
        )
        rows = classifier.classify(
            phrases=(phrase,),
            package_id="pkg-test",
            sequence_file_id="seq-test",
        )
        assert len(rows) == 1
        labels = {label.value for label in rows[0].labels}
        assert "accent_hit" in labels
        assert rows[0].classifier_version == "effect_function_v1"

    def test_v1_rules_produce_only_v1_labels(self) -> None:
        v1_label_values = {
            "rhythm_driver",
            "accent_hit",
            "sustainer",
            "transition",
            "texture_bed",
            "motion_driver",
        }
        classifier = TaxonomyClassifier(TaxonomyClassifierOptions(rules_path=_V1_RULES))
        phrase = _phrase(
            duration_ms=2400,
            continuity_class=ContinuityClass.SUSTAINED,
            energy_class=EnergyClass.LOW,
            spatial_class=SpatialClass.MULTI_TARGET,
            color_class=ColorClass.PALETTE,
            onset_sync_score=0.3,
        )
        rows = classifier.classify(
            phrases=(phrase,),
            package_id="pkg-test",
            sequence_file_id="seq-test",
        )
        labels = {label.value for label in rows[0].labels}
        assert labels <= v1_label_values
