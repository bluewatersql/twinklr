# tests/vendor/nltk_data/

Vendored NLTK data resources needed to run the test suite offline. Wired up
by `tests/conftest.py`, which prepends this directory to `nltk.data.path`
before any test imports `g2p_en`/`nltk`.

## Contents

- `taggers/averaged_perceptron_tagger_eng/` — the `averaged_perceptron_tagger_eng`
  POS tagger (NLTK's [Averaged Perceptron
  Tagger](https://www.nltk.org/_modules/nltk/tag/perceptron.html)), fetched via
  `nltk.download('averaged_perceptron_tagger_eng')` from NLTK's public data
  repository (Apache-2.0 licensed data, redistributable). Used by
  `twinklr.core.audio.phonemes.g2p_service` (via `g2p_en` -> `nltk.pos_tag(...,
  lang="eng")`) for part-of-speech-disambiguated grapheme-to-phoneme
  conversion. Three plain-text JSON files, ~5.4MB total (`weights.json`,
  `classes.json`, `tagdict.json`) — no binary pickle.
- `corpora/cmudict/` — the CMU Pronouncing Dictionary, fetched via
  `nltk.download('cmudict')` (public domain). `g2p_en.G2p.__init__` loads
  this eagerly (`cmudict.dict()`) as its base pronunciation lookup before
  falling back to its own predictor for out-of-vocabulary words. Plain
  ASCII word-list text file, ~3.6MB — no binary pickle.

Note: `g2p_en` also probes at import time for the legacy, non-suffixed
`averaged_perceptron_tagger` resource (pre-NLTK-3.8 naming) and attempts
`nltk.download()` if absent. That attempt is *not* vendored here: it fails
silently offline (`nltk.download()` catches the connection error and
returns `False` without raising) and is never actually used at runtime —
`nltk.pos_tag(..., lang="eng")` (NLTK's current default) loads
`averaged_perceptron_tagger_eng` instead, which *is* vendored above.
Verified: `tests/unit/audio/phonemes/` passes with `HOME` redirected to an
empty temp dir and `HTTP_PROXY`/`HTTPS_PROXY` pointed at an unreachable
port (no network reachable, no pre-existing `~/nltk_data`).

## Re-fetching / updating

```bash
uv run python -c "import nltk; nltk.download('averaged_perceptron_tagger_eng', download_dir='tests/vendor/nltk_data')"
uv run python -c "import nltk; nltk.download('cmudict', download_dir='tests/vendor/nltk_data')"
# then: rm tests/vendor/nltk_data/corpora/cmudict.zip (keep only the extracted dir)
```

## Scope note

This vendoring is test-time only (see
`changes/twinklr-reactivation-review/build/specs/phase-0-foundation/P0-T2-structural-test-repair.md`'s
non-goals) — it does not change how production code
(`packages/twinklr/core/audio/phonemes/*`) locates NLTK data at runtime.
