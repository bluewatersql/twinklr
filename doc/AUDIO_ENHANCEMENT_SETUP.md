# Audio Enhancement Setup Guide (v3.0)

**Version**: 3.0  
**Features**: Metadata enrichment, Lyrics resolution, Phoneme/viseme generation  
**Date**: 2026-01-27

---

## Quick Start

### Minimal Install (Embedded-Only Mode)

Works with zero configuration. No API keys, no network calls, no ML models.

```bash
# Install core dependencies
uv sync

# Run BlinkB0t (uses embedded metadata and .lrc files only)
uv run blinkb0t run --audio song.mp3 --xsq sequence.xsq --config job_config.json
```

**Features available**:
- ✅ Embedded metadata from audio file tags
- ✅ Lyrics from .lrc sidecar files or embedded tags
- ✅ Phoneme/viseme generation (if lyrics have timing)

---

## Full Install (Network + ML Features)

Enables all features including online lookups and AI transcription.

### 1. Install Python Dependencies

```bash
# Install with optional ML dependencies
uv sync --extra ml
```

### 2. Install Binary Dependencies

#### macOS (Homebrew)
```bash
brew install chromaprint ffmpeg
```

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install libchromaprint-tools ffmpeg
```

#### Windows
- **chromaprint**: Download from https://acoustid.org/chromaprint
- **ffmpeg**: Download from https://ffmpeg.org/ (already required)

### 3. Set Up API Keys

Copy `.env.example` to `.env` and add your API keys:

```bash
cp .env.example .env
```

Edit `.env`:
```bash
# Required
OPENAI_API_KEY=sk-proj-your_key_here

# Optional (for audio enhancements)
ACOUSTID_API_KEY=your_acoustid_key_here
GENIUS_CLIENT_TOKEN=your_genius_token_here
HF_TOKEN=your_huggingface_token_here
```

**Get API keys**:
- **AcoustID**: https://acoustid.org/api-key (free)
- **Genius**: https://genius.com/api-clients (free)
- **HuggingFace**: https://huggingface.co/settings/tokens (free)

### 4. Configure Features

Edit `config.json`:

```json
{
  "audio_processing": {
    "enhancements": {
      "enable_metadata": true,
      "enable_lyrics": true,
      "enable_phonemes": true,
      "enable_acoustid": true,
      "enable_musicbrainz": true,
      "enable_lyrics_lookup": true,
      "enable_whisperx": false,
      "enable_diarization": false
    }
  }
}
```

---

## Feature Flags

### Metadata Enrichment

**`enable_metadata`** (default: `true`)
- Extracts embedded tags from audio files (title, artist, album, artwork, etc.)
- Always works without network

**`enable_acoustid`** (default: `false`)
- Fingerprints audio and queries AcoustID database
- **Requires**: `ACOUSTID_API_KEY` + `chromaprint` binary
- Provides canonical MusicBrainz IDs

**`enable_musicbrainz`** (default: `false`)
- Queries MusicBrainz for canonical metadata
- **No API key required** (rate limited to 1 request/second)
- Enhances accuracy with canonical data

### Lyrics Resolution

**`enable_lyrics`** (default: `true`)
- Resolves lyrics from multiple sources
- Always works without network (uses .lrc files and embedded tags)

**`enable_lyrics_lookup`** (default: `false`)
- Queries online lyrics providers (LRCLib, Genius)
- **Requires**: Provider API keys (e.g., `GENIUS_CLIENT_TOKEN`)
- Provides synced lyrics with word-level timing

**`enable_whisperx`** (default: `false`)
- Uses AI to transcribe or align lyrics
- **Requires**: Model download (~150MB for 'base' model)
- **No API key required**
- Triggers automatically if lyrics missing or insufficient timing

**`enable_diarization`** (default: `false`)
- Detects multiple speakers in audio
- **Requires**: `HF_TOKEN` + model download (~300MB)
- Useful for duets, features, backing vocals

### Phoneme/Viseme Generation

**`enable_phonemes`** (default: `true`)
- Generates phoneme and viseme timing for lip-sync
- **Requires**: Timed lyrics (word-level timestamps)
- Uses CMUdict (built-in) + g2p_en for fallback
- Smoothing applied for singing decor

---

## Model Downloads

### WhisperX Models (Auto-Downloaded on First Use)

When `enable_whisperx=true`, models download automatically on first use.

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| tiny  | ~75 MB | Very fast | Low |
| base  | ~150 MB | Fast | Good |
| small | ~500 MB | Medium | Better |
| medium | ~1.5 GB | Slow | Very good |
| large | ~3 GB | Very slow | Best |

**Configuration**:
```json
{
  "audio_processing": {
    "enhancements": {
      "whisperx_model": "base",
      "whisperx_device": "cpu"
    }
  }
}
```

**Device options**:
- `cpu`: Works everywhere (slow)
- `cuda`: NVIDIA GPU (fast)
- `mps`: Apple Silicon GPU (fast)

### Pyannote Models (Auto-Downloaded on First Use)

When `enable_diarization=true`:
- Requires `HF_TOKEN` environment variable
- Downloads ~300MB on first use
- Cached locally after download

---

## Verification

### Check Binary Dependencies

```bash
# Check chromaprint
fpcalc -version
# Should print: fpcalc version 1.5.x

# Check ffmpeg
ffmpeg -version
# Should print: ffmpeg version 4.x or higher
```

### Test Configuration Loading

```bash
# Verify config loads without errors
uv run python -c "from blinkb0t.core.config import AppConfig; c = AppConfig.load_or_default(); print('Config loaded successfully'); print(f'Metadata enabled: {c.audio_processing.enhancements.enable_metadata}')"
```

Expected output:
```
Config loaded successfully
Metadata enabled: True
```

### Test with Sample Audio

```bash
# Run with minimal features (embedded only)
uv run blinkb0t run --audio test.mp3 --xsq test.xsq --config job_config.json
```

---

## Troubleshooting

### chromaprint not found

**Error**: `ChromaprintError: fpcalc not found`

**Solution**:
```bash
# macOS
brew install chromaprint

# Ubuntu
sudo apt-get install libchromaprint-tools

# Verify
fpcalc -version
```

### API Key Errors

**Error**: `enable_acoustid is true but ACOUSTID_API_KEY not set`

**Solution**:
1. Get API key from https://acoustid.org/api-key
2. Add to `.env`: `ACOUSTID_API_KEY=your_key_here`
3. Restart BlinkB0t

### Model Download Errors

**Error**: `HF_TOKEN required for diarization`

**Solution**:
1. Get token from https://huggingface.co/settings/tokens
2. Add to `.env`: `HF_TOKEN=your_token_here`
3. Accept model license agreement on HuggingFace website
4. Restart BlinkB0t (will download on first use)

### Rate Limit Errors

**Error**: `MusicBrainz rate limit exceeded`

**Solution**:
- MusicBrainz limits requests to 1 per second
- Framework automatically retries with backoff
- If persistent, adjust: `musicbrainz_rate_limit_rps: 0.5` in config

### Performance Issues

**Slow WhisperX**: Use smaller model or CPU
```json
{
  "enhancements": {
    "whisperx_model": "tiny",
    "whisperx_device": "cpu"
  }
}
```

**Slow Diarization**: Disable if not needed
```json
{
  "enhancements": {
    "enable_diarization": false
  }
}
```

---

## Gradual Rollout Strategy

### Phase 1: Embedded Only (Zero Risk)

```json
{
  "audio_processing": {
    "enhancements": {
      "enable_metadata": true,
      "enable_lyrics": true,
      "enable_phonemes": true,
      "enable_acoustid": false,
      "enable_musicbrainz": false,
      "enable_lyrics_lookup": false,
      "enable_whisperx": false,
      "enable_diarization": false
    }
  }
}
```

**Result**: Uses embedded tags and .lrc files only. No network, no models.

### Phase 2: Add Network Metadata (Low Risk)

```json
{
  "enhancements": {
    "enable_acoustid": true,
    "enable_musicbrainz": true
  }
}
```

**Requires**: `ACOUSTID_API_KEY` + chromaprint binary

### Phase 3: Add Online Lyrics (Medium Risk)

```json
{
  "enhancements": {
    "enable_lyrics_lookup": true
  }
}
```

**Requires**: Provider API keys (e.g., Genius)

### Phase 4: Add AI Features (High Resource)

```json
{
  "enhancements": {
    "enable_whisperx": true,
    "enable_diarization": true
  }
}
```

**Requires**: Model downloads, GPU recommended

---

## Performance Expectations

| Feature | First Run | Cached | Notes |
|---------|-----------|--------|-------|
| Embedded metadata | ~50ms | ~5ms | Fast |
| AcoustID lookup | ~1-3s | ~5ms | Cached 30 days |
| MusicBrainz lookup | ~1-2s | ~5ms | Cached 30 days, rate limited |
| Lyrics lookup | ~1-5s | ~5ms | Cached 30 days |
| WhisperX (base, CPU) | ~10-30s | ~10ms | Heavy, cached |
| Diarization | ~20-60s | ~10ms | Heavy, cached |
| Phonemes | ~100ms | ~5ms | Fast |

**All results cached globally**. Subsequent runs instant (< 100ms total).

---

## Advanced Configuration

See `01_architecture_full_spec.md` in specs for complete configuration reference.

### Custom WhisperX Settings

```json
{
  "enhancements": {
    "whisperx_model": "small",
    "whisperx_device": "cuda",
    "whisperx_batch_size": 32,
    "whisperx_return_char_alignments": true
  }
}
```

### Custom Phoneme Weights

```json
{
  "enhancements": {
    "phoneme_vowel_weight": 2.5,
    "phoneme_consonant_weight": 0.8,
    "phoneme_min_duration_ms": 40
  }
}
```

### Custom Viseme Smoothing

```json
{
  "enhancements": {
    "viseme_min_hold_ms": 60,
    "viseme_min_burst_ms": 50,
    "viseme_boundary_soften_ms": 20
  }
}
```

---

## Support

**Documentation**: `changes/vnext/specs/audio/`  
**Configuration**: `doc/configs/app_config.example.json`  
**Environment**: `.env.example`

---

## Changelog

### v3.0 (2026-01-27)
- Added audio enhancement features
- Metadata enrichment (embedded + AcoustID + MusicBrainz)
- Lyrics resolution (embedded + lookup + WhisperX)
- Phoneme/viseme generation
- Framework integration (core.io, core.api.http, core.caching)
