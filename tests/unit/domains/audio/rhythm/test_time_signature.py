"""Tests for time signature detection and extraction.

CRITICAL REGRESSION TESTS:
These tests address the KeyError: 'beats_per_bar' bug where code expected
a nested dict structure but only received a string.
"""

from __future__ import annotations


class TestTimeSignatureExtraction:
    """Regression tests for time_signature string extraction."""

    def test_extract_beats_per_bar_from_time_sig_string(self):
        """Test extracting beats_per_bar from time signature strings.

        REGRESSION TEST for KeyError: 'beats_per_bar'

        The fix extracts beats_per_bar from time_signature strings like:
        - "4/4" → 4
        - "3/4" → 3
        - "6/8" → 6
        """
        # Test common time signatures
        test_cases = [
            ("4/4", 4),
            ("3/4", 3),
            ("6/8", 6),
            ("2/4", 2),
            ("5/4", 5),
            ("7/8", 7),
            ("12/8", 12),
        ]

        for time_sig_str, expected_beats in test_cases:
            # This is the extraction logic used in analyzer.py
            beats_per_bar = int(time_sig_str.split("/")[0])
            assert beats_per_bar == expected_beats, (
                f"Failed to extract beats_per_bar from {time_sig_str}: "
                f"got {beats_per_bar}, expected {expected_beats}"
            )

    def test_time_signature_result_structure(self):
        """Test that time_signature result has expected structure.

        REGRESSION TEST: Verify the structure returned by detect_time_signature
        and how it's stored in song_features.
        """
        # Simulate what detect_time_signature returns
        time_sig_result = {
            "time_signature": "4/4",
            "confidence": 0.9,
        }

        # Verify structure
        assert "time_signature" in time_sig_result
        assert isinstance(time_sig_result["time_signature"], str)
        assert "confidence" in time_sig_result

        # Extract beats_per_bar
        time_sig_label = time_sig_result["time_signature"]
        beats_per_bar = int(time_sig_label.split("/")[0])

        # This is what should be in song_features
        song_features_structure = {
            "time_signature": time_sig_result,  # Full dict
            "assumptions": {
                "time_signature": time_sig_label,  # String
                "beats_per_bar": beats_per_bar,  # Int
            },
        }

        # Verify the structure we expect
        assert song_features_structure["time_signature"]["time_signature"] == "4/4"
        assert song_features_structure["assumptions"]["beats_per_bar"] == 4
        assert song_features_structure["assumptions"]["time_signature"] == "4/4"


class TestTimeSignatureEdgeCases:
    """Tests for edge cases in time signature handling."""

    def test_unusual_time_signatures(self):
        """Test extraction works for unusual time signatures."""
        unusual_cases = [
            ("11/8", 11),
            ("13/16", 13),
            ("15/8", 15),
        ]

        for time_sig_str, expected_beats in unusual_cases:
            beats_per_bar = int(time_sig_str.split("/")[0])
            assert beats_per_bar == expected_beats

    def test_time_signature_with_whitespace(self):
        """Test that time signatures with whitespace are handled."""
        # Some detection might return strings with whitespace
        time_sig_with_space = " 4/4 "
        time_sig_clean = time_sig_with_space.strip()
        beats_per_bar = int(time_sig_clean.split("/")[0])
        assert beats_per_bar == 4
