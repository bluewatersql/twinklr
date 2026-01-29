# Audio Pipeline Testing Guide

This guide explains how to test the audio analysis pipeline directly, including specific stages like WhisperX transcription.

## Quick Start

### Using Makefile (Recommended)

```bash
# Test full pipeline
make test-audio FILE=path/to/song.mp3

# Test with all enhancements enabled
make test-audio-all FILE=path/to/song.mp3

# Test WhisperX transcribe specifically
make test-audio-whisperx FILE=path/to/song.mp3
```

### Using Shell Script

```bash
# Full pipeline test
scripts/test_audio_simple.sh path/to/song.mp3

# Force WhisperX transcribe
scripts/test_audio_simple.sh path/to/song.mp3 whisperx

# Test lyrics only
scripts/test_audio_simple.sh path/to/song.mp3 lyrics-only

# Test metadata only
scripts/test_audio_simple.sh path/to/song.mp3 metadata-only

# Test Genius lookup specifically
scripts/test_audio_simple.sh path/to/song.mp3 genius

# Test LRCLib lookup specifically
scripts/test_audio_simple.sh path/to/song.mp3 lrclib
```

### Using Python Script Directly

```bash
# Basic usage
uv run python scripts/test_audio_pipeline.py path/to/song.mp3

# Force WhisperX transcribe (skip other lyrics sources)
uv run python scripts/test_audio_pipeline.py path/to/song.mp3 \
    --force-whisperx-transcribe \
    --no-cache

# Force WhisperX align with reference lyrics
uv run python scripts/test_audio_pipeline.py path/to/song.mp3 \
    --force-whisperx-align \
    --lyrics-text "your reference lyrics here" \
    --no-cache

# Test with specific WhisperX config
uv run python scripts/test_audio_pipeline.py path/to/song.mp3 \
    --whisperx-model small \
    --whisperx-device mps \
    --whisperx-batch-size 32

# Save full results to JSON
uv run python scripts/test_audio_pipeline.py path/to/song.mp3 \
    --output-json results.json

# Skip specific features
uv run python scripts/test_audio_pipeline.py path/to/song.mp3 \
    --skip-metadata \
    --skip-lyrics

# Enable everything
uv run python scripts/test_audio_pipeline.py path/to/song.mp3 \
    --enable-all
```

## Testing Specific Stages

### 1. Test WhisperX Transcribe

This forces WhisperX to transcribe lyrics from audio (no reference text):

```bash
# Using Makefile
make test-audio-whisperx FILE=path/to/song.mp3

# Using script
uv run python scripts/test_audio_pipeline.py path/to/song.mp3 \
    --force-whisperx-transcribe \
    --no-cache \
    --output-json whisperx_results.json
```

**Expected Output:**
- Lyrics source: `WHISPERX_TRANSCRIBE`
- Word-level timing for all transcribed words
- Quality metrics (coverage, gap ratio)
- Confidence score

### 2. Test WhisperX Align

This aligns existing lyrics text to audio timing:

```bash
# Read lyrics from Genius first
LYRICS=$(cat path/to/lyrics.txt)

# Test align
uv run python scripts/test_audio_pipeline.py path/to/song.mp3 \
    --force-whisperx-align \
    --lyrics-text "$LYRICS" \
    --no-cache
```

**Expected Output:**
- Lyrics source: `WHISPERX_ALIGN`
- Mismatch ratio (how well text matches audio)
- Word-level timing
- Confidence with mismatch penalty

### 3. Test Genius Lookup

```bash
scripts/test_audio_simple.sh path/to/song.mp3 genius
```

**Expected Output:**
- Lyrics source: `LOOKUP_PLAIN` (Genius)
- Plain text lyrics (no timing)
- May trigger WhisperX align if `lyrics_require_timed` is true

### 4. Test LRCLib Lookup

```bash
scripts/test_audio_simple.sh path/to/song.mp3 lrclib
```

**Expected Output:**
- Lyrics source: `LOOKUP_SYNCED` (LRCLib)
- Line-level timing
- Quality metrics

### 5. Test Metadata Only

```bash
scripts/test_audio_simple.sh path/to/song.mp3 metadata-only
```

**Expected Output:**
- Artist, title, album, genre
- Sources: embedded tags, AcoustID, MusicBrainz
- Fingerprint data

## Understanding Output

### Status Codes

- `✓ OK` - Stage completed successfully
- `⊘ SKIPPED` - Stage was skipped (disabled or not needed)
- `⚠ PARTIAL` - Stage completed with warnings
- `✗ ERROR` - Stage failed

### Lyrics Sources

1. **EMBEDDED** - From audio file tags (SYLT, USLT, LRC sidecar)
2. **LOOKUP_SYNCED** - From LRCLib (line-level timing)
3. **LOOKUP_PLAIN** - From Genius (plain text, no timing)
4. **WHISPERX_ALIGN** - WhisperX aligned existing text to audio
5. **WHISPERX_TRANSCRIBE** - WhisperX transcribed from audio

### Quality Metrics

- **Coverage**: % of song duration with lyrics
- **Gap Ratio**: % of silence/gaps between lyrics
- **Avg Word Duration**: Average duration per word (ms)
- **Confidence**: 0.0-1.0 score based on source and quality

## Common Use Cases

### Validate WhisperX Installation

```bash
# Test on a short audio file
make test-audio-whisperx FILE=test_audio.mp3

# Check for:
# - WhisperX model download (first run)
# - Successful transcription
# - Reasonable word timings
```

### Compare Lyrics Sources

```bash
# Test with cache enabled (will use best available source)
make test-audio FILE=song.mp3

# Test with cache disabled (force fresh analysis)
uv run python scripts/test_audio_pipeline.py song.mp3 --no-cache

# Test WhisperX specifically
make test-audio-whisperx FILE=song.mp3
```

### Debug Lyrics Issues

```bash
# Full debug output with all stages
uv run python scripts/test_audio_pipeline.py song.mp3 \
    --enable-all \
    --no-cache \
    --verbose \
    --output-json debug_results.json

# Check logs for:
# - Which providers were called
# - Why certain sources were skipped
# - Confidence scores and penalties
```

### Performance Testing

```bash
# Test with different WhisperX models
for model in tiny base small medium; do
    echo "Testing model: $model"
    time uv run python scripts/test_audio_pipeline.py song.mp3 \
        --whisperx-model $model \
        --no-cache
done
```

### GPU vs CPU Comparison

```bash
# CPU
time make test-audio-whisperx FILE=song.mp3 DEVICE=cpu

# GPU (Mac M1/M2/M3)
time uv run python scripts/test_audio_pipeline.py song.mp3 \
    --force-whisperx-transcribe \
    --whisperx-device mps \
    --no-cache

# GPU (NVIDIA)
time uv run python scripts/test_audio_pipeline.py song.mp3 \
    --force-whisperx-transcribe \
    --whisperx-device cuda \
    --no-cache
```

## Troubleshooting

### WhisperX Not Found

```bash
# Install ML dependencies
make install-dev

# Verify installation
uv pip list | grep whisperx
```

### Model Download Issues

```bash
# Check cache directory
ls -la ~/.cache/whisperx/
ls -la ~/.cache/huggingface/

# Clear cache and retry
rm -rf ~/.cache/whisperx/
make test-audio-whisperx FILE=song.mp3
```

### No Lyrics Found

```bash
# Check all stages with debug
uv run python scripts/test_audio_pipeline.py song.mp3 \
    --enable-all \
    --verbose 2>&1 | grep -i "lyrics"

# Verify providers are configured
grep -E "GENIUS|enable_lyrics" config.json .env
```

## Advanced Options

### Custom Configuration

Create a test config:
```json
{
  "audio_processing": {
    "enhancements": {
      "enable_whisperx": true,
      "whisperx_model": "medium",
      "whisperx_device": "mps",
      "whisperx_batch_size": 8,
      "lyrics_require_timed": true
    }
  }
}
```

Use it:
```bash
CONFIG=test_config.json uv run python scripts/test_audio_pipeline.py song.mp3
```

### Batch Testing

```bash
# Test all MP3 files in a directory
for file in music/*.mp3; do
    echo "Testing: $file"
    uv run python scripts/test_audio_pipeline.py "$file" \
        --output-json "results/$(basename "$file" .mp3).json"
done
```

### Integration with pytest

```python
# tests/integration/test_audio_pipeline_real.py
import subprocess

def test_whisperx_transcribe():
    result = subprocess.run([
        "uv", "run", "python", "scripts/test_audio_pipeline.py",
        "test_audio.mp3",
        "--force-whisperx-transcribe",
        "--output-json", "test_results.json",
    ], capture_output=True)
    
    assert result.returncode == 0
    # Parse and validate results...
```

## See Also

- [Audio Enhancement Setup](../doc/AUDIO_ENHANCEMENT_SETUP.md)
- [Configuration Reference](../doc/configs/)
- Main codebase: `packages/blinkb0t/core/audio/`
