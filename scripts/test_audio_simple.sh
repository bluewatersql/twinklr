#!/bin/bash
# Simple audio pipeline test examples

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Check if audio file provided
if [ -z "$1" ]; then
    echo -e "${YELLOW}Usage: $0 <audio_file.mp3>${NC}"
    echo ""
    echo "Examples:"
    echo "  $0 path/to/song.mp3                    # Full pipeline"
    echo "  $0 path/to/song.mp3 whisperx           # Force WhisperX transcribe"
    echo "  $0 path/to/song.mp3 lyrics-only        # Only test lyrics"
    echo "  $0 path/to/song.mp3 metadata-only      # Only test metadata"
    exit 1
fi

AUDIO_FILE="$1"
MODE="${2:-full}"

if [ ! -f "$AUDIO_FILE" ]; then
    echo -e "${YELLOW}Error: File not found: $AUDIO_FILE${NC}"
    exit 1
fi

cd "$PROJECT_ROOT"

case "$MODE" in
    "full")
        echo -e "${BLUE}Testing full audio pipeline...${NC}"
        uv run python scripts/test_audio_pipeline.py "$AUDIO_FILE" --enable-all
        ;;
    "whisperx")
        echo -e "${BLUE}Testing WhisperX transcribe (no cache)...${NC}"
        uv run python scripts/test_audio_pipeline.py "$AUDIO_FILE" \
            --force-whisperx-transcribe \
            --no-cache \
            --whisperx-model base \
            --whisperx-device cpu
        ;;
    "lyrics-only")
        echo -e "${BLUE}Testing lyrics only...${NC}"
        uv run python scripts/test_audio_pipeline.py "$AUDIO_FILE" \
            --skip-metadata \
            --skip-phonemes
        ;;
    "metadata-only")
        echo -e "${BLUE}Testing metadata only...${NC}"
        uv run python scripts/test_audio_pipeline.py "$AUDIO_FILE" \
            --skip-lyrics \
            --skip-phonemes
        ;;
    "genius")
        echo -e "${BLUE}Testing Genius lookup...${NC}"
        uv run python scripts/test_audio_pipeline.py "$AUDIO_FILE" \
            --force-plain-lookup
        ;;
    "lrclib")
        echo -e "${BLUE}Testing LRCLib lookup...${NC}"
        uv run python scripts/test_audio_pipeline.py "$AUDIO_FILE" \
            --force-synced-lookup
        ;;
    *)
        echo -e "${YELLOW}Unknown mode: $MODE${NC}"
        echo "Valid modes: full, whisperx, lyrics-only, metadata-only, genius, lrclib"
        exit 1
        ;;
esac
