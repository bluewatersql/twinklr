# Audio Pipeline Testing Examples

Quick reference for common testing scenarios.

## Prerequisites

```bash
# Install standard dependencies
make install

# Install ML dependencies (for WhisperX)
make install-dev

# Verify setup
uv pip list | grep -E "(whisperx|torch)"
```

## Basic Tests

### 1. Quick Test (Default Pipeline)

```bash
# Using Makefile
make test-audio FILE=path/to/song.mp3

# Using shell script
scripts/test_audio_simple.sh path/to/song.mp3
```

**What this tests:**
- Audio feature extraction (tempo, beats, bars, sections)
- Metadata lookup (if enabled in config)
- Lyrics resolution (embedded → LRCLib → Genius → WhisperX fallback)
- Uses cache if available

### 2. Force WhisperX Transcribe

```bash
# Using Makefile (easiest)
make test-audio-whisperx FILE=path/to/song.mp3

# Using shell script
scripts/test_audio_simple.sh path/to/song.mp3 whisperx

# Using Python directly (most control)
uv run --env-file .env python scripts/test_audio_pipeline.py path/to/song.mp3 \
    --force-whisperx-transcribe \
    --no-cache \
    --whisperx-model base \
    --whisperx-device cpu \
    --output-json whisperx_results.json
```

**What this tests:**
- WhisperX model loading
- Audio-to-text transcription
- Word-level timing generation
- Quality metrics
- Confidence scoring

**Expected output:**
```
================================================================================
  Results Summary
================================================================================

Duration: 197.40s
Tempo: 146.0 BPM
Beats: 480
Bars: 120
Sections: 8

Lyrics:
  Status: ✓ OK
  Source: WHISPERX_TRANSCRIBE (whisperx)
  Confidence: 0.78
  Text Length: 1245 chars
  Words: 187 timed words
  Phrases: 45 phrases
  Quality:
    Coverage: 82.45%
    Gap Ratio: 17.55%
    Avg Word Duration: 650ms

  First 5 words:
       0ms -    340ms: I
     340ms -    680ms: need
     680ms -   1020ms: a
    1020ms -   1360ms: favor
    1360ms -   1700ms: from
```

### 3. Test WhisperX Align (with reference lyrics)

```bash
# Get lyrics from Genius first
LYRICS="Your reference lyrics here...
Multiple lines...
Of lyrics text..."

# Test alignment
uv run python scripts/test_audio_pipeline.py path/to/song.mp3 \
    --force-whisperx-align \
    --lyrics-text "$LYRICS" \
    --no-cache
```

**What this tests:**
- Forced time alignment of text to audio
- Mismatch detection (how well text matches audio)
- Timing adjustment
- Quality validation

**Expected output includes:**
- Mismatch ratio (e.g., 0.08 = 8% mismatch)
- Confidence with mismatch penalty
- Word timings that match your reference text

### 4. Compare Lyrics Sources

```bash
# Test 1: With cache (will use best cached source)
echo "=== Test 1: Cached (normal flow) ==="
make test-audio FILE=song.mp3

# Test 2: Genius lookup
echo "=== Test 2: Force Genius ===" 
scripts/test_audio_simple.sh song.mp3 genius

# Test 3: LRCLib lookup
echo "=== Test 3: Force LRCLib ==="
scripts/test_audio_simple.sh song.mp3 lrclib

# Test 4: WhisperX transcribe
echo "=== Test 4: Force WhisperX ==="
make test-audio-whisperx FILE=song.mp3
```

Compare the output:
- Which source was used
- Confidence scores
- Word timing quality
- Coverage percentages

### 5. Test Metadata Extraction

```bash
# Metadata only (skip lyrics)
scripts/test_audio_simple.sh path/to/song.mp3 metadata-only
```

**Expected output:**
```
Metadata:
  Status: ✓ OK
  Resolved: Artist Name - Song Title
    Genre: ['Rock', 'Alternative']
    Year: 2023
  Embedded: Artist Name - Song Title
```

### 6. Test Performance

```bash
# Test different WhisperX models
echo "=== tiny model ==="
time uv run python scripts/test_audio_pipeline.py song.mp3 \
    --whisperx-model tiny --no-cache

echo "=== base model ==="
time uv run python scripts/test_audio_pipeline.py song.mp3 \
    --whisperx-model base --no-cache

echo "=== small model ==="
time uv run python scripts/test_audio_pipeline.py song.mp3 \
    --whisperx-model small --no-cache
```

**Expected timing (rough estimates for 3-minute song):**
- `tiny`: ~10-15 seconds (CPU)
- `base`: ~20-30 seconds (CPU)
- `small`: ~40-60 seconds (CPU)
- `medium`: ~2-3 minutes (CPU)

With GPU (MPS/CUDA), times are 5-10x faster.

### 7. Test GPU Acceleration (Mac)

```bash
# CPU baseline
time scripts/test_audio_simple.sh song.mp3 whisperx

# MPS (Apple Silicon GPU)
time uv run python scripts/test_audio_pipeline.py song.mp3 \
    --force-whisperx-transcribe \
    --whisperx-device mps \
    --no-cache
```

### 8. Batch Testing

```bash
# Test all songs in a directory
mkdir -p test_results

for file in music/*.mp3; do
    echo "Testing: $file"
    basename=$(basename "$file" .mp3)
    
    uv run python scripts/test_audio_pipeline.py "$file" \
        --enable-all \
        --output-json "test_results/${basename}.json" \
        > "test_results/${basename}.log" 2>&1
    
    echo "  → Results: test_results/${basename}.json"
done
```

### 9. Debug Mode (Full Logging)

```bash
# Maximum verbosity
uv run python scripts/test_audio_pipeline.py song.mp3 \
    --enable-all \
    --no-cache \
    --verbose \
    --output-json debug.json \
    2>&1 | tee debug.log

# Check logs
grep -i "whisperx" debug.log
grep -i "genius" debug.log
grep -i "error" debug.log
```

## Real-World Scenarios

### Scenario 1: Song with No Online Lyrics

**Goal:** Validate WhisperX can transcribe when no lyrics are available online

```bash
# Test song with no Genius/LRCLib results
make test-audio-whisperx FILE=obscure_song.mp3
```

**Look for:**
- WhisperX was actually called (not skipped)
- Reasonable transcription quality
- Word timings make sense

### Scenario 2: Song with Embedded Lyrics

**Goal:** Validate embedded lyrics are extracted correctly

```bash
# Test song with embedded SYLT/USLT tags
make test-audio FILE=song_with_tags.mp3
```

**Look for:**
- Lyrics source: `EMBEDDED`
- High confidence (0.70)
- Word/phrase timings from tags

### Scenario 3: Compare Accuracy

**Goal:** Compare Genius lyrics vs WhisperX transcription

```bash
# Get Genius lyrics
make test-audio FILE=song.mp3 > genius_output.txt

# Force WhisperX
make test-audio-whisperx FILE=song.mp3 > whisperx_output.txt

# Compare
diff genius_output.txt whisperx_output.txt
```

### Scenario 4: Validate Timing Quality

**Goal:** Ensure word timings are reasonable

```bash
# Test with JSON output
uv run python scripts/test_audio_pipeline.py song.mp3 \
    --output-json results.json

# Analyze timings
python -c "
import json
data = json.load(open('results.json'))
words = data['lyrics']['words']

# Check for timing issues
for i, word in enumerate(words):
    duration = word['end_ms'] - word['start_ms']
    if duration < 50:  # Words shorter than 50ms
        print(f'Warning: Very short word at {word[\"start_ms\"]}ms: {word[\"text\"]} ({duration}ms)')
    if duration > 5000:  # Words longer than 5s
        print(f'Warning: Very long word at {word[\"start_ms\"]}ms: {word[\"text\"]} ({duration}ms)')

# Check for gaps
for i in range(len(words)-1):
    gap = words[i+1]['start_ms'] - words[i]['end_ms']
    if gap > 3000:  # Gaps > 3s
        print(f'Warning: Large gap at {words[i][\"end_ms\"]}ms: {gap}ms')
"
```

## Troubleshooting Examples

### WhisperX Not Installing

```bash
# Check Python version
python --version  # Must be 3.10-3.12

# Try clean install
make clean-venv
make install-dev

# Verify
uv pip list | grep whisperx
```

### WhisperX Model Not Downloading

```bash
# Check cache
ls -la ~/.cache/whisperx/

# Test with smallest model first
uv run python scripts/test_audio_pipeline.py song.mp3 \
    --whisperx-model tiny \
    --force-whisperx-transcribe \
    --no-cache

# Check network/proxy settings
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

### Poor Transcription Quality

```bash
# Try larger model
uv run python scripts/test_audio_pipeline.py song.mp3 \
    --whisperx-model medium \
    --force-whisperx-transcribe

# Try with GPU
uv run python scripts/test_audio_pipeline.py song.mp3 \
    --whisperx-device mps \
    --whisperx-model base \
    --force-whisperx-transcribe
```

### Genius API Not Working

```bash
# Check API token
grep GENIUS .env

# Test token directly
curl "https://api.genius.com/search?q=test" \
    -H "Authorization: Bearer $GENIUS_ACCESS_TOKEN"

# Test with verbose logging
uv run python scripts/test_audio_pipeline.py song.mp3 \
    --verbose 2>&1 | grep -i genius
```

## See Also

- [Full Testing Guide](README_TESTING.md)
- [Audio Enhancement Setup](../doc/AUDIO_ENHANCEMENT_SETUP.md)
- [Configuration Reference](../config.json)
