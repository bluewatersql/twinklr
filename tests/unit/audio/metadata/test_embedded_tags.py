"""Tests for embedded tag extraction (Phase 2).

Following TDD for embedded metadata extraction using mutagen.
"""

import hashlib
from unittest.mock import Mock, patch

from twinklr.core.audio.metadata.embedded_tags import extract_embedded_metadata
from twinklr.core.audio.models.metadata import EmbeddedMetadata


class TestExtractEmbeddedMetadata:
    """Test embedded tag extraction."""

    def test_no_tags_returns_empty_metadata(self):
        """File with no tags returns empty EmbeddedMetadata."""
        # Mock mutagen to return None (no tags)
        with patch("twinklr.core.audio.metadata.embedded_tags.File", return_value=None):
            result = extract_embedded_metadata("/fake/path.mp3")

        assert isinstance(result, EmbeddedMetadata)
        assert result.title is None
        assert result.artist is None
        assert len(result.warnings) == 1
        assert "No tags found" in result.warnings[0]

    def test_basic_id3_tags(self):
        """Extract basic ID3 tags from MP3."""
        # Mock mutagen File with ID3 tags
        mock_file = Mock()
        mock_file.tags = {
            "TIT2": Mock(text=["Test Song"]),  # Title
            "TPE1": Mock(text=["Test Artist"]),  # Artist
            "TALB": Mock(text=["Test Album"]),  # Album
        }
        mock_file.pictures = []

        with patch("twinklr.core.audio.metadata.embedded_tags.File", return_value=mock_file):
            result = extract_embedded_metadata("/fake/path.mp3")

        assert result.title == "Test Song"
        assert result.artist == "Test Artist"
        assert result.album == "Test Album"

    def test_track_and_disc_numbers(self):
        """Extract track and disc numbers."""
        mock_file = Mock()
        mock_file.tags = {
            "TRCK": Mock(text=["5/12"]),  # Track 5 of 12
            "TPOS": Mock(text=["1/2"]),  # Disc 1 of 2
        }
        mock_file.pictures = []

        with patch("twinklr.core.audio.metadata.embedded_tags.File", return_value=mock_file):
            result = extract_embedded_metadata("/fake/path.mp3")

        assert result.track_number == 5
        assert result.track_total == 12
        assert result.disc_number == 1
        assert result.disc_total == 2

    def test_year_extraction(self):
        """Extract year from various date formats."""
        mock_file = Mock()
        mock_file.tags = {
            "TDRC": Mock(text=["2026"]),  # Recording time
        }
        mock_file.pictures = []

        with patch("twinklr.core.audio.metadata.embedded_tags.File", return_value=mock_file):
            result = extract_embedded_metadata("/fake/path.mp3")

        assert result.year == 2026
        assert result.date_raw == "2026"

    def test_genre_list(self):
        """Extract genre as list."""
        mock_file = Mock()
        mock_file.tags = {
            "TCON": Mock(text=["Rock", "Alternative"]),  # Genre
        }
        mock_file.pictures = []

        with patch("twinklr.core.audio.metadata.embedded_tags.File", return_value=mock_file):
            result = extract_embedded_metadata("/fake/path.mp3")

        assert result.genre == ["Rock", "Alternative"]

    def test_artwork_detection_and_hashing(self):
        """Detect artwork and compute SHA256 hash."""
        # Create fake artwork data
        artwork_data = b"fake image data for testing"
        expected_hash = hashlib.sha256(artwork_data).hexdigest()

        mock_picture = Mock()
        mock_picture.data = artwork_data
        mock_picture.mime = "image/jpeg"

        mock_file = Mock()
        mock_file.tags = {}
        mock_file.pictures = [mock_picture]

        with patch("twinklr.core.audio.metadata.embedded_tags.File", return_value=mock_file):
            result = extract_embedded_metadata("/fake/path.mp3")

        assert result.artwork_present is True
        assert result.artwork_mime == "image/jpeg"
        assert result.artwork_hash_sha256 == expected_hash
        assert result.artwork_size_bytes == len(artwork_data)

    def test_lyrics_detection(self):
        """Detect embedded lyrics (USLT/SYLT tags)."""
        mock_file = Mock()
        mock_file.tags = {
            "USLT": Mock(text=["Verse 1: Test lyrics"]),  # Unsynchronized lyrics
        }
        mock_file.pictures = []

        with patch("twinklr.core.audio.metadata.embedded_tags.File", return_value=mock_file):
            result = extract_embedded_metadata("/fake/path.mp3")

        assert result.lyrics_embedded_present is True

    def test_compilation_flag(self):
        """Detect compilation album flag."""
        mock_file = Mock()
        mock_file.tags = {
            "TCMP": Mock(text=["1"]),  # Compilation flag
        }
        mock_file.pictures = []

        with patch("twinklr.core.audio.metadata.embedded_tags.File", return_value=mock_file):
            result = extract_embedded_metadata("/fake/path.mp3")

        assert result.compilation is True

    def test_file_not_found_returns_warning(self):
        """Non-existent file returns metadata with warning."""
        with patch(
            "twinklr.core.audio.metadata.embedded_tags.File", side_effect=FileNotFoundError()
        ):
            result = extract_embedded_metadata("/nonexistent/file.mp3")

        assert isinstance(result, EmbeddedMetadata)
        assert len(result.warnings) > 0
        assert any("not found" in w.lower() for w in result.warnings)

    def test_corrupted_file_returns_warning(self):
        """Corrupted file returns metadata with warning."""
        with patch(
            "twinklr.core.audio.metadata.embedded_tags.File", side_effect=Exception("Corrupted")
        ):
            result = extract_embedded_metadata("/fake/corrupted.mp3")

        assert isinstance(result, EmbeddedMetadata)
        assert len(result.warnings) > 0

    def test_vorbis_comments_flac(self):
        """Extract Vorbis comments from FLAC."""
        mock_file = Mock()
        mock_file.tags = {
            "title": ["Test Title"],
            "artist": ["Test Artist"],
            "album": ["Test Album"],
        }
        # FLAC doesn't have pictures attribute, might have different structure
        mock_file.pictures = []

        with patch("twinklr.core.audio.metadata.embedded_tags.File", return_value=mock_file):
            result = extract_embedded_metadata("/fake/file.flac")

        # Should normalize to canonical fields
        assert result.title == "Test Title"
        assert result.artist == "Test Artist"

    def test_empty_string_fields_converted_to_none(self):
        """Empty string fields should be converted to None."""
        mock_file = Mock()
        mock_file.tags = {
            "TIT2": Mock(text=[""]),  # Empty title
            "TPE1": Mock(text=["  "]),  # Whitespace-only artist
        }
        mock_file.pictures = []

        with patch("twinklr.core.audio.metadata.embedded_tags.File", return_value=mock_file):
            result = extract_embedded_metadata("/fake/path.mp3")

        assert result.title is None
        assert result.artist is None

    def test_multiple_artwork_uses_first(self):
        """Multiple artwork images - use first one."""
        artwork1 = b"image1"
        artwork2 = b"image2"

        mock_pic1 = Mock()
        mock_pic1.data = artwork1
        mock_pic1.mime = "image/jpeg"

        mock_pic2 = Mock()
        mock_pic2.data = artwork2
        mock_pic2.mime = "image/png"

        mock_file = Mock()
        mock_file.tags = {}
        mock_file.pictures = [mock_pic1, mock_pic2]

        with patch("twinklr.core.audio.metadata.embedded_tags.File", return_value=mock_file):
            result = extract_embedded_metadata("/fake/path.mp3")

        # Should use first artwork
        assert result.artwork_hash_sha256 == hashlib.sha256(artwork1).hexdigest()
        assert result.artwork_mime == "image/jpeg"
