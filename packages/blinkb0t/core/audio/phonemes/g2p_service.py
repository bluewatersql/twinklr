"""G2P (grapheme-to-phoneme) service (Phase 6).

Converts text to phonemes using g2p_en library.

Functions:
    word_to_phonemes: Convert word to phoneme list
    normalize_phoneme: Strip stress markers from phoneme

Classes:
    G2PConfig: Configuration for G2P conversion
    G2PService: Protocol for G2P service
    G2PImpl: Implementation using g2p_en

Example:
    >>> from blinkb0t.core.audio.phonemes.g2p_service import word_to_phonemes
    >>> phonemes = word_to_phonemes("hello")
    >>> phonemes
    ['HH', 'EH', 'L', 'OW']
"""

import logging
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

# Lazy import g2p_en (optional dependency)
try:
    from g2p_en import G2p as _G2p

    _G2P_AVAILABLE = True
except ImportError:
    _G2p = None  # type: ignore[assignment, misc]
    _G2P_AVAILABLE = False


class G2PConfig(BaseModel):
    """Configuration for G2P conversion.

    Attributes:
        strip_stress: Whether to strip stress markers (0, 1, 2) from phonemes
        filter_punctuation: Whether to filter out punctuation from results

    Example:
        >>> config = G2PConfig(strip_stress=True)
        >>> config.strip_stress
        True
    """

    model_config = ConfigDict(extra="forbid")

    strip_stress: bool = Field(
        default=True, description="Strip stress markers from phonemes"
    )
    filter_punctuation: bool = Field(
        default=True, description="Filter out punctuation from results"
    )


def normalize_phoneme(phoneme: str) -> str:
    """Strip stress markers from phoneme.

    Removes digits (0, 1, 2) that indicate stress level in ARPAbet.

    Args:
        phoneme: Phoneme with stress markers (e.g., "AH0", "IY1")

    Returns:
        Phoneme without stress markers (e.g., "AH", "IY")

    Example:
        >>> normalize_phoneme("AH0")
        'AH'
        >>> normalize_phoneme("IY1")
        'IY'
        >>> normalize_phoneme("M")
        'M'
    """
    return "".join(ch for ch in phoneme if not ch.isdigit())


def word_to_phonemes(word: str, *, config: G2PConfig | None = None) -> list[str]:
    """Convert word to list of phonemes.

    Uses g2p_en library to convert text to ARPAbet phonemes.

    Args:
        word: Word to convert
        config: Optional configuration

    Returns:
        List of phonemes (ARPAbet format)

    Raises:
        ImportError: If g2p_en library not installed

    Example:
        >>> word_to_phonemes("hello")
        ['HH', 'EH', 'L', 'OW']
        >>> word_to_phonemes("HELLO")
        ['HH', 'EH', 'L', 'OW']
    """
    if not _G2P_AVAILABLE:
        raise ImportError(
            "g2p_en library not installed. "
            "Install with: pip install g2p-en"
        )

    if config is None:
        config = G2PConfig()

    # Handle empty/whitespace
    word = word.strip()
    if not word:
        return []

    # Convert to phonemes
    g2p = _G2p()
    phonemes = g2p(word)

    # Filter out non-phoneme tokens (spaces, punctuation)
    if config.filter_punctuation:
        phonemes = [p for p in phonemes if any(ch.isalpha() for ch in p)]

    # Strip stress markers if configured
    if config.strip_stress:
        phonemes = [normalize_phoneme(p) for p in phonemes]

    return phonemes


class G2PService(Protocol):
    """Protocol for G2P service.

    Defines the interface for grapheme-to-phoneme conversion.
    """

    def convert(self, text: str, *, config: G2PConfig) -> list[str]:
        """Convert text to list of phonemes.

        Args:
            text: Text to convert
            config: G2P configuration

        Returns:
            List of phonemes (ARPAbet format)

        Raises:
            ImportError: If g2p_en not installed
        """
        ...


class G2PImpl:
    """G2P service implementation using g2p_en.

    Example:
        >>> service = G2PImpl()
        >>> config = G2PConfig()
        >>> phonemes = service.convert("hello", config=config)
        >>> len(phonemes)
        4
    """

    def convert(self, text: str, *, config: G2PConfig) -> list[str]:
        """Convert text to list of phonemes.

        Args:
            text: Text to convert
            config: G2P configuration

        Returns:
            List of phonemes (ARPAbet format)

        Raises:
            ImportError: If g2p_en not installed
        """
        return word_to_phonemes(text, config=config)
