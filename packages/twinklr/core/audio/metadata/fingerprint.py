"""Chromaprint fingerprinting (Phase 3).

Compute audio fingerprints using the fpcalc binary from chromaprint.
"""

import logging
import re
import subprocess

logger = logging.getLogger(__name__)


class ChromaprintError(RuntimeError):
    """Chromaprint computation failed."""

    pass


def compute_chromaprint_fingerprint(audio_path: str, *, timeout_s: float) -> tuple[str, float]:
    """Compute chromaprint fingerprint using fpcalc binary.

    Args:
        audio_path: Path to audio file
        timeout_s: Timeout for fpcalc subprocess (seconds)

    Returns:
        Tuple of (fingerprint_string, duration_seconds)

    Raises:
        ChromaprintError: If fpcalc not found or computation fails

    Notes:
        Requires chromaprint binary (fpcalc) to be installed:
        - macOS: brew install chromaprint
        - Ubuntu: apt-get install libchromaprint-tools
        - Windows: Download from https://acoustid.org/chromaprint
    """
    try:
        # Run fpcalc binary
        result = subprocess.run(
            ["fpcalc", "-json", audio_path],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,  # We'll check returncode manually
        )

        # Check for errors
        if result.returncode != 0:
            raise ChromaprintError(
                f"fpcalc failed with exit code {result.returncode}: {result.stderr}"
            )

        # Parse output
        # fpcalc outputs lines like:
        # DURATION=180.50
        # FINGERPRINT=AQADtEmRJkqRJEqSJEqRJEqS
        output = result.stdout

        # Extract duration
        duration_match = re.search(r"DURATION\s*=\s*(\S+)", output)
        if not duration_match:
            raise ChromaprintError("fpcalc output missing DURATION field")

        try:
            duration = float(duration_match.group(1))
        except ValueError as e:
            raise ChromaprintError(f"Invalid duration in fpcalc output: {e}") from e

        # Extract fingerprint
        fingerprint_match = re.search(r"FINGERPRINT\s*=\s*(\S+)", output)
        if not fingerprint_match:
            raise ChromaprintError("fpcalc output missing FINGERPRINT field")

        fingerprint = fingerprint_match.group(1)

        logger.debug(f"Computed chromaprint for {audio_path}: duration={duration}s")

        return fingerprint, duration

    except FileNotFoundError as e:
        raise ChromaprintError(
            "fpcalc binary not found. Install chromaprint: "
            "brew install chromaprint (macOS) or "
            "apt-get install libchromaprint-tools (Ubuntu)"
        ) from e

    except subprocess.TimeoutExpired as e:
        raise ChromaprintError(f"fpcalc timeout after {timeout_s}s for {audio_path}") from e

    except ChromaprintError:
        # Re-raise our own errors
        raise

    except Exception as e:
        raise ChromaprintError(f"Unexpected error computing chromaprint: {e}") from e
