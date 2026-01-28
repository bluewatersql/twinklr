"""WhisperX service for lyrics transcription and alignment.

This module provides a service wrapper for WhisperX ML model operations:
- Transcribe: Generate lyrics from audio (no reference needed)
- Align: Align existing lyrics to audio timing

The service follows the Protocol pattern for testability and extensibility.

Classes:
    WhisperXService: Protocol defining the service interface
    WhisperXImpl: Real implementation using whisperx library

Functions:
    compute_mismatch_ratio: Calculate token-level edit distance ratio
"""

import logging
import re
from typing import Protocol

from Levenshtein import distance as levenshtein_distance

from blinkb0t.core.audio.lyrics.whisperx_models import (
    WhisperXAlignResult,
    WhisperXConfig,
    WhisperXTranscribeResult,
)
from blinkb0t.core.audio.models.lyrics import LyricWord

logger = logging.getLogger(__name__)


def compute_mismatch_ratio(reference: str, aligned: str) -> float:
    """Compute token-level mismatch ratio between reference and aligned text.

    Uses Levenshtein distance normalized by the length of the longer string.
    Text is normalized (lowercase, punctuation removed, whitespace normalized).

    Args:
        reference: Reference lyrics text
        aligned: Aligned lyrics text from WhisperX

    Returns:
        Mismatch ratio from 0.0 (perfect match) to 1.0 (completely different)

    Example:
        >>> compute_mismatch_ratio("hello world", "hello world")
        0.0
        >>> compute_mismatch_ratio("hello world", "hello earth")
        0.36  # Approximately
    """

    def normalize(text: str) -> str:
        """Normalize text for comparison."""
        # Lowercase
        text = text.lower()
        # Remove punctuation
        text = re.sub(r"[^\w\s]", "", text)
        # Normalize whitespace
        text = " ".join(text.split())
        return text

    ref_norm = normalize(reference)
    aligned_norm = normalize(aligned)

    # Handle empty strings
    if not ref_norm and not aligned_norm:
        return 0.0
    if not ref_norm or not aligned_norm:
        return 1.0

    # Compute Levenshtein distance
    dist = levenshtein_distance(ref_norm, aligned_norm)
    max_len = max(len(ref_norm), len(aligned_norm))

    # Normalize to 0.0-1.0 range
    ratio = dist / max_len if max_len > 0 else 0.0

    return min(1.0, max(0.0, ratio))


class WhisperXService(Protocol):
    """Protocol for WhisperX service operations.

    Defines the interface for transcription and alignment operations.
    Implementations can be real (using whisperx library) or mock (for testing).
    """

    def align(
        self, audio_path: str, lyrics_text: str, config: WhisperXConfig
    ) -> WhisperXAlignResult:
        """Align existing lyrics to audio timing.

        Use when lyrics text exists but lacks word-level timing.
        Faster and more accurate than transcribe when reference is good.

        Args:
            audio_path: Path to audio file
            lyrics_text: Reference lyrics text to align
            config: WhisperX configuration

        Returns:
            WhisperXAlignResult with word-level timings and mismatch ratio

        Raises:
            ImportError: If whisperx not installed
            FileNotFoundError: If audio file not found
            RuntimeError: If alignment fails
        """
        ...

    def transcribe(
        self, audio_path: str, config: WhisperXConfig
    ) -> WhisperXTranscribeResult:
        """Transcribe lyrics from audio (no reference needed).

        Use when no lyrics text exists. Generates lyrics from audio.

        Args:
            audio_path: Path to audio file
            config: WhisperX configuration

        Returns:
            WhisperXTranscribeResult with text and word-level timings

        Raises:
            ImportError: If whisperx not installed
            FileNotFoundError: If audio file not found
            RuntimeError: If transcription fails
        """
        ...


class WhisperXImpl(WhisperXService):
    """Real WhisperX implementation using whisperx library.

    Requires whisperx to be installed (`uv sync --extra ml`).
    Models are downloaded on first use.

    Example:
        >>> service = WhisperXImpl()
        >>> config = WhisperXConfig(device="cpu", model="base")
        >>> result = service.transcribe("song.mp3", config)
        >>> len(result.words)
        150
    """

    def align(
        self, audio_path: str, lyrics_text: str, config: WhisperXConfig
    ) -> WhisperXAlignResult:
        """Align existing lyrics to audio timing using WhisperX.

        Downloads model on first use. Supports GPU (cuda/mps) and CPU.

        Args:
            audio_path: Path to audio file
            lyrics_text: Reference lyrics text to align
            config: WhisperX configuration

        Returns:
            WhisperXAlignResult with word timings and mismatch ratio

        Raises:
            ImportError: If whisperx not installed
            FileNotFoundError: If audio file not found
            RuntimeError: If alignment fails
        """
        try:
            import whisperx  # type: ignore
        except ImportError as e:
            raise ImportError(
                "whisperx not installed. Install with: uv sync --extra ml"
            ) from e

        logger.info(
            f"WhisperX align: {audio_path} (model={config.model}, device={config.device})"
        )

        # Load audio
        audio = whisperx.load_audio(audio_path)

        # Load alignment model
        align_model, metadata = whisperx.load_align_model(
            language_code=config.language or "en", device=config.device
        )

        # Perform alignment
        result = whisperx.align(
            transcript=[{"text": lyrics_text}],
            model=align_model,
            align_model_metadata=metadata,
            audio=audio,
            device=config.device,
            return_char_alignments=config.return_char_alignments,
        )

        # Extract words
        words: list[LyricWord] = []
        aligned_text_parts: list[str] = []

        for segment in result.get("segments", []):
            aligned_text_parts.append(segment.get("text", ""))
            for word_dict in segment.get("words", []):
                word_text = word_dict.get("word", "").strip()
                start_s = word_dict.get("start", 0.0)
                end_s = word_dict.get("end", 0.0)

                if word_text:
                    words.append(
                        LyricWord(
                            text=word_text,
                            start_ms=int(start_s * 1000),
                            end_ms=int(end_s * 1000),
                        )
                    )

        # Compute mismatch ratio
        aligned_text = " ".join(aligned_text_parts)
        mismatch_ratio = compute_mismatch_ratio(lyrics_text, aligned_text)

        logger.info(
            f"WhisperX align complete: {len(words)} words, "
            f"mismatch={mismatch_ratio:.3f}"
        )

        return WhisperXAlignResult(
            words=words,
            mismatch_ratio=mismatch_ratio,
            metadata={
                "model": config.model,
                "device": config.device,
                "language": config.language or "en",
                "aligned_text": aligned_text,
            },
        )

    def transcribe(
        self, audio_path: str, config: WhisperXConfig
    ) -> WhisperXTranscribeResult:
        """Transcribe lyrics from audio using WhisperX.

        Downloads model on first use. Supports GPU (cuda/mps) and CPU.

        Args:
            audio_path: Path to audio file
            config: WhisperX configuration

        Returns:
            WhisperXTranscribeResult with text and word timings

        Raises:
            ImportError: If whisperx not installed
            FileNotFoundError: If audio file not found
            RuntimeError: If transcription fails
        """
        try:
            import whisperx  # type: ignore
        except ImportError as e:
            raise ImportError(
                "whisperx not installed. Install with: uv sync --extra ml"
            ) from e

        logger.info(
            f"WhisperX transcribe: {audio_path} (model={config.model}, device={config.device})"
        )

        # Load model and audio
        compute_type = "float32" if config.device == "cpu" else "float16"
        model = whisperx.load_model(
            config.model, device=config.device, compute_type=compute_type
        )
        audio = whisperx.load_audio(audio_path)

        # Transcribe
        result = model.transcribe(
            audio, batch_size=config.batch_size, language=config.language
        )

        # Extract text and words
        text_parts: list[str] = []
        words: list[LyricWord] = []

        for segment in result.get("segments", []):
            text_parts.append(segment.get("text", ""))
            for word_dict in segment.get("words", []):
                word_text = word_dict.get("word", "").strip()
                start_s = word_dict.get("start", 0.0)
                end_s = word_dict.get("end", 0.0)

                if word_text:
                    words.append(
                        LyricWord(
                            text=word_text,
                            start_ms=int(start_s * 1000),
                            end_ms=int(end_s * 1000),
                        )
                    )

        text = " ".join(text_parts)
        detected_language = result.get("language", config.language or "unknown")

        logger.info(
            f"WhisperX transcribe complete: {len(words)} words, "
            f"language={detected_language}"
        )

        return WhisperXTranscribeResult(
            text=text,
            words=words,
            metadata={
                "model": config.model,
                "device": config.device,
                "language": detected_language,
            },
        )
