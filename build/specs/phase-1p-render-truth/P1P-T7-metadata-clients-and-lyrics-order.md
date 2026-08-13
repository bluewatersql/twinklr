# P1P-T7 — Metadata clients + lyrics order

Phase: 1P (Render Truth) · Lane: A (audio truth, parallel to R) · Executor: opus · Verifier: opus · Depends on: P0-T4

## Objective

Make song identification and lyric resolution work at all. Today both metadata clients
raise `TypeError` on their first parser line for every call — a 100% failure rate reported
to the user as "no match found" — and the analyzer's parallelization structurally skips
the two authoritative lyrics providers, letting ASR outrank synced lyrics. This task fixes
both, and lands the MusicBrainz rate limiter in the same change because fixing AcoustID
alone converts a dormant ToS violation into a live one.

**The metadata-client fix and the MusicBrainz rate limiter land together. This is a hard
constraint (see "Sequencing constraints").**

## Evidence & background

Findings: **SF-3** = **P1-F1** + **P2-M3** + **P2-F13**; **SF-2** = **P2-M1** + **P2-F14**;
plus **P1-F2** (the counterfactual client tests).

Line numbers are hints from baseline `aa8d325`. Re-verify before editing.

### 1. Both metadata clients fail unconditionally (P1-F1, HIGH, mechanism reproduced empirically). Verbatim:

> `AsyncApiClient.get` returns `httpx.Response` (`api/http/client.py:622-635` → `557`);
> decoding requires `client.json(resp)` (`client.py:652-690`). Both audio clients pass the
> `Response` object directly into a dict-expecting parser:
> `api/audio/acoustid.py:84-90` → `_parse_response` → `acoustid.py:112` (`if "status" not in
> data`); `api/audio/musicbrainz.py:90-97` → `_parse_recording` → `musicbrainz.py:119`
> (`if "id" not in data or "title" not in data`). `httpx.Response` (0.28.1, `uv.lock:597-598`)
> defines no `__contains__`, `__iter__`, or `__getitem__` — verified by reading the class
> body, which contains only `__init__`, `__repr__`, `__getstate__`, `__setstate__`. The `in`
> test raises `TypeError`, caught by the catch-all at `acoustid.py:96-97` /
> `musicbrainz.py:103-104` and re-raised as `AcoustIDError` / `MusicBrainzError`, presenting to
> the user as "no match found". Root cause is `http_client: Any` (`acoustid.py:41`,
> `musicbrainz.py:49`) defeating mypy. The sibling lyrics providers use the API correctly
> (`lyrics/providers/lrclib.py:64-65`, `genius.py:72-73`).

> **Three verifier refinements.** (1) *Not fully silent* — `MetadataPipeline` logs at WARNING
> and attaches a `warnings` list to the returned bundle … The deception lies in the message's
> content, not its absence: "provider lookup failed" is indistinguishable from a network or
> credential fault and points debugging away from the type error. (2) *MusicBrainz is
> unreachable today* — MBIDs are collected only from AcoustID candidates
> (`audio/metadata/pipeline.py:154-163`), so with AcoustID failing `_query_musicbrainz` is
> never called. **Fix both in one change**: repairing AcoustID alone converts a dormant
> identical defect into a live one. (3) *Dead-docs class* — a fourth instance of phase 7's
> **P7-M2**; `docs/user-guide.md` instructs users to enable AcoustID.
>
> *Fix:* call `self.http_client.json(response)` in both clients; replace `Any` with the real
> type so the compiler holds the contract.

Re-verified in the current tree: `acoustid.py:41` is `def __init__(self, api_key: str | None, http_client: Any)`;
`:84` is `response_data = await self.http_client.get(`; `:90` is
`return self._parse_response(response_data)`; `:99` is
`def _parse_response(self, data: dict[str, Any]) -> AcoustIDResponse:`. `musicbrainz.py:49`
is `def __init__(self, http_client: Any, user_agent: str | None)` and `:90` is the same
`await self.http_client.get(` shape.

### 2. The latent ToS violation the fix would make live (P2-F13, verbatim):

> MusicBrainz's documented 1 req/sec, no-concurrent-requests policy is acknowledged but not
> enforced, and `metadata/pipeline.py` contains code that would fire concurrent MBID lookups
> — **but this path is currently UNREACHABLE**: AcoustID's own `_parse_response` raises
> `TypeError` on every call (phase 1's P1-F1), so no real MBIDs ever reach the
> `asyncio.gather`. Latent, not live. Becomes live the moment P1-F1 is fixed unless pacing
> lands in the same change.

And from phase 2 §4, verbatim:

> MusicBrainz's documented 1 req/sec, no-concurrent-requests policy is acknowledged in code
> comments (`musicbrainz.py:6-9,33-35`) but not enforced by the framework HTTP client
> or by `metadata/pipeline.py:161-164`'s `asyncio.gather(*mb_tasks)`. … Related config fields
> (`musicbrainz_rate_limit_rps`, `musicbrainz_timeout_s`, `http_max_retries`,
> `http_timeout_s`, `http_circuit_breaker_threshold` — `config/models.py:315-323`) are
> declared and unread anywhere in `core/audio/` or `core/api/`.

Re-verified: `audio/metadata/pipeline.py:163-164` is
`mb_tasks = [self._query_musicbrainz(mbid, warnings) for mbid in mbids_to_query]` /
`mb_results = await asyncio.gather(*mb_tasks)`.

### 3. The lyrics gating inversion (P2-M1, HIGH). Verbatim:

> `_build_song_bundle`'s parallel metadata+lyrics extraction passes `metadata_bundle=None`
> into the first lyrics pass; with WhisperX enabled the first pass resolves non-`SKIPPED`
> via ASR before the metadata-aware retry can fire, so LRCLib/Genius (the pipeline's own
> declared higher-priority sources) are **never actually consulted** when metadata would
> have resolved — an inversion of the documented fallback order under normal parallel
> execution, not just an edge case. With WhisperX off, the cost is a fully redundant second
> lyrics-extraction pass instead.
>
> Evidence: `analyzer.py:274-289` (parallel gather with `None` metadata on first pass),
> `:380-395` (artist/title resolution from metadata), retry condition at `:282-288` gated on
> `stage_status == SKIPPED`.
>
> Fix: resolve metadata before starting lyrics extraction, or restructure the retry
> condition to also cover "resolved via lower-priority ASR fallback".

Re-verified: `analyzer.py:276` is `metadata_bundle, lyrics_bundle = await asyncio.gather(`
and `:283-284` gate the retry on
`lyrics_bundle.stage_status == StageStatus.SKIPPED and metadata_bundle.stage_status != StageStatus.SKIPPED`.

### 4. The counterfactual client tests (P1-F2, HIGH). Verbatim:

> `tests/unit/api/audio/test_acoustid_client.py:17-22,41-58` sets
> `mock_http_client.get.return_value = <dict>`; the MusicBrainz test does the same. The suite
> is green *because* the fake is counterfactual — this is the mechanism by which P1-F1 shipped
> and survived. Contrast `tests/unit/api/http/test_client_async.py:25`, which correctly uses
> `httpx.MockTransport`. *Fix:* build audio-client fakes from `AsyncApiClient`'s real
> signature or from `MockTransport`; add one contract test asserting `AsyncApiClient.get`
> returns `httpx.Response`.

Phase 2 §5 corroborates, verbatim:

> **AcoustID/MusicBrainz clients are tested exclusively against mocks** … the mocked tests
> never would have caught the real `TypeError` bug, since the mocks bypass
> `_parse_response`'s actual input shape entirely — a concrete example of mock-only
> testing masking a live defect.

### 5. Related, in scope only as far as gating order (P2-F14, narrowed). Verbatim:

> WhisperX transcription is never gated on vocal presence (`vocal_segments` used only for a
> post-hoc quality metric); narrowed because WhisperX defaults **off** and
> `vocal_presence_pct` is already surfaced to the downstream lyrics agent — the gap is
> "nothing acts on an available signal," and any fix is blocked on P2-M2 (vocal detector
> itself is time-misaligned).

**P2-M2 is fixed in P1P-T8, not here.** Do not add vocal-presence gating in this task; the
signal it would gate on is still misaligned until T8 lands. Lane A is serial (T7 → T8) so
the gating can be revisited afterwards if wanted.

## Current behavior

- Every AcoustID call raises `TypeError` inside `_parse_response`, is caught, and is
  re-raised as `AcoustIDError`; the user sees "no match found" plus a generic
  "provider lookup failed" warning.
- MusicBrainz has the identical defect but is never reached, because MBIDs only come from
  AcoustID results.
- `metadata/pipeline.py` fans MBID lookups out under `asyncio.gather`, violating
  MusicBrainz's documented 1 req/s, no-concurrency policy the moment AcoustID works.
- `musicbrainz_rate_limit_rps` and four sibling pacing/timeout config fields are declared
  and never read.
- The analyzer runs metadata and lyrics concurrently, handing `metadata_bundle=None` to
  the first lyrics pass; the metadata-aware retry only fires when lyrics came back
  `SKIPPED`, so an ASR result suppresses the retry and LRCLib/Genius are never consulted.
  With WhisperX off, lyrics resolve twice per analyze.
- Both client test modules feed `dict`s where production feeds `httpx.Response`.

## Target behavior

1. Both clients decode via the HTTP client's `json(...)` step before parsing. `http_client`
   is typed, not `Any`, so mypy holds the contract.
2. A failed provider lookup reports a message that distinguishes a parse/contract failure
   from a network or credential failure.
3. MusicBrainz requests are paced to at most 1 request/second with no concurrent requests,
   honoring `musicbrainz_rate_limit_rps` (which gains its first reader). The
   `asyncio.gather` fan-out over MBIDs is replaced by paced sequential execution or a
   limiter that guarantees the same.
4. Metadata resolves **before** lyrics extraction begins, or the retry condition covers
   "resolved via lower-priority ASR fallback" — either way, LRCLib/Genius are consulted
   whenever metadata could identify the track, and lyrics are resolved **once**.
5. Client tests exercise the real contract (`httpx.MockTransport` or fakes built from
   `AsyncApiClient`'s real signature), plus one contract test asserting
   `AsyncApiClient.get` returns `httpx.Response`.

**Non-goals.** No vocal-presence gating (blocked on P1P-T8). No new providers. No
`enable_*` flag/env-binding redesign (P2-M11 — that is a config task, not this one). Do
not close the leaked `httpx` pools (P2-M10) here unless it falls out for free.

## Implementation approach

Files/symbols to touch:
- `packages/twinklr/core/api/audio/acoustid.py` — `__init__` typing (`:41`), the
  `get`→`_parse_response` seam (`:84-90`), the catch-all (`:96-97`).
- `packages/twinklr/core/api/audio/musicbrainz.py` — same shape (`:49`, `:90-97`,
  `:103-104`), plus the rate-limit comments at `:6-9,33-35` that document the unenforced
  policy.
- `packages/twinklr/core/audio/metadata/pipeline.py` — the MBID fan-out (`:154-164`) and
  the warning messages (`:116,133,150,178-188`).
- `packages/twinklr/core/config/models.py` — `musicbrainz_rate_limit_rps` and siblings
  (`:315-323`) gain readers.
- `packages/twinklr/core/audio/analyzer.py` — the parallel gather (`:274-289`) and the
  retry condition (`:282-288`).
- `tests/unit/api/audio/test_acoustid_client.py`, `test_musicbrainz_client.py` — rewrite
  the doubles.

Design decisions already made (do not relitigate):
- **Type the client.** The review names `http_client: Any` as the root cause; replacing the
  annotation is part of the fix, not a nicety.
- **The limiter is enforced where the requests are issued**, not documented in a comment.
  Prefer a small shared paced-request helper over per-call `sleep`s, so a future second
  MusicBrainz call site inherits it.
- **Fix the lyrics order by resolving metadata first** (the review's first-listed remedy)
  unless that measurably serializes an otherwise-parallel stage in a way that matters;
  if the retry-condition variant is chosen instead, it must also eliminate the
  double-resolution when WhisperX is off.
- **Rewriting the client tests is part of the fix**, mirroring P4-M4's rule for the render
  path: a fix that leaves counterfactual tests green has not fixed the contract.

Sequencing constraints (copied verbatim from `build/plan/00-overview.md`):

> Metadata client fix + MusicBrainz rate limiter land **together** (P1P-T7).

> `make validate` equivalents (check-only forms until P0-T4 lands the guard) must pass
> at every merge; golden tests (once P1P-T1 exists) must pass for any lane touching
> render/export code.

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases land)
> — specs cite symbol + file, with line numbers as hints only.

From `build/plan/02-phase-1p-render-truth.md`:

> **Lane A (audio truth, parallel to R — files in `core/audio/` + `api/`)**: T7 → T8.

## Acceptance criteria

- [ ] Neither `acoustid.py` nor `musicbrainz.py` passes an `httpx.Response` into a
      dict-typed parser; both call the client's `json(...)` decode step. Verifiable by
      reading the two call sites.
- [ ] `http_client` is annotated with the real client type in both clients; `mypy` passes
      and would now catch a recurrence.
- [ ] A test drives **both** clients through `httpx.MockTransport` (or an equivalent real-
      signature fake) with a realistic provider payload and asserts a populated result —
      this test fails against the pre-fix code with `TypeError`.
- [ ] A contract test asserts `AsyncApiClient.get` returns `httpx.Response`.
- [ ] No `asyncio.gather` over MusicBrainz requests remains; a test asserts that N MBID
      lookups issue **sequentially** and that the elapsed pacing respects the configured
      rate (use a fake clock or an injected limiter — no real `sleep`-based slow test).
- [ ] `musicbrainz_rate_limit_rps` has a production reader.
- [ ] Provider-failure warnings distinguish parse/contract failures from transport
      failures.
- [ ] A test proves LRCLib/Genius are consulted when metadata identifies the track and
      WhisperX is enabled (today: structurally skipped).
- [ ] A test proves lyrics extraction runs **once** per analyze with WhisperX off (today:
      twice).
- [ ] `grep` shows no remaining `mock_http_client.get.return_value = {` (dict) pattern in
      `tests/unit/api/audio/`.
- [ ] `make validate` check-only equivalents pass.

## Tests

TDD: the `MockTransport` client test and the "LRCLib consulted" test both fail at
baseline; write them first.

| Test | Behavior pinned |
|---|---|
| `test_acoustid_parses_real_response_object` | The P1-F1 mechanism cannot return |
| `test_musicbrainz_parses_real_response_object` | Same, on the client that was unreachable |
| `test_async_api_client_get_returns_httpx_response` | The contract the doubles must honor |
| `test_musicbrainz_requests_are_sequential_and_paced` | P2-F13: no concurrent MB requests, ≥1 s spacing |
| `test_rate_limit_config_is_read` | `musicbrainz_rate_limit_rps` is no longer dead config |
| `test_lyrics_consults_authoritative_providers_when_metadata_resolves` | P2-M1 inversion fixed |
| `test_lyrics_resolved_once_when_whisperx_disabled` | P2-M1's double-resolution cost |
| `test_provider_failure_message_distinguishes_parse_from_transport` | The "deception" refinement in P1-F1 |

**Test budget:** zero live network calls. All provider payloads are recorded fixtures.
Any live-provider smoke test is **LOCAL-ONLY** and excluded from CI (AcoustID and Genius
both require keys; MusicBrainz is free but rate-limited and must not be hit from CI).

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .

uv run pytest tests/unit/api/audio -v
uv run pytest tests/unit/audio -v
uv run pytest tests/integration/audio -v

# defect-specific checks the verifier runs
grep -n "http_client: Any" packages/twinklr/core/api/audio/acoustid.py packages/twinklr/core/api/audio/musicbrainz.py   # expect: no match
grep -n "asyncio.gather" packages/twinklr/core/audio/metadata/pipeline.py                                               # expect: no match over MB tasks
grep -rn "musicbrainz_rate_limit_rps" packages/twinklr/core --include=*.py                                              # expect: a reader, not just the field
grep -rn "return_value = {" tests/unit/api/audio                                                                        # expect: no dict-for-Response doubles

# LOCAL-ONLY (not run in CI; requires ACOUSTID_API_KEY and network):
# uv run pytest tests/local/test_metadata_live.py -v -m local
```

## Effort & risk

**Effort: M.**

**Main risk: this is the change that makes real outbound requests start working.** The
moment it lands, a run with `enable_acoustid=true` contacts third-party services for the
first time in this codebase's history. Mitigation: the limiter lands in the same change
(the stated constraint); the user-agent string MusicBrainz requires is already declared
(`musicbrainz.py` `user_agent` argument) and must be verified non-empty; keep the
providers' `enable_*` defaults at `False` so nothing turns on implicitly.

**Second risk: resolving metadata before lyrics serializes two stages** that currently run
concurrently, adding wall-clock time to every analyze. Mitigation: measure it; if the cost
is material, take the retry-condition variant instead, which preserves concurrency — but
it must still eliminate the double resolution.

**Third risk: the rewritten client tests could re-encode a different wrong contract.**
Mitigation: build them from `httpx.MockTransport` against real recorded provider payloads,
and keep the `AsyncApiClient.get` contract test as the anchor.
