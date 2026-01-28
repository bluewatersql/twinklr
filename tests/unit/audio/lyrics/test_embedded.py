"""Tests for embedded lyrics extraction (Phase 4).

Testing LRC file parsing, SYLT/USLT tag extraction, and timestamp normalization.
"""

from unittest.mock import MagicMock, patch

from blinkb0t.core.audio.lyrics.embedded import (
    extract_embedded_lyrics,
    parse_lrc_content,
    parse_lrc_timestamp,
)


class TestParseLrcTimestamp:
    """Test LRC timestamp parsing."""

    def test_parse_standard_timestamp(self):
        """Parse standard [mm:ss.xx] format."""
        ms = parse_lrc_timestamp("[01:23.45]")
        assert ms == (1 * 60 + 23) * 1000 + 450

    def test_parse_short_centiseconds(self):
        """Parse [mm:ss.x] format."""
        ms = parse_lrc_timestamp("[01:23.4]")
        assert ms == (1 * 60 + 23) * 1000 + 400

    def test_parse_no_centiseconds(self):
        """Parse [mm:ss] format."""
        ms = parse_lrc_timestamp("[01:23]")
        assert ms == (1 * 60 + 23) * 1000

    def test_parse_zero_timestamp(self):
        """Parse [00:00.00] format."""
        ms = parse_lrc_timestamp("[00:00.00]")
        assert ms == 0

    def test_parse_long_duration(self):
        """Parse timestamps over 10 minutes."""
        ms = parse_lrc_timestamp("[12:34.56]")
        assert ms == (12 * 60 + 34) * 1000 + 560

    def test_invalid_timestamp_returns_none(self):
        """Invalid timestamps return None."""
        assert parse_lrc_timestamp("[invalid]") is None
        assert parse_lrc_timestamp("[1:2:3]") is None
        assert parse_lrc_timestamp("01:23.45") is None  # No brackets


class TestParseLrcContent:
    """Test LRC content parsing."""

    def test_parse_simple_lyrics(self):
        """Parse simple LRC with one timestamp per line."""
        content = """[00:12.00]First line
[00:17.20]Second line
[00:23.00]Third line"""

        phrases = parse_lrc_content(content)

        assert len(phrases) == 3
        assert phrases[0].text == "First line"
        assert phrases[0].start_ms == 12000
        assert phrases[1].text == "Second line"
        assert phrases[1].start_ms == 17200

    def test_parse_with_metadata(self):
        """Parse LRC with metadata tags (ar, ti, al, etc)."""
        content = """[ar:Artist Name]
[ti:Song Title]
[al:Album Name]
[00:12.00]First line
[00:17.20]Second line"""

        phrases = parse_lrc_content(content)

        # Metadata lines should be skipped
        assert len(phrases) == 2
        assert phrases[0].text == "First line"

    def test_parse_with_offset(self):
        """Parse LRC with [offset:+/-ms] tag."""
        content = """[offset:+500]
[00:12.00]First line
[00:17.20]Second line"""

        phrases = parse_lrc_content(content)

        # Offset should be applied to all timestamps
        assert phrases[0].start_ms == 12000 + 500
        assert phrases[1].start_ms == 17200 + 500

    def test_parse_negative_offset(self):
        """Parse LRC with negative offset."""
        content = """[offset:-200]
[00:12.00]First line"""

        phrases = parse_lrc_content(content)

        assert phrases[0].start_ms == 12000 - 200

    def test_parse_multiple_timestamps_per_line(self):
        """Parse line with multiple timestamps (chorus repetition)."""
        content = """[00:12.00][00:45.00]Chorus line
[00:17.20]Verse line"""

        phrases = parse_lrc_content(content)

        # Should create separate phrases for each timestamp (sorted by time)
        assert len(phrases) == 3
        assert phrases[0].text == "Chorus line"
        assert phrases[0].start_ms == 12000
        assert phrases[1].text == "Verse line"
        assert phrases[1].start_ms == 17200
        assert phrases[2].text == "Chorus line"
        assert phrases[2].start_ms == 45000

    def test_parse_empty_lines(self):
        """Parse LRC with empty lines."""
        content = """[00:12.00]First line

[00:17.20]Second line"""

        phrases = parse_lrc_content(content)

        assert len(phrases) == 2

    def test_parse_with_instrumental_breaks(self):
        """Parse LRC with instrumental sections."""
        content = """[00:12.00]Verse 1
[00:20.00]
[00:30.00]Verse 2"""

        phrases = parse_lrc_content(content)

        # Empty text is allowed (instrumental break)
        assert len(phrases) == 3
        assert phrases[0].text == "Verse 1"
        assert phrases[1].text == ""
        assert phrases[1].start_ms == 20000

    def test_compute_end_times(self):
        """End times computed from next line's start time."""
        content = """[00:12.00]First line
[00:17.20]Second line
[00:23.00]Third line"""

        phrases = parse_lrc_content(content)

        # End time should be start of next phrase
        assert phrases[0].end_ms == 17200
        assert phrases[1].end_ms == 23000
        # Last phrase end_ms equals start_ms (unknown duration)
        assert phrases[2].end_ms == 23000

    def test_parse_with_song_duration(self):
        """Parse with explicit song duration for last phrase."""
        content = """[00:12.00]First line
[00:17.20]Second line"""

        phrases = parse_lrc_content(content, duration_ms=25000)

        # Last phrase should extend to song end
        assert phrases[1].end_ms == 25000

    def test_parse_malformed_lines(self):
        """Malformed lines are skipped gracefully."""
        content = """[00:12.00]Valid line
Not a valid LRC line
[invalid:timestamp]Also invalid
[00:17.20]Another valid line"""

        phrases = parse_lrc_content(content)

        assert len(phrases) == 2
        assert phrases[0].text == "Valid line"
        assert phrases[1].text == "Another valid line"

    def test_parse_empty_content(self):
        """Empty content returns empty list."""
        phrases = parse_lrc_content("")
        assert phrases == []


class TestExtractEmbeddedLyrics:
    """Test complete embedded lyrics extraction."""

    def test_extract_from_lrc_sidecar(self):
        """Extract lyrics from .lrc sidecar file."""
        audio_path = "/test/audio/song.mp3"
        lrc_content = """[00:12.00]First line
[00:17.20]Second line"""

        with (
            patch("pathlib.Path.exists") as mock_exists,
            patch("pathlib.Path.read_text") as mock_read,
        ):
            # Mock .lrc file exists
            mock_exists.return_value = True
            mock_read.return_value = lrc_content

            text, phrases, words, warnings = extract_embedded_lyrics(audio_path)

        assert text is not None
        assert "First line" in text
        assert "Second line" in text
        assert len(phrases) == 2
        assert phrases[0].text == "First line"
        assert words == []  # LRC has phrase-level only
        assert warnings == []

    def test_extract_from_sylt_tag(self):
        """Extract lyrics from SYLT (synced) tag."""
        audio_path = "/test/audio/song.mp3"

        mock_file = MagicMock()
        mock_sylt = MagicMock()
        mock_sylt.format = 2  # SYLT format 2 (ms)
        mock_sylt.text = [
            (12000, "First line"),
            (17200, "Second line"),
        ]
        mock_file.tags = {"SYLT::eng": mock_sylt}

        with (
            patch("pathlib.Path.exists", return_value=False),
            patch("mutagen.File", return_value=mock_file),
        ):
            text, phrases, _words, _warnings = extract_embedded_lyrics(audio_path)

        assert text is not None
        assert len(phrases) == 2
        assert phrases[0].start_ms == 12000
        assert phrases[0].text == "First line"

    def test_extract_from_uslt_tag(self):
        """Extract lyrics from USLT (unsynced) tag."""
        audio_path = "/test/audio/song.mp3"

        mock_file = MagicMock()
        mock_uslt = MagicMock()
        mock_uslt.text = "First line\nSecond line\nThird line"
        mock_file.tags = {"USLT::eng": mock_uslt}

        with (
            patch("pathlib.Path.exists", return_value=False),
            patch("mutagen.File", return_value=mock_file),
        ):
            text, phrases, words, _warnings = extract_embedded_lyrics(audio_path)

        assert text is not None
        assert "First line" in text
        assert phrases == []  # No timing
        assert words == []

    def test_priority_lrc_over_tags(self):
        """LRC sidecar takes priority over tags."""
        audio_path = "/test/audio/song.mp3"
        lrc_content = "[00:12.00]LRC line"

        mock_file = MagicMock()
        mock_uslt = MagicMock()
        mock_uslt.text = "Tag line"
        mock_file.tags = {"USLT::eng": mock_uslt}

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=lrc_content),
            patch("mutagen.File", return_value=mock_file),
        ):
            text, _phrases, _words, _warnings = extract_embedded_lyrics(audio_path)

        # Should use LRC, not tag
        assert "LRC line" in text
        assert "Tag line" not in text

    def test_no_embedded_lyrics(self):
        """No embedded lyrics returns None."""
        audio_path = "/test/audio/song.mp3"

        mock_file = MagicMock()
        mock_file.tags = {}

        with (
            patch("pathlib.Path.exists", return_value=False),
            patch("mutagen.File", return_value=mock_file),
        ):
            text, phrases, words, _warnings = extract_embedded_lyrics(audio_path)

        assert text is None
        assert phrases == []
        assert words == []

    def test_extraction_warning_on_invalid_lrc(self):
        """Invalid LRC produces warning."""
        audio_path = "/test/audio/song.mp3"
        lrc_content = "Not a valid LRC file at all"

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=lrc_content),
        ):
            text, phrases, _words, warnings = extract_embedded_lyrics(audio_path)

        # Should fail gracefully
        assert text is None
        assert phrases == []
        assert len(warnings) > 0

    def test_extraction_handles_missing_file(self):
        """Missing audio file handled gracefully."""
        audio_path = "/test/audio/nonexistent.mp3"

        with (
            patch("pathlib.Path.exists", return_value=False),
            patch("mutagen.File", side_effect=FileNotFoundError),
        ):
            text, phrases, _words, warnings = extract_embedded_lyrics(audio_path)

        assert text is None
        assert phrases == []
        assert len(warnings) > 0

    def test_extraction_handles_corrupt_file(self):
        """Corrupt audio file handled gracefully."""
        audio_path = "/test/audio/corrupt.mp3"

        with (
            patch("pathlib.Path.exists", return_value=False),
            patch("mutagen.File", side_effect=Exception("Corrupt file")),
        ):
            text, phrases, _words, warnings = extract_embedded_lyrics(audio_path)

        assert text is None
        assert phrases == []
        assert len(warnings) > 0
