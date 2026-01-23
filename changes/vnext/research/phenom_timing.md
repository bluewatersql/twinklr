# Phase 3 (Singing Decor) – Phoneme/Viseme Timing Options (v0 + future)

Goal: approximate **phoneme-level timing** (really: **viseme timing**) to drive singing decor.

---

## Option 1 (v0): WhisperX-only (fewer moving parts)
Use WhisperX for:
- **word timestamps** (alignment step)
- optionally **char alignments** for finer granularity within words (`return_char_alignments=True`)
Then:
- convert each word → **phonemes** (ARPAbet) via a lightweight G2P (e.g. `g2p_en` or CMUdict)
- distribute a word’s time window across its phonemes (optionally weighted by vowel/consonant)
- map phonemes → visemes and smooth (min-hold + merge tiny bursts)

**Pros**
- Keeps stack minimal (you already use WhisperX)
- Stable enough for v0 visuals
- No extra “phoneme recognizer” model

**Cons**
- Phoneme timing is an approximation (chars/word window ≠ true phones)
- Singing can deviate from canonical pronunciation

**Best for**
- v0 singing decor that “looks right” with smoothing + snapping

---

## Option 2 (future): Add a phoneme recognizer (Allosaurus)
Run Allosaurus to get **phone timestamps** directly from audio.
Then map phones → visemes and smooth.

**Pros**
- Direct phone timing, no lyrics required
- Good fallback when lyrics are missing/dirty

**Cons**
- Another model + dependency + phone-set mapping
- Singing accuracy varies; still needs smoothing

**Best for**
- v1/v2 as a second pass / fallback path

---

# v0 Sample (WhisperX → words/chars → phoneme-window → visemes)

## Dependencies
- whisperx
- torch
- (optional) g2p_en  # ARPAbet-ish phonemes
- numpy

## Data contracts (minimal)
- Input: audio path + (optional) canonical lyric text
- Output: list of viseme events: {viseme, start_s, end_s, confidence, source}

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import whisperx

try:
    from g2p_en import G2p
except ImportError:  # allow running without G2P installed
    G2p = None  # type: ignore[assignment]


@dataclass(frozen=True)
class VisemeEvent:
    viseme: str
    start_s: float
    end_s: float
    confidence: float
    source: str  # "whisperx"


# Minimal ARPAbet-ish phoneme → viseme mapping (expand later)
_PHONEME_TO_VISEME: dict[str, str] = {
    # vowels (very rough buckets)
    "AA": "A", "AE": "A", "AH": "A", "AO": "O", "AW": "O", "AY": "A",
    "EH": "E", "ER": "R", "EY": "E", "IH": "I", "IY": "I",
    "OW": "O", "OY": "O", "UH": "U", "UW": "U",
    # consonants (rough)
    "P": "BMP", "B": "BMP", "M": "BMP",
    "F": "FV", "V": "FV",
    "TH": "TH", "DH": "TH",
    "T": "TD", "D": "TD", "S": "SZ", "Z": "SZ",
    "K": "KG", "G": "KG", "NG": "KG",
    "CH": "CHJ", "JH": "CHJ", "SH": "SH", "ZH": "SH",
    "L": "L", "R": "R",
    "N": "N", "Y": "Y", "W": "W", "HH": "H",
}


def _to_viseme(phoneme: str) -> str:
    # strip stress markers like "AH0" -> "AH"
    base = "".join(ch for ch in phoneme if not ch.isdigit())
    return _PHONEME_TO_VISEME.get(base, "REST")


def _g2p_word(word: str) -> list[str]:
    if G2p is None:
        return []  # no G2P installed
    g2p = G2p()
    phones = [p for p in g2p(word) if p.isalpha() or any(ch.isdigit() for ch in p)]
    # filter out spaces / punctuation tokens g2p_en may emit
    return [p for p in phones if any(ch.isalpha() for ch in p)]


def _split_word_window_to_phonemes(word_start: float, word_end: float, phonemes: list[str]) -> list[tuple[str, float, float]]:
    if not phonemes:
        return []
    dur = max(0.0, word_end - word_start)
    if dur == 0:
        return []
    step = dur / len(phonemes)
    out: list[tuple[str, float, float]] = []
    t = word_start
    for ph in phonemes:
        out.append((ph, t, min(word_end, t + step)))
        t += step
    return out


def whisperx_visemes_v0(
    audio_file: str,
    *,
    device: str = "cpu",
    compute_type: str = "int8",
    model_name: str = "large-v3",
    batch_size: int = 8,
    use_char_alignments: bool = False,
) -> list[VisemeEvent]:
    # 1) Transcribe
    model = whisperx.load_model(model_name, device=device, compute_type=compute_type)
    audio = whisperx.load_audio(audio_file)
    base = model.transcribe(audio, batch_size=batch_size)

    # 2) Align for word timestamps (and optional char alignments)
    model_a, metadata = whisperx.load_align_model(language_code=base["language"], device=device)
    aligned: dict[str, Any] = whisperx.align(
        base["segments"],
        model_a,
        metadata,
        audio,
        device,
        return_char_alignments=use_char_alignments,
    )

    # 3) Convert word windows -> phoneme windows -> visemes
    events: list[VisemeEvent] = []
    for seg in aligned.get("segments", []):
        for w in seg.get("words", []):
            w_text = str(w.get("word", "")).strip().strip("'\"")
            w_start = float(w.get("start", 0.0))
            w_end = float(w.get("end", 0.0))

            # (Optional) if you enabled char alignments, you can refine w_start/w_end or
            # distribute based on char timings here. For v0 we keep it simple.
            phonemes = _g2p_word(w_text)
            for ph, ps, pe in _split_word_window_to_phonemes(w_start, w_end, phonemes):
                vis = _to_viseme(ph)
                events.append(VisemeEvent(viseme=vis, start_s=ps, end_s=pe, confidence=0.6, source="whisperx"))

    # 4) Minimal smoothing placeholder (you will likely do this in your own module)
    # - merge adjacent same-viseme
    merged: list[VisemeEvent] = []
    for e in sorted(events, key=lambda x: (x.start_s, x.end_s)):
        if merged and merged[-1].viseme == e.viseme and e.start_s <= merged[-1].end_s + 0.02:
            prev = merged[-1]
            merged[-1] = VisemeEvent(prev.viseme, prev.start_s, max(prev.end_s, e.end_s), min(prev.confidence, e.confidence), prev.source)
        else:
            merged.append(e)

    return merged


if __name__ == "__main__":
    evts = whisperx_visemes_v0("path/to/song.mp3", device="cpu", compute_type="int8", use_char_alignments=False)
    for e in evts[:20]:
        print(e)
```