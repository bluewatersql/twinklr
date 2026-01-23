#Lyric Lookup & Resolution

###Approximate Pipeline
1. Try synced lyrics (SYLT / LRC) → exit
2. Else fetch plain lyrics
3. Run WhisperX transcription (optionally with initial_prompt per chunk)
4. Reconcile ASR↔lyrics to get canonical lyric tokens
5. Run WhisperX align() on lyric-based segments to refine word times
6. (Optional) diarization only if you care about speaker labels

####Lyrics Lookup
```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import requests

@dataclass(frozen=True)
class LyricsResult:
    source: str
    synced_lrc: Optional[str] = None
    plain: Optional[str] = None
    confidence: float = 0.0

def fetch_lrclib(artist: str, title: str, duration_s: int) -> Optional[LyricsResult]:
    # LRCLIB has multiple endpoints; this is a “shape” you can adapt to the docs.
    # Keep duration in the query to reduce mismatches.
    resp = requests.get(
        "https://lrclib.net/api/search",
        params={"artist_name": artist, "track_name": title, "duration": duration_s},
        timeout=10,
    )
    resp.raise_for_status()
    candidates = resp.json()
    if not candidates:
        return None

    best = candidates[0]  # you should re-rank: duration diff, exact artist/title match, etc.
    synced = best.get("syncedLyrics") or best.get("synced_lyrics") or best.get("lrc")
    plain = best.get("plainLyrics") or best.get("plain_lyrics") or best.get("lyrics")

    if synced:
        return LyricsResult(source="lrclib", synced_lrc=synced, confidence=0.8)
    if plain:
        return LyricsResult(source="lrclib", plain=plain, confidence=0.5)
    return None
```

####Reconcilation Sketch
```python
import re
from rapidfuzz import fuzz

def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[\[\]\(\)\{\}]", " ", s)
    s = re.sub(r"[^a-z0-9'\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # optional: expand a few common contractions
    s = s.replace("gonna", "going to").replace("wanna", "want to")
    return s

def best_lyric_block_for_segment(seg_text: str, lyric_blocks: list[str]) -> int:
    seg_n = norm(seg_text)
    best_i, best_score = 0, -1
    for i, block in enumerate(lyric_blocks):
        score = fuzz.token_set_ratio(seg_n, norm(block))
        if score > best_score:
            best_i, best_score = i, score
    return best_i

# After WhisperX align, you have segments with seg["words"] = [{"word":..., "start":..., "end":...}, ...]
def project_times_to_lyrics(seg_words, lyric_text: str):
    # Simple heuristic: greedy match words; you can upgrade to DP alignment later.
    lyric_words = norm(lyric_text).split()
    asr_words = [norm(w["word"]) for w in seg_words]
    out = []
    j = 0
    for lw in lyric_words:
        # find next matching asr word
        while j < len(asr_words) and asr_words[j] != lw:
            j += 1
        if j < len(asr_words):
            out.append({"word": lw, "start": seg_words[j]["start"], "end": seg_words[j]["end"], "source": "asr"})
            j += 1
        else:
            out.append({"word": lw, "start": None, "end": None, "source": "insert"})  # fill via interpolation later
    return out
```

####WhisperX Transcription

```python
import whisperx
import gc 
import torch

# Configuration
audio_file = "path/to/your_audio.mp3"
batch_size = 16 

# Set compute_type="int8" for CPU to reduce memory usage, or "float16" for GPU
device = "cpu"
compute_type = int8" 
hf_token = "YOUR_HUGGING_FACE_TOKEN" # Required for speaker diarization

# 1. Load model and audio
model = whisperx.load_model("large-v3", device=device, compute_type=compute_type)
audio = whisperx.load_audio(audio_file)

# 2. Transcribe audio
result = model.transcribe(audio, batch_size=batch_size)
print(result["segments"]) # Prints initial transcription with utterance-level timestamps

# delete model if low on GPU resources
gc.collect()

# 3. Align transcription (for accurate word-level timestamps)
model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
print(result["segments"]) # Prints segments with word_timestamps

# delete alignment model and metadata
gc.collect()

# 4. Diarization (speaker identification)
diarize_model = whisperx.DiarizationPipeline(use_auth_token=hf_token, device=device)
diarize_segments = diarize_model(audio_file)

# 5. Assign speakers to segments
result = whisperx.assign_speakers_to_segments(result["segments"], diarize_segments, merge_word_info=False)
print(result["segments"]) # Prints final transcription with speaker labels assigned to each segment
```

####WhisperX Transcribing with Plain Lyrics (biased)

```python
from __future__ import annotations

import math
from typing import Any

import numpy as np
import whisperx


def chunk_audio(
    audio: np.ndarray,
    sample_rate: int,
    chunk_s: float = 30.0,
    overlap_s: float = 2.0,
) -> list[tuple[float, np.ndarray]]:
    """Return [(chunk_start_seconds, chunk_audio_np), ...]."""
    chunk_n = int(chunk_s * sample_rate)
    overlap_n = int(overlap_s * sample_rate)
    step = max(1, chunk_n - overlap_n)

    chunks: list[tuple[float, np.ndarray]] = []
    for start in range(0, len(audio), step):
        end = min(len(audio), start + chunk_n)
        if end - start < int(5 * sample_rate):  # skip tiny tail
            break
        chunks.append((start / sample_rate, audio[start:end]))
        if end == len(audio):
            break
    return chunks


def split_lyrics_into_blocks(lyrics_plain: str, lines_per_block: int = 4) -> list[str]:
    """Very simple: chunk lyrics lines into blocks for prompting."""
    lines = [ln.strip() for ln in lyrics_plain.splitlines() if ln.strip()]
    blocks = []
    for i in range(0, len(lines), lines_per_block):
        blocks.append("\n".join(lines[i : i + lines_per_block]))
    return blocks or [""]


def transcribe_with_lyric_bias(
    audio_file: str,
    lyrics_plain: str,
    *,
    device: str = "cpu",
    compute_type: str = "int8",  # "float16" on GPU
    model_name: str = "large-v3",
    batch_size: int = 16,
    sample_rate: int = 16000,  # whisperx.load_audio returns 16k audio
) -> dict[str, Any]:
    model = whisperx.load_model(model_name, device=device, compute_type=compute_type)
    audio = whisperx.load_audio(audio_file)  # np.ndarray float32 @ 16kHz

    lyric_blocks = split_lyrics_into_blocks(lyrics_plain, lines_per_block=4)

    # Chunk the audio so we can change the prompt over time
    chunks = chunk_audio(audio, sample_rate=sample_rate, chunk_s=30.0, overlap_s=2.0)

    all_segments: list[dict[str, Any]] = []
    for idx, (t0, chunk) in enumerate(chunks):
        # Naive sequential mapping: chunk 0 uses block 0, chunk 1 uses block 1, etc.
        # You can improve this later with fuzzy matching / section detection.
        block = lyric_blocks[min(idx, len(lyric_blocks) - 1)]

        # Keep prompts short and “local” to the chunk
        prompt = (
            "These are the expected lyrics in this section. "
            "Transcribe matching the wording closely:\n"
            f"{block}\n"
        )

        # WhisperX forwards kwargs to the underlying Whisper/faster-whisper decode.
        # `initial_prompt` is the key biasing hook.
        result = model.transcribe(
            chunk,
            batch_size=batch_size,
            initial_prompt=prompt,
            # optional knobs:
            # language="en",        # set if known; otherwise Whisper will detect per chunk
            # temperature=0.0,      # reduce “creative” decoding
            # vad_filter=True,      # can help on noisy tracks
        )

        # Shift chunk-relative times to absolute times
        for seg in result.get("segments", []):
            seg = dict(seg)
            if "start" in seg:
                seg["start"] = float(seg["start"]) + t0
            if "end" in seg:
                seg["end"] = float(seg["end"]) + t0
            all_segments.append(seg)

    # Optional: de-overlap segments (simple heuristic)
    all_segments.sort(key=lambda s: (s.get("start", 0.0), s.get("end", 0.0)))
    deduped: list[dict[str, Any]] = []
    last_end = -math.inf
    for seg in all_segments:
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", 0.0))
        if start < last_end - 0.25:  # overlap region (tune)
            continue
        deduped.append(seg)
        last_end = max(last_end, end)

    return {"segments": deduped}


if __name__ == "__main__":
    audio_file = "path/to/song.mp3"
    lyrics_plain = """
    Hello darkness, my old friend
    I've come to talk with you again
    Because a vision softly creeping
    Left its seeds while I was sleeping
    """

    out = transcribe_with_lyric_bias(
        audio_file=audio_file,
        lyrics_plain=lyrics_plain,
        device="cpu",
        compute_type="int8",
        model_name="large-v3",
        batch_size=16,
    )

    for s in out["segments"][:5]:
        print(f'{s.get("start", 0):7.2f}-{s.get("end", 0):7.2f}  {s.get("text","")}')

```

###Single-Pass + Target Prompt Feedback

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import re
import numpy as np
import whisperx
from rapidfuzz import fuzz


@dataclass(frozen=True)
class Section:
    name: str
    start_s: float
    end_s: float


def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9'\s]", " ", s)
    return " ".join(s.split())


def _best_block_id(text: str, lyric_blocks: dict[str, str]) -> tuple[str, int]:
    t = _norm(text)
    best_id = next(iter(lyric_blocks.keys()))
    best_score = -1
    for bid, btxt in lyric_blocks.items():
        score = fuzz.token_set_ratio(t, _norm(btxt))
        if score > best_score:
            best_id, best_score = bid, score
    return best_id, best_score


def _slice_audio(audio: np.ndarray, sr: int, start_s: float, end_s: float, pad_s: float = 0.25) -> tuple[float, np.ndarray]:
    start = max(0, int((start_s - pad_s) * sr))
    end = min(len(audio), int((end_s + pad_s) * sr))
    return start / sr, audio[start:end]


def cpu_whisperx_with_lyrics_guidance(
    audio_file: str,
    sections: list[Section],
    lyric_blocks: dict[str, str],
    *,
    device: str = "cpu",
    compute_type: str = "int8",
    model_name: str = "large-v3",
    batch_size: int = 8,
    sr: int = 16000,
    retx_threshold: int = 45,  # match score below this triggers targeted re-transcribe
) -> dict[str, Any]:
    # 1) One full-song transcription (cheap-ish relative to N section passes)
    model = whisperx.load_model(model_name, device=device, compute_type=compute_type)
    audio = whisperx.load_audio(audio_file)
    base = model.transcribe(audio, batch_size=batch_size)

    # 2) Assign each structure section a lyric block based on the ASR text within that time range
    #    (No re-transcribe yet.)
    segments = base.get("segments", [])
    section_assignments: list[dict[str, Any]] = []

    for sec in sections:
        sec_text_parts = [
            seg.get("text", "")
            for seg in segments
            if float(seg.get("start", 0.0)) >= sec.start_s and float(seg.get("end", 0.0)) <= sec.end_s
        ]
        rough_text = " ".join(sec_text_parts).strip()
        bid, score = _best_block_id(rough_text, lyric_blocks) if rough_text else (_best_block_id(sec.name, lyric_blocks))

        section_assignments.append(
            {
                "section": sec,
                "lyric_block_id": bid,
                "match_score": score,
                "rough_text": rough_text,
            }
        )

    # 3) Targeted re-transcribe ONLY low-confidence sections (often 0–2 sections)
    #    This is the “prompt bias” part, but applied sparingly.
    improved_segments: list[dict[str, Any]] = []
    for seg in segments:
        improved_segments.append(dict(seg))

    # Index segments by time to allow replacement
    def replace_segments_in_window(start_s: float, end_s: float, new_segments: list[dict[str, Any]]):
        nonlocal improved_segments
        kept = [s for s in improved_segments if not (float(s["start"]) >= start_s and float(s["end"]) <= end_s)]
        kept.extend(new_segments)
        kept.sort(key=lambda s: (float(s.get("start", 0.0)), float(s.get("end", 0.0))))
        improved_segments = kept

    for a in section_assignments:
        if a["match_score"] >= retx_threshold:
            continue

        sec: Section = a["section"]
        bid: str = a["lyric_block_id"]
        prompt = (
            "Expected lyrics for this section. Transcribe matching wording closely:\n"
            f"{lyric_blocks[bid].strip()}\n"
        )

        t0, audio_slice = _slice_audio(audio, sr, sec.start_s, sec.end_s, pad_s=0.25)
        r = model.transcribe(audio_slice, batch_size=batch_size, initial_prompt=prompt)

        new_segs = []
        for s in r.get("segments", []):
            s = dict(s)
            s["start"] = float(s["start"]) + t0
            s["end"] = float(s["end"]) + t0
            s["prompt_block_id"] = bid
            s["prompt_match_score"] = a["match_score"]
            new_segs.append(s)

        replace_segments_in_window(sec.start_s, sec.end_s, new_segs)

    # 4) Align ONCE (word timestamps) using the final/improved segments
    model_a, metadata = whisperx.load_align_model(language_code=base["language"], device=device)
    aligned = whisperx.align(improved_segments, model_a, metadata, audio, device, return_char_alignments=False)

    return {
        "language": base.get("language"),
        "section_assignments": section_assignments,
        "segments": aligned.get("segments", []),
    }
```