"""Tests for feature validation module."""

from __future__ import annotations

from typing import Any

from twinklr.core.audio.validation.validator import validate_features


class TestValidateFeatures:
    """Tests for validate_features function."""

    def test_valid_features_no_warnings(self) -> None:
        """Valid features produce no warnings."""
        features: dict[str, Any] = {
            "tempo_bpm": 120.0,
            "beats_s": [0.5 * i for i in range(100)],  # 100 beats
            "key": {"key": "C", "mode": "major", "confidence": 0.8},
            "structure": {
                "sections": [
                    {"label": "verse", "start_s": 0, "end_s": 30},
                    {"label": "chorus", "start_s": 30, "end_s": 60},
                ]
            },
            "rhythm": {
                "downbeat_meta": {"phase_confidence": 0.7},
            },
        }
        warnings = validate_features(features)
        assert len(warnings) == 0

    def test_unusual_tempo_warning_low(self) -> None:
        """Tempo below 40 BPM generates warning."""
        features: dict[str, Any] = {
            "tempo_bpm": 30.0,  # Too slow
            "beats_s": [0.5 * i for i in range(100)],
            "key": {"confidence": 0.8},
            "structure": {"sections": [{"label": "verse"}]},
        }
        warnings = validate_features(features)
        assert any("Unusual tempo" in w for w in warnings)

    def test_unusual_tempo_warning_high(self) -> None:
        """Tempo above 240 BPM generates warning."""
        features: dict[str, Any] = {
            "tempo_bpm": 300.0,  # Too fast
            "beats_s": [0.5 * i for i in range(100)],
            "key": {"confidence": 0.8},
            "structure": {"sections": [{"label": "verse"}]},
        }
        warnings = validate_features(features)
        assert any("Unusual tempo" in w for w in warnings)

    def test_few_beats_warning(self) -> None:
        """Very few beats (< 10) generates warning."""
        features: dict[str, Any] = {
            "tempo_bpm": 120.0,
            "beats_s": [0.5 * i for i in range(5)],  # Only 5 beats
            "key": {"confidence": 0.8},
            "structure": {"sections": [{"label": "verse"}]},
        }
        warnings = validate_features(features)
        assert any("Very few beats" in w for w in warnings)

    def test_low_key_confidence_warning(self) -> None:
        """Low key detection confidence generates warning."""
        features: dict[str, Any] = {
            "tempo_bpm": 120.0,
            "beats_s": [0.5 * i for i in range(100)],
            "key": {"confidence": 0.1},  # Very low confidence
            "structure": {"sections": [{"label": "verse"}]},
        }
        warnings = validate_features(features)
        assert any("Low key detection confidence" in w for w in warnings)

    def test_irregular_beat_spacing_warning(self) -> None:
        """Highly irregular beat spacing generates warning."""
        features: dict[str, Any] = {
            "tempo_bpm": 120.0,
            # Irregular beats - large variation in intervals
            "beats_s": [0.0, 0.5, 0.6, 2.0, 2.1, 5.0, 5.5, 10.0, 10.1, 15.0, 16.0],
            "key": {"confidence": 0.8},
            "structure": {"sections": [{"label": "verse"}]},
        }
        warnings = validate_features(features)
        assert any("irregular beat spacing" in w for w in warnings)

    def test_no_sections_warning(self) -> None:
        """No sections detected generates warning."""
        features: dict[str, Any] = {
            "tempo_bpm": 120.0,
            "beats_s": [0.5 * i for i in range(100)],
            "key": {"confidence": 0.8},
            "structure": {"sections": []},  # No sections
        }
        warnings = validate_features(features)
        assert any("No sections detected" in w for w in warnings)

    def test_low_downbeat_confidence_warning(self) -> None:
        """Low downbeat phase confidence generates warning."""
        features: dict[str, Any] = {
            "tempo_bpm": 120.0,
            "beats_s": [0.5 * i for i in range(100)],
            "key": {"confidence": 0.8},
            "structure": {"sections": [{"label": "verse"}]},
            "rhythm": {
                "downbeat_meta": {"phase_confidence": 0.2},  # Low confidence
            },
        }
        warnings = validate_features(features)
        assert any("Low downbeat phase confidence" in w for w in warnings)

    def test_multiple_warnings(self) -> None:
        """Multiple issues generate multiple warnings."""
        features: dict[str, Any] = {
            "tempo_bpm": 30.0,  # Warning: unusual
            "beats_s": [0.0, 0.5, 1.0],  # Warning: few beats
            "key": {"confidence": 0.1},  # Warning: low confidence
            "structure": {"sections": []},  # Warning: no sections
            "rhythm": {
                "downbeat_meta": {"phase_confidence": 0.2},  # Warning: low confidence
            },
        }
        warnings = validate_features(features)
        assert len(warnings) >= 4  # At least 4 different warnings


class TestValidatorSchemaAlignment:
    """The checks must read the keys the analyzer actually writes."""

    @staticmethod
    def _well_formed() -> dict[str, Any]:
        """A feature dict shaped the way the full analysis path emits it."""
        return {
            "tempo_bpm": 120.0,
            "beats_s": [0.5 * i for i in range(100)],
            "harmonic": {"key": {"key": "C", "mode": "major", "confidence": 0.85}},
            "structure": {"sections": [{"label": "verse", "start_s": 0, "end_s": 30}]},
            "rhythm": {"downbeat_meta": {"phase": 0, "phase_confidence": 0.7}},
        }

    def test_validator_no_spurious_key_warning(self) -> None:
        """Key data under features["harmonic"] does not trip the low-confidence check.

        The check used to read a top-level "key" the analyzer never writes, so
        `key_conf` defaulted to 0 and "Low key detection confidence: 0.00" fired on
        every single run.
        """
        warnings = validate_features(self._well_formed())

        assert not any("Low key detection confidence" in w for w in warnings)
        assert warnings == []

    def test_low_confidence_under_harmonic_still_warns(self) -> None:
        """A genuinely low confidence in the current schema is still reported."""
        features = self._well_formed()
        features["harmonic"]["key"]["confidence"] = 0.1

        warnings = validate_features(features)

        assert any("Low key detection confidence: 0.10" in w for w in warnings)

    def test_missing_key_is_reported_as_missing(self) -> None:
        """Absent key data is named for what it is, not reported as 0.00 confidence."""
        features = self._well_formed()
        del features["harmonic"]

        warnings = validate_features(features)

        assert any("Key detection result missing" in w for w in warnings)
        assert not any("Low key detection confidence" in w for w in warnings)

    def test_short_audio_top_level_key_still_read(self) -> None:
        """The short-audio path writes a top-level "key"; that schema still works."""
        features = self._well_formed()
        del features["harmonic"]
        features["key"] = {"key": "C", "mode": "major", "confidence": 0.85}

        assert validate_features(features) == []

    def test_validator_downbeat_check_can_fire(self) -> None:
        """The downbeat check fires on the key the analyzer now writes."""
        features = self._well_formed()
        features["rhythm"]["downbeat_meta"]["phase_confidence"] = 0.11

        warnings = validate_features(features)

        assert any("Low downbeat phase confidence: 0.11" in w for w in warnings)
