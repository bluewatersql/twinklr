# P2P-T5 — Preview render client

Phase: 2P (Creative Quality, Measured) · Lane: E (evaluation harness, parallel) · Executor: sonnet · Verifier: opus · Depends on: P1P-T11

## Objective

Build the Python client for the xLights HTTP automation API that turns a generated
`.xsq` into a rendered video preview — `loadSequence → renderAll →
exportVideoPreview → closeSequence` — so P2P-T6 has frames to judge. Because video
export requires a windowed xLights and cannot run headless, the client also exposes
the deterministic `--fseqcmp` comparison as the CI-tier check that *can* run without
a GUI.

## Evidence & background

Findings: **D11 research (verified)**, **D2 (promoted)**, **M6b** (integration
surfaces).
Sources: `changes/twinklr-reactivation-review/reviews/reactivation-proposal.md` D11,
D2, §5; `.../reviews/modernization.md` M6b.

Quoted facts, all research-verified and accessed 2026-08-13:

> **Render**: xLights' `exportVideoPreview` is an implemented xlDo command
> (verified in source; upstream ships `BatchVideoExport.lua` doing exactly
> `openSequence→renderAll→exportVideoPreview→closeSequence`). Frame-stepped (faster
> than realtime), audio muxed in, fps = sequence frame rate. Constraint: needs a
> **windowed** xLights (`--headless` renders fseq only, no video) — fine on the
> owner's Mac; Linux CI unproven.

> **The real extension points: Lua scripting (Tools > Run Scripts; `RunCommand`
> drives xlDo) and the HTTP automation API** (xFade service, port 49913/49914, POST
> `/xlDoAutomation`; no authentication documented — flag as a local attack surface).
> Key commands: `importXLightsSequence` (with `mapmethod: file|auto|both` + `.xmap`/
> `.xjmap` hint files), `addEffect` (direct effect injection into the open sequence),
> `getModels`/`getViews` (read the user's real layout), `newSequence`, `renderAll`,
> `checkSequence`, media embed/extract.

> **D11 render constraint**: video export needs a windowed xLights — fine locally,
> unproven in Linux CI; the harness's CI tier can stop at deterministic
> fseq-compare (`--fseqcmp`) with video judging run locally/scheduled.

**Verified in this tree (2026-08-13): no xLights automation client exists.** Grep for
`xlDoAutomation`, `49913`, `exportVideoPreview`, `addEffect`, `getModels` across
`packages/` and `scripts/` returns nothing. This is greenfield code, not a repair.

Two named unknowns from M6b that this client is the vehicle for answering (P1P-T12
owns the acceptance test; this client is what it drives):

> UNVERIFIED: whether a bare `.xsq` without `xlights_rgbeffects.xml` imports (docs
> state the requirement only for the zip path) — Stage 4 empirical test.

> **Version stamps: documented cutoff is pre-2020 only (warning, not rejection;
> introduced 2026.04)** — "2024.10" is acceptable today; the boundary can ratchet, so
> update stamps anyway (free). UNVERIFIED: treatment of synthetic/unknown stamp
> values.

## Current behavior

Nothing in the repository talks to a running xLights. Delivery is file-based only:
P1P-T11 ships `.xtiming` + a fresh minimal `.xsq` + `.xmap`. Verification of a
rendered show is manual and visual.

## Target behavior

1. **An automation client** that POSTs xlDo commands to the local xLights HTTP
   service (default port 49913, fallback 49914) and returns typed results. Minimum
   command coverage for this task: `loadSequence`, `renderAll`, `exportVideoPreview`,
   `closeSequence`, plus `getModels` and `checkSequence` (cheap, and `getModels` is
   what P2P-T12 needs). Commands are modeled as typed request/response pairs, not
   dict-shaped calls.
2. **A preview-render workflow** — the four-command sequence, with the upstream
   `BatchVideoExport.lua` as the reference for ordering and parameters, returning the
   path of the exported video plus the sequence frame rate (the judge's sampling rate
   depends on it).
3. **Windowed-instance management on macOS.** Detect whether a windowed xLights is
   running and reachable; if not, fail with an actionable message rather than a
   connection traceback. Launching/quitting xLights automatically is optional and, if
   implemented, must be opt-in — never kill a running instance the user has work in.
4. **`--fseqcmp` deterministic comparison as the CI tier.** A byte/structural
   comparison of two `.fseq` outputs that runs without a GUI, exposed as the
   CI-runnable check. Everything video is `LOCAL-ONLY`.
5. **The unauthenticated-local-port caveat is documented** wherever the client is
   configured: the automation API has no documented authentication, so any local
   process can drive xLights while it is enabled. Document it; do not add
   authentication (not ours to add), and do not bind or proxy the port.
6. **Timeouts and failure semantics.** `renderAll` on a long song is slow; video
   export is frame-stepped but not instant. Every call takes an explicit timeout; a
   timeout is a typed error, and the client never leaves a sequence open on failure
   (best-effort `closeSequence` in a finally).

### Non-goals

- `addEffect` injection and the per-section regenerate loop — **P2P-T12**, which
  shares this client.
- The frame sampling, contact sheets, rubric, or any LLM call — **P2P-T6**.
- Running video export in CI (constraint: needs a windowed instance; Linux CI
  unproven — do not attempt).
- The xLights acceptance suite itself (P1P-T12); this client is the tool it uses.

## Implementation approach

Files/symbols:

- New client module under the repo's existing I/O boundary — place it beside the
  other external-service clients, not inside `sequencer/`. Follow the existing
  `httpx` usage conventions (httpx is already a direct dependency).
- **Do not add a second retry stack.** CC-6 records "2 OpenAI clients/4 retry stacks"
  as existing duplication debt; this client gets one, explicit, and documented.
- Close what you open: P2-M10 records leaked httpx pools ("never aclosed,
  placeholder base URLs") as an existing defect class — this client must be an async
  context manager (or expose an explicit `aclose`) and be tested for it.
- `--fseqcmp`: check whether an fseq reader already exists in `formats/`; reuse
  rather than writing a second parser (CC-6: "2 XSQ writers" is an existing lesson).

Sequencing constraints copied verbatim from the plan:

> - **Verification currency**: evidence in specs is from baseline `aa8d325`.
>   Executors must re-verify cited line numbers before editing (the tree will drift
>   as phases land) — specs cite symbol + file, with line numbers as hints only.
> - Nothing in this program authorizes pushes/PRs to remotes or paid API calls beyond
>   each spec's stated test budget; live-LLM and xLights-GUI tests are marked
>   `LOCAL-ONLY` in specs and excluded from CI.

## Acceptance criteria

1. The client issues typed `loadSequence`, `renderAll`, `exportVideoPreview`,
   `closeSequence`, `getModels`, `checkSequence` commands against the documented
   endpoint and parses their responses into typed results.
2. `render_preview(sequence_path) -> PreviewResult` performs the four-command
   workflow and returns the video path plus the sequence frame rate.
3. With no xLights running, every entry point fails with a single actionable error
   message naming the port and the windowed-instance requirement — no raw
   `ConnectException` reaches the caller.
4. A failure mid-workflow still closes the sequence (asserted with a fake transport).
5. `--fseqcmp` compares two `.fseq` files and reports equal/unequal with a diff
   summary, runs headless, and is the check wired into CI.
6. The unauthenticated-local-port caveat appears in the module docstring and in the
   user-facing documentation for the feature.
7. The client is closed properly (context manager or explicit `aclose`), asserted by
   a test.
8. `make validate` check-only forms pass. No test in the default suite requires a
   running xLights.

## Tests

1. `test_command_serialization` — each supported command produces the documented
   request body; pins the wire format against a fake transport.
2. `test_render_preview_workflow_order` — asserts the exact four-command order
   (`loadSequence → renderAll → exportVideoPreview → closeSequence`), matching
   upstream's `BatchVideoExport.lua`.
3. `test_sequence_closed_on_failure` — inject a failure at `exportVideoPreview`;
   assert `closeSequence` still issued.
4. `test_no_instance_error_message` — connection refused produces the actionable
   error.
5. `test_timeout_is_typed_error`.
6. `test_client_closes_transport`.
7. `test_fseqcmp_detects_difference` / `_reports_equal` — on two small committed
   fixture fseqs (or generated ones), headless.
8. **LOCAL-ONLY** `test_live_preview_export` — marked and excluded from CI; renders
   one short fixture sequence against a running xLights 2026.15 and asserts a video
   file appears with non-zero size. Document the manual run command in the module
   docstring.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest tests/unit -k "xlights or automation or fseq" -q
uv run pytest -m "not local_only" -q
```

LOCAL-ONLY (owner's Mac, windowed xLights 2026.15 running, API enabled):

```bash
uv run pytest -m local_only -k preview -q
```

No paid API calls in this task.

## Effort & risk

**M.** Main risk: the wire format. The command set is documented in xLights'
`documentation/xlDo Commands.txt` and demonstrated by `BatchVideoExport.lua`, but the
exact response shapes are only verifiable against a running instance — a client built
purely from docs may parse the wrong thing. Mitigation: build against the Lua
reference, keep response parsing lenient (typed on the fields we need, tolerant of
extras), and gate the merge on one LOCAL-ONLY live run whose captured
request/response pairs become the fake-transport fixtures. Second risk: the
no-authentication port is a real local attack surface — mitigated by documenting it
and never enabling or exposing it from Twinklr's side.
