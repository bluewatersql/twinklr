# Modernization Assessment (Stage 6)

_Authored 2026-08-13 from official-primary-source research (document-specialist, opus;
all URLs accessed 2026-08-13) plus orchestrator source checks at baseline `aa8d325`.
No dependency or lockfile changes are part of this review. Classifications:
REQUIRED | HIGH_VALUE | OPTIONAL | SPECULATIVE | NOT_RECOMMENDED._

## Headline

**No external blocker for Stage 4 live validation.** All five hardcoded model IDs
(`gpt-5.2`, `gpt-5-mini`, `gpt-4.1`, `gpt-4o-mini`, `gpt-image-1.5`) still serve as of
2026-08-13. Orchestrator grep confirmed no call site uses the already-retired
`-chat-latest`/`-codex` variants. Two models carry hard retirement deadlines that the
remediation roadmap must respect.

Sources: developers.openai.com/api/docs/{models,deprecations,pricing,guides/structured-outputs},
pypi.org (openai, torch, whisperx, pyannote.audio, pydantic, ruff, mypy, pytest),
github.com/{openai/openai-python,m-bain/whisperX,asg017/sqlite-vec,astral-sh/uv},
xlights.org/releases + release notes, devguide.python.org/versions. Access date for
all: 2026-08-13.

## M1. Model retargeting — REQUIRED (USER_MANDATED; hard deadlines)

| Current (code) | Status | Deadline | Target |
|---|---|---|---|
| `gpt-5.2` (default, 29 sites) | serving, "previous frontier" | none | **`gpt-5.6-terra`** default; `gpt-5.6-sol` only where evaluation proves quality-critical |
| `gpt-5-mini` (judge) | deprecated | **2026-12-11** | `gpt-5.6-terra` (official) or `gpt-5.6-luna` (cost-analogue judge, $0.20/$1.20 per 1M) |
| `gpt-image-1.5` (image client) | deprecated | **2026-12-01** | `gpt-image-2` |
| `gpt-4.1`, `gpt-4o-mini` | serving, no deadline | — | opportunistic (`terra`/`luna`) |

Economics (per 1M tokens, standard tier): gpt-5.2 $1.75/$14.00; gpt-5.6-terra
$2.00/$12.00 (output *cheaper* than incumbent); gpt-5.6-sol $5.00/$30.00 (≈2–3×);
gpt-5.6-luna $0.20/$1.20. Context expands 400K→1.05M on 5.6.

**Behavioral trap:** GPT-5.6 defaults `reasoning.effort=medium`; gpt-5.2 defaults to
none. A bare string swap silently adds reasoning-token cost and latency — the retarget
MUST set `reasoning.effort` explicitly per agent role. Remediation should also move
model IDs from 29 hardcoded sites into configuration (they are already configurable via
`AgentConfig.model` defaults — consolidate; note phase-1/3 finding: most of that
config surface is currently unwired).

**Cache-interaction (verified)**: model IDs ARE in every LLM stage's cache key, so the
retarget cannot serve stale cached plans — gate cleared. But prompt-pack content is in
NO key; once cross-run cache reuse is fixed (P1-F4), any prompt edit silently serves
stale plans — land prompt-content hashing in the same change as the session-ID fix
(see verification.md cache-fingerprint addendum).

## M2. Structured outputs migration — HIGH_VALUE (sequenced with M1)

The Responses API's strict structured outputs (`text.format: {"type":"json_schema",
"strict":true}`; SDK `client.responses.parse(text_format=PydanticModel)`) is the
officially recommended replacement for the `json_object` mode Twinklr uses. It would
replace the client-side schema-repair loop (≤5 retries/agent) with server-side
enforcement, shrinking the retry surface to refusal/truncation/content-filter cases.

Real refactor, not a flag flip — strict-mode constraints force model changes: all
fields required (Optional→`X | null`), `additionalProperties:false` everywhere, object
root only, no `allOf`; ceilings (5000 properties, 10 nesting levels, 1000 enum values)
must be checked against the choreography schemas. `json_object` mode is not deprecated,
so this is value-driven, not forced. UNVERIFIED (cheap Stage 4 live test): whether
`gpt-5.6-*` accepts `json_object` at all — test before retargeting without M2.

## M3. ML chain coordinated bump — HIGH_VALUE (single coordinated change)

Most stale area. Current whisperx (3.8.6) pins `torch~=2.8.0` — so the target is
**torch/torchaudio 2.8.x** (not the locked 2.4.0, and not latest 2.13, which whisperx
forbids). Requires **pyannote-audio 3.3.2 → 4.x (major; API breakage risk concentrates
here — the repo's diarization module is currently orphaned, which lowers the cost)**,
plus new whisperx deps (ctranslate2≥4.5, faster-whisper≥1.2, transformers≥4.48,
torchcodec, triton[linux-only]).

**Python version:** the 3.12-only constraint no longer holds externally — whisperx
supports `>=3.10,<3.14`; torch/pydantic support 3.13+. Python 3.12 is now
security-only (no new binaries). Recommend **3.12 → 3.13** as part of this bump;
supersedes `memories/constraints/python-3.12-only.md` (update at closeout with
provenance). 3.14 remains blocked by whisperx.

## M4. OpenAI SDK 3.x — OPTIONAL, defer

3.0.0 released **2026-08-12 (yesterday)**; lock has 2.16.0. Breaking change is the
HTTPX2 default client; Twinklr never injects a custom `http_client` into the OpenAI SDK
(orchestrator grep — httpx use is Twinklr's own audio-API layer, and httpx is a direct
dependency). Low risk but zero soak time: pin latest 2.x for reactivation; adopt 3.x
as a separate later item.

## M5. Tooling — OPTIONAL

pydantic 2.12.5→2.13.4 (minor; no v3 exists — no migration cliff). uv 0.12.3 already
current. ruff 0.15→0.16 (minor; new rules will fire). **mypy 1.19→2.3 is a major bump
that will surface a wave of new errors — defer as its own item; not a reactivation
blocker.** pytest 9.0.2→9.1.1 trivial.

## M6. xLights alignment — REQUIRED (empirical) + strategic input

Current xLights: **2026.15** (2026-08-04, ~10–20-day cadence). Twinklr's hardcoded
sequence stamps ("2024.10"/"2024.01") are ~2 years / ~40 releases old. No separate
.xsq format version exists — evolution tracks app releases; 2026 changes were additive
(embedded images 2026.03, relative paths 2026.04, face definitions 2026.14).
UNVERIFIED and untestable from docs: whether 2026.15 opens a "2024.10"-stamped file —
**Stage 4 empirical test: generate and open in current xLights.**

Strategic (feeds Stage 2): xLights now ships first-party AI plumbing — AI Services
(ChatGPT/Generic-OpenAI/Ollama, model dropdowns, 2026.11), AI image generation
(2026.03), stem-aware "Generate AI Lyrics" with HTDemucs separation (2026.11). No
built-in full-song choreography generation found — Twinklr's thesis space is still
open, but the host now owns LLM plumbing + stem-aware audio, narrowing the moat and
overlapping parts of Twinklr's audio-analysis value.

## M6b. xLights integration surfaces (Stage 2 follow-up research, access date 2026-08-13)

Sources: manual.xlights.org (services, import, tools, timing-tracks), xLights GitHub
`documentation/xlDo Commands.txt` + `Lua Scripting.md`, xlights.org/2026-04-released.

- **AI Services layer is configuration-extensible only** (providers: ChatGPT, Claude,
  Gemini, Generic-OpenAI with arbitrary Base URL, Ollama, Apple Intelligence) and
  scoped to palettes/images/import-mapping — **no choreography/effect-generation
  hook**. Not a Twinklr entry point.
- **The real extension points: Lua scripting (Tools > Run Scripts; `RunCommand` drives
  xlDo) and the HTTP automation API** (xFade service, port 49913/49914, POST
  `/xlDoAutomation`; no authentication documented — flag as a local attack surface).
  Key commands: `importXLightsSequence` (with `mapmethod: file|auto|both` + `.xmap`/
  `.xjmap` hint files), `addEffect` (direct effect injection into the open sequence),
  `getModels`/`getViews` (read the user's real layout), `newSequence`, `renderAll`,
  `checkSequence`, media embed/extract.
- **Effect import accepts xLights donor sequences** targeting the currently open
  sequence, carrying effects + timing tracks; models must pre-exist in the view;
  mapping is the friction (mitigated by shipping `.xmap` or using AI/auto mapping).
  UNVERIFIED: whether a bare `.xsq` without `xlights_rgbeffects.xml` imports (docs
  state the requirement only for the zip path) — Stage 4 empirical test.
- **Timing tracks import standalone as `.xtiming`** — a mapping-free minimum-viable
  deliverable for Twinklr's audio analysis alone.
- **Version stamps: documented cutoff is pre-2020 only (warning, not rejection;
  introduced 2026.04)** — "2024.10" is acceptable today; the boundary can ratchet, so
  update stamps anyway (free). UNVERIFIED: treatment of synthetic/unknown stamp values.

**Three escalating integration options for Stage 8**: (1) `.xtiming`-only deliverable
(trivial, no mapping); (2) minimal `.xsq` + shipped `.xmap`, manually or API-triggered
import (Stage 2's contract, de-risked); (3) direct `addEffect` injection against
`getModels` output — inverts the integration from "export and hope" to "drive the host
app", eliminating mapping at the root; requires xLights running with the API enabled.

## M7. sqlite-vec extra — REMOVE (NOT_RECOMMENDED to keep)

Declared as the `fe` extra, never imported anywhere. Upstream is healthy but pre-v1
("expect breaking changes"). Carrying an unused optional dep on a pre-v1 library is
pure liability — drop the extra; re-add pinned if vector search is actually built.

## Recommended sequencing (feeds Stage 8 roadmap)

1. M1 model retarget with explicit `reasoning.effort` + model-ID configuration cleanup
   (deadline-driven: Dec 1 / Dec 11, 2026).
2. M2 structured-outputs migration (with M1; after the `json_object`-on-5.6 live test).
3. M3 ML chain bump + Python 3.12→3.13 (coordinated, single change; pyannote 4.x is
   the risk center).
4. M6 xLights stamp update after the Stage 4 empirical acceptance test.
5. M7 drop sqlite-vec extra (trivial).
6. M4 openai 3.x and M5 mypy 2.x as separate soak-then-adopt items.
