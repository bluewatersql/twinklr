"""Tests for chromaprint fingerprinting (Phase 3).

Testing chromaprint computation, duration bucketing, and error handling.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from twinklr.core.audio.metadata.fingerprint import (
    ChromaprintError,
    compute_chromaprint_fingerprint,
)


class TestComputeChromaprintFingerprint:
    """Test chromaprint fingerprint computation."""

    def test_successful_fingerprint(self):
        """Successful chromaprint computation."""
        # Mock fpcalc output
        mock_output = """
DURATION=180.50
FINGERPRINT=AQADtEmRJkqRJEqSJEqRJEqS
"""

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            fingerprint, duration = compute_chromaprint_fingerprint(
                "/test/audio.mp3",
                timeout_s=30.0,
            )

            assert fingerprint == "AQADtEmRJkqRJEqSJEqRJEqS"
            assert duration == 180.50

    def test_fingerprint_with_bucketed_duration(self):
        """Duration is returned as-is (bucketing done by caller)."""
        mock_output = "DURATION=123.456\nFINGERPRINT=ABC123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            _, duration = compute_chromaprint_fingerprint("/test/audio.mp3", timeout_s=30.0)

            # Duration is exact, not bucketed
            assert duration == 123.456

    def test_fpcalc_not_found(self):
        """fpcalc binary not found raises ChromaprintError."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("fpcalc not found")

            with pytest.raises(ChromaprintError) as exc_info:
                compute_chromaprint_fingerprint("/test/audio.mp3", timeout_s=30.0)

            assert "fpcalc binary not found" in str(exc_info.value).lower()

    def test_fpcalc_timeout(self):
        """fpcalc timeout raises ChromaprintError."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("fpcalc", 30.0)

            with pytest.raises(ChromaprintError) as exc_info:
                compute_chromaprint_fingerprint("/test/audio.mp3", timeout_s=30.0)

            assert "timeout" in str(exc_info.value).lower()

    def test_fpcalc_non_zero_exit(self):
        """fpcalc non-zero exit code raises ChromaprintError."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: file not found",
            )

            with pytest.raises(ChromaprintError) as exc_info:
                compute_chromaprint_fingerprint("/test/audio.mp3", timeout_s=30.0)

            assert "failed with exit code 1" in str(exc_info.value).lower()

    def test_fpcalc_missing_duration(self):
        """fpcalc output missing DURATION raises ChromaprintError."""
        mock_output = "FINGERPRINT=ABC123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            with pytest.raises(ChromaprintError) as exc_info:
                compute_chromaprint_fingerprint("/test/audio.mp3", timeout_s=30.0)

            assert "duration" in str(exc_info.value).lower()

    def test_fpcalc_missing_fingerprint(self):
        """fpcalc output missing FINGERPRINT raises ChromaprintError."""
        mock_output = "DURATION=180.0"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            with pytest.raises(ChromaprintError) as exc_info:
                compute_chromaprint_fingerprint("/test/audio.mp3", timeout_s=30.0)

            assert "fingerprint" in str(exc_info.value).lower()

    def test_fpcalc_invalid_duration(self):
        """fpcalc output with invalid duration raises ChromaprintError."""
        mock_output = "DURATION=not_a_number\nFINGERPRINT=ABC123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            with pytest.raises(ChromaprintError) as exc_info:
                compute_chromaprint_fingerprint("/test/audio.mp3", timeout_s=30.0)

            assert "invalid duration" in str(exc_info.value).lower()

    def test_fpcalc_command_called_correctly(self):
        """fpcalc is called with correct arguments."""
        mock_output = "DURATION=180.0\nFINGERPRINT=ABC123"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            compute_chromaprint_fingerprint("/path/to/audio.mp3", timeout_s=45.0)

            # Verify subprocess.run was called correctly
            mock_run.assert_called_once()
            call_args = mock_run.call_args

            # Check command
            assert call_args[0][0] == ["fpcalc", "-json", "/path/to/audio.mp3"]

            # Check other arguments
            assert call_args[1]["capture_output"] is True
            assert call_args[1]["text"] is True
            assert call_args[1]["timeout"] == 45.0

    def test_fpcalc_handles_whitespace_in_output(self):
        """fpcalc output with extra whitespace is handled."""
        mock_output = """

DURATION = 180.0
FINGERPRINT = ABC123

"""

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            fingerprint, duration = compute_chromaprint_fingerprint(
                "/test/audio.mp3",
                timeout_s=30.0,
            )

            assert fingerprint == "ABC123"
            assert duration == 180.0

    def test_fpcalc_short_duration(self):
        """Short audio files (< 1s) work correctly."""
        mock_output = "DURATION=0.5\nFINGERPRINT=SHORT"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            fingerprint, duration = compute_chromaprint_fingerprint(
                "/test/short.mp3",
                timeout_s=30.0,
            )

            assert fingerprint == "SHORT"
            assert duration == 0.5

    def test_fpcalc_long_duration(self):
        """Long audio files (> 1 hour) work correctly."""
        mock_output = "DURATION=3725.8\nFINGERPRINT=LONG"  # ~62 minutes

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr="",
            )

            fingerprint, duration = compute_chromaprint_fingerprint(
                "/test/long.mp3",
                timeout_s=60.0,
            )

            assert fingerprint == "LONG"
            assert duration == 3725.8


class TestChromaprintError:
    """Test ChromaprintError exception."""

    def test_chromaprint_error_is_runtime_error(self):
        """ChromaprintError is a RuntimeError subclass."""
        error = ChromaprintError("test error")

        assert isinstance(error, RuntimeError)
        assert str(error) == "test error"

    def test_chromaprint_error_can_be_raised(self):
        """ChromaprintError can be raised and caught."""
        with pytest.raises(ChromaprintError) as exc_info:
            raise ChromaprintError("Chromaprint computation failed")

        assert "Chromaprint computation failed" in str(exc_info.value)
