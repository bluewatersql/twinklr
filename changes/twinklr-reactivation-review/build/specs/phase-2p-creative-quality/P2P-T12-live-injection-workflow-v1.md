# P2P-T12 — Live injection workflow v1 (D2)

Phase: 2P (Creative Quality, Measured) · Lane: W (workflow) · Executor: opus · Verifier: opus · Depends on: P2P-T2, P2P-T5 (spec sequencing places the lane after P2P-T4)

## Objective

Invert the integration: instead of exporting a file and hoping it maps, drive the
host app. Read the user's real layout with `getModels`, plan against it, and inject
effects into the open sequence with `addEffect` — plus a per-section regenerate
command, which is the actual iteration loop a hobbyist wants while working on their
own show.

## Evidence & background

Findings: **D2 (revised ranking — promoted)**, **M6b** (integration surfaces),
**P7-M1 / P7-F8** (the shipped CLI is correct only for the author's own display).
Sources: `changes/twinklr-reactivation-review/reviews/reactivation-proposal.md` D2,
§4 (M2), §2.3; `.../reviews/modernization.md` M6b; `.../reviews/verification.md`
"Phase 7".

### D2 quoted — why this is core, not premium-later

> **D2 — Delivery contract** *(revised ranking)*: fresh minimal `.xsq`+`.xmap` remains
> the file contract, `.xtiming` ships first — but **live injection
> (`getModels`→plan→`addEffect`) is promoted from "premium later" to a core M2/M3
> workflow**. v1 demoted it on a staffing argument (commercial lens); for a hobbyist
> iterating on their own show, regenerate-this-section against a running xLights is
> the best-fit interaction, and the same session provides D11's render surface.

### M6b quoted — the surfaces and the caveat

> - **The real extension points: Lua scripting (Tools > Run Scripts; `RunCommand`
>   drives xlDo) and the HTTP automation API** (xFade service, port 49913/49914, POST
>   `/xlDoAutomation`; no authentication documented — flag as a local attack surface).
>   Key commands: `importXLightsSequence` (with `mapmethod: file|auto|both` + `.xmap`/
>   `.xjmap` hint files), `addEffect` (direct effect injection into the open sequence),
>   `getModels`/`getViews` (read the user's real layout), `newSequence`, `renderAll`,
>   `checkSequence`, media embed/extract.

> **Three escalating integration options for Stage 8**: (1) `.xtiming`-only deliverable
> (trivial, no mapping); (2) minimal `.xsq` + shipped `.xmap`, manually or
> API-triggered import (Stage 2's contract, de-risked); (3) direct `addEffect`
> injection against `getModels` output — inverts the integration from "export and
> hope" to "drive the host app", eliminating mapping at the root; requires xLights
> running with the API enabled.

This task is option (3). P1P-T11 shipped options (1) and (2).

### The layout problem this solves (P7-M1, quoted)

> **P7-M1 (MED-HIGH, CONFIRMED)**: `cli/main.py:208` passes literal `fixture_count=4`
> into the planner prompt path (`stage.py:145` → `orchestrator.py:75`) while resolving
> the user's real fixture config three lines later — any non-4-fixture rig gets a
> planner told a false count on the only shipped path.

P1P-T11 makes the fixture config the CLI's input, killing the hardcode. This task goes
one step further: `getModels` reads the *actual* layout from the running instance, so
the plan is made against ground truth rather than a config file that may have drifted.

### Prerequisite from P2P-T5

The automation client, its windowed-instance management, and the unauthenticated-port
caveat all come from P2P-T5. **This task adds `addEffect` to that client and builds
the workflow on top; it does not build a second client.**

## Current behavior

- Delivery is file-based: `.xtiming`, plus a fresh minimal `.xsq` + `.xmap` (P1P-T11).
  The user imports and maps.
- Nothing reads the user's live layout. The planner is told about fixtures from
  configuration.
- There is no way to regenerate one section without regenerating and re-importing the
  whole show.

## Target behavior

1. **`getModels` → layout model.** Read the running instance's models (and
   `getViews` where useful), map them onto Twinklr's fixture/group concepts, and make
   the result the planning input. Where the live layout and the configured fixture
   config disagree, the live layout wins and the divergence is reported — a silent
   reconciliation here recreates P7-M1 in a new place.
2. **Plan against the real layout.** The MH planning path accepts the live layout as
   its rig description. Schema-v2 intents (P2P-T2) resolve against those fixtures'
   declared channels, so a rig without a colour channel drops colour intent with a
   recorded trace rather than emitting garbage.
3. **`addEffect` injection into the open sequence.** Rendered effects are injected
   directly. Requirements:
   - **Never touch the user's own work silently.** P5-F4's extension is the exact
     hazard: "add_effect appends Twinklr effects into the user's own layer 0
     interleaved with pre-existing effects, no overlap resolution." Injection must
     target an identifiable Twinklr layer/region, detect collisions with existing
     effects, and stop or ask rather than interleave.
   - **Idempotence.** Re-running the same injection replaces Twinklr's previous
     effects for that range rather than stacking a second copy.
   - **Dry run.** A mode that reports exactly what would be injected without issuing
     a write, because the target is the user's live, unsaved sequence.
4. **Per-section regenerate command.** `regenerate <section>` re-plans and re-injects
   one section against the open sequence — the hobbyist iteration loop D2 names as the
   best-fit interaction. It must be fast enough to be used repeatedly (cache the
   analysis; only the planning + injection for that section re-runs).
5. **The unauthenticated-local-port caveat is documented** in the command's help text
   and the user-facing docs, not only in code comments: enabling the automation API
   means any local process can drive xLights.
6. **Failure semantics**: a partial injection must be recoverable. If injection fails
   halfway, report exactly what was injected, and make the idempotent re-run the
   documented recovery path.

### Non-goals

- Display/group-planner injection (Phase 3 convergence).
- Replacing the file contract. `.xtiming` + fresh `.xsq`/`.xmap` remain the delivery
  contract; injection is an additional workflow.
- Saving the user's sequence on their behalf. Twinklr injects; the user saves.
- Authentication for the automation port (not ours to add).
- Asset/image generation (D13, Phase 3).

## Implementation approach

Files/symbols:

- P2P-T5's automation client — add `addEffect` (and `getViews` if not already
  present) as typed commands.
- CLI: the injection and per-section regenerate commands. Follow P1P-T11's CLI
  conventions (fixture config as input) rather than inventing a parallel entry point.
- The MH planning path — accepts a live layout as its rig description.
- The effect-serialization boundary: `addEffect` needs effect settings strings, which
  is exactly what `DmxSettingsBuilder`/`xsq_export` already construct for the file
  path. **Reuse them.** CC-6 records "2 XSQ writers" and "2 fresh emitters" as
  existing duplication debt with a real conflict (P5-M3: "fresh emitters also disagree
  on sequenceTiming (50ms vs 20ms), and the MH path applies no quantization at all
  while display snaps to 20ms"). A third serialization path would be a new instance of
  a known defect class.
- Documentation: user-facing docs for the workflow + the port caveat.

Sequencing constraints copied verbatim from the plan:

> - **Verification currency**: evidence in specs is from baseline `aa8d325`.
>   Executors must re-verify cited line numbers before editing.
> - `make validate` equivalents (check-only forms until P0-T4 lands the guard) must
>   pass at every merge; golden tests (once P1P-T1 exists) must pass for any lane
>   touching render/export code.
> - Nothing in this program authorizes pushes/PRs to remotes or paid API calls beyond
>   each spec's stated test budget; live-LLM and xLights-GUI tests are marked
>   `LOCAL-ONLY` in specs and excluded from CI.

Lane note from the phase doc: **Lane W (workflow): T12 (injection v1) after T4.**

## Acceptance criteria

1. `getModels` output is parsed into Twinklr's rig representation and drives planning;
   a divergence between the live layout and the configured fixture config is reported,
   not silently reconciled.
2. Effects are injected via `addEffect` into an identifiable Twinklr target; a
   collision with pre-existing user effects halts (or prompts) rather than
   interleaving. Asserted against a fake transport with a pre-populated sequence
   state.
3. Injection is idempotent: the same injection run twice leaves the sequence in the
   same state as running it once.
4. A dry-run mode reports the exact command sequence without issuing a write, verified
   by a fake transport that fails on any write.
5. `regenerate <section>` re-plans and re-injects exactly that section, leaving other
   sections untouched.
6. Effect settings strings sent via `addEffect` are produced by the **same** builder
   the file export uses — asserted by comparing an injected effect's settings string
   against the golden settings string for the same section.
7. The unauthenticated-local-port caveat appears in the command help and the
   user-facing docs.
8. A partial-failure run reports what was injected and documents the idempotent re-run
   as recovery.
9. `make validate` check-only forms pass; no default-suite test requires a running
   xLights.

## Tests

1. `test_getmodels_parsed_into_rig` — against a captured `getModels` response fixture.
2. `test_layout_divergence_is_reported`.
3. `test_injection_settings_match_golden_export` — criterion 6; the strongest
   guarantee that injection and file export cannot drift.
4. `test_injection_is_idempotent` — fake transport with sequence state.
5. `test_collision_with_user_effects_halts` — the P5-F4 guard.
6. `test_dry_run_issues_no_writes`.
7. `test_regenerate_section_touches_only_that_section`.
8. `test_partial_failure_reports_injected_set`.
9. **LOCAL-ONLY** `test_live_injection_round_trip` — against a running xLights
   2026.15 with a scratch sequence: inject one section, `renderAll`, confirm via
   `checkSequence` (and optionally P2P-T5's preview) that the effects exist. **Never
   run against a sequence the user cares about** — the test must create or require a
   scratch sequence and say so in its docstring.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest tests/unit -k "injection or getmodels or regenerate" -q
uv run pytest -m "not local_only" -q
uv run pytest -k golden -q
```

LOCAL-ONLY (owner's Mac, windowed xLights 2026.15 with the automation API enabled,
scratch sequence open):

```bash
uv run pytest -m local_only -k injection -q
```

Live-LLM budget for the regenerate loop's manual validation: **≤ 3 songs' worth of
section re-plans, ≤ $3.00**.

## Effort & risk

**M–L.** Main risk is the one the review already documented as a real corruption
vector: appending into the user's own layer with no overlap resolution. This task
writes into a live, possibly unsaved sequence, so the blast radius is the user's own
work rather than a generated file. Mitigations, all acceptance criteria: an
identifiable Twinklr target, collision detection that halts, idempotent re-injection,
and a dry run. Second risk: a third settings-string serialization path drifting from
the exporter — mitigated by criterion 6's golden comparison. Third risk: the
automation API's response shapes differing from what the client assumes — mitigated by
P2P-T5's captured fixtures and the LOCAL-ONLY round trip.

## Implementation handoff (2026-08-14)

Implementation is complete in the isolated P2P-T12 worktree and is ready for an
independent review. It has not been committed, self-approved, or exercised against a
live xLights instance or a paid model provider.

### Upstream API re-verification

The automation contract was re-verified on 2026-08-14 against primary upstream xLights
sources at master commit
[`5f48d23a8a9861440b2c1386a1cea0c51e753be5`](https://github.com/xLightsSequencer/xLights/commit/5f48d23a8a9861440b2c1386a1cea0c51e753be5):

- [`documentation/xlDo Commands.txt`](https://github.com/xLightsSequencer/xLights/blob/5f48d23a8a9861440b2c1386a1cea0c51e753be5/documentation/xlDo%20Commands.txt),
  blob `0edb85865edbbbba290072734c99f2e1e918d4b5`;
- [`src-ui-wx/automation/xLightsAutomations.cpp`](https://github.com/xLightsSequencer/xLights/blob/5f48d23a8a9861440b2c1386a1cea0c51e753be5/src-ui-wx/automation/xLightsAutomations.cpp),
  blob `cf993f95ec70623959cf4bb28e3b94c7a9352fac`.

Those sources confirm POST `/xlDoAutomation` on the documented local xFade service
ports 49913/49914; no authentication is documented. `getModels` returns names only,
so live names are authoritative while fixture DMX semantics come only from matching
configured models. `addEffect` accepts string fields `target`, `effect`, `settings`,
`palette`, `layer`, `startTime`, and `endTime`, creates missing layers, and reports
only `worked` (not a created effect ID). `getEffectIDs`, `getEffectSettings`, and
`deleteEffect` provide the read/delete seam used for ownership preflight and
replacement. The implementation has per-command undo capture but no multi-command
transaction. Consequently an ambiguous add/delete POST is never automatically
replayed.

### Delivered behavior

- `twinklr inject` and `twinklr regenerate <canonical-section-id>` keep one T5
  `XLightsAutomationClient` alive and pinned from the successful layout read through
  planning and mutation. A connection refusal can select the alternate documented
  port before pinning; later timeouts/read failures cannot fail over or replay on
  another xLights window.
- Separate `getModels` reads obtain live model and group names. Matching configured
  fixtures retain their deterministic channel/calibration data; missing configured
  models/groups and unknown live models are reported, and unknown channels are never
  guessed.
- T2's existing `XsqAdapter` and `DmxSettingsBuilder` path serializes every live DMX
  effect. No third effect-settings emitter was introduced.
- Layers starting at 99 are reserved for Twinklr, with every `XsqAdapter` relative
  layer preserved by adding 99. Before writes, every affected target/layer is read via
  `getEffectIDs` and `getEffectSettings` and compared with the sequence-keyed,
  artifact-local `.twinklr-live-ownership.json` manifest. Any overlapping effect not
  identified by that manifest halts before mutation. Full injection replaces all
  previously owned sections; section regeneration deletes/re-adds only that canonical
  section, including the valid case where re-planning produces no effects.
- Replacement is explicitly destructive for previously Twinklr-owned effects:
  confirmed old effect IDs are deleted before new effects are added. Dry run reports
  that exact ordered wire plan without writes. Identical runs are no-ops. Partial
  failures report the confirmed prefix and failed payload. An add whose response is
  lost is recorded as uncertain ownership so the next preflight can recognize either
  outcome without replaying the ambiguous POST.
- Twinklr never sends a save command. The user must inspect the reserved layers starting
  at 99 and save manually.
  Help, user docs, developer docs, and the owner-only harness all state the
  unauthenticated-local-port caveat.

### Exact implementation manifest

- `packages/twinklr/core/api/xlights/models.py`
- `packages/twinklr/core/api/xlights/client.py`
- `packages/twinklr/core/api/xlights/injection.py` (new)
- `packages/twinklr/core/api/xlights/__init__.py`
- `packages/twinklr/core/agents/sequencer/moving_heads/stage.py`
- `packages/twinklr/core/agents/sequencer/moving_heads/rendering_stage.py`
- `packages/twinklr/core/pipeline/definitions/moving_heads.py`
- `packages/twinklr/cli/main.py`
- `tests/unit/api/xlights/test_client.py`
- `tests/unit/api/xlights/test_injection.py` (new)
- `tests/unit/cli/test_live_injection_command.py` (new)
- `tests/unit/agents/sequencer/moving_heads/test_stage.py`
- `tests/local_only/test_live_injection.py` (new)
- `docs/user-guide.md`
- `docs/developer-guide.md`
- this specification handoff

### Test-first and verification evidence

The discriminating test-first checkpoint failed collection with
`ModuleNotFoundError: twinklr.core.api.xlights.injection`. After implementation:

- focused live-injection/CLI/stage/local-only selection: `27 passed, 1 skipped`;
- xLights client plus injection contracts after the disappearing-target hardening:
  `18 passed`;
- CLI/agent/MH sequencer regression selection: `475 passed, 2 skipped`;
- non-local repository suite before the final two hardening tests:
  `5063 passed, 25 skipped, 12 deselected`;
- golden selection after implementation: `74 passed, 8 skipped, 5020 deselected`;
- LOCAL-ONLY harness without opt-in: `1 skipped`;
- `ruff format --check`, `ruff check --no-cache`, and `mypy .`: passed (mypy checked
  709 source files);
- final full default suite, including this handoff: `5065 passed, 37 skipped`, with nine
  pre-existing `ProfileCorpusBuilder` deprecation warnings.

The four substantive `make validate` gates passed via their direct commands: formatting,
lint, type checking, and the full test suite. The wrapper target itself was intentionally
not invoked because it begins with `git diff`, while this execution brief prohibits all
git commands.

### Residual owner gate — not claimed

The only residual acceptance evidence is the deliberately skipped empirical xLights
2026.15 round trip. On the owner's Mac, open an expendable scratch sequence, ensure the
explicit model exists, enable the local automation API, and run:

```bash
TWINKLR_RUN_LIVE_XLIGHTS_INJECTION=1 \
TWINKLR_XLIGHTS_SCRATCH_SEQUENCE=/absolute/path/scratch.xsq \
TWINKLR_XLIGHTS_SCRATCH_MODEL='Dmx MH1' \
  uv run pytest tests/local_only/test_live_injection.py -m local_only -q
```

The harness compares `getOpenSequence.fullseq` with the exact opt-in scratch path before
mutation, adds one short layer-99 DMX effect, calls `renderAll`, and calls
`checkSequence`. It never saves. Do not run it against a valued sequence; discard the
scratch sequence and disable the unauthenticated local API afterward. This executor
made no live xLights or provider calls and does not claim this owner gate passed.

### Independent-verifier rejection remediation (2026-08-14)

The first independent verification correctly rejected the author handoff because it
flattened every `XsqAdapter` placement onto layer 99 and the generic CLI exception path
hid structured partial-failure evidence. Both findings were remediated red-first:

- `LiveEffect`, its manifest representation, semantic signature, preflight, delete, and
  exact add wire payload now carry the actual reserved layer. The mapping is
  `live_layer = 99 + placement.layer_index`, preserving regular/transition topology
  instead of collapsing exporter layers 0/1 into 99/99.
- Preflight groups reads by target and examines every actual affected layer. Ownership,
  idempotence, selective section regeneration, disappearing-target deletion, and
  uncertain-add recovery are layer-sensitive. Planned effects that overlap on the same
  target and actual layer now halt before even the first xLights request; overlap across
  different exporter layers remains valid.
- A golden regression independently obtains `XsqAdapter` placements and proves the live
  target/relative-layer/time topology is identical. Multi-layer fake tests cover exact
  99/100 add wires, idempotence, section replacement, a failed layer-100 add after a
  confirmed layer-99 prefix, and JSON manifest round-trip.
- The CLI catches `InjectionPartialError` before its generic safe-stop path and prints
  every confirmed injected effect, every confirmed deletion, the exact failed payload,
  the underlying error, and the recovery instructions. A command-facing output test
  pins all five fields.
- Section regeneration now also narrows `energy_profile.section_profiles` to the one
  canonical section (in addition to structure, macro, and lyric cues). The previously
  reported formatting defect in `test_stage.py` was fixed.

Post-remediation evidence: focused live/client/CLI/stage selection `40 passed, 1
skipped`; broad xLights/CLI/MH regression selection `501 passed, 2 skipped`; golden
selection `75 passed, 8 skipped, 5023 deselected`; frozen static gates passed with 1,313
files formatted, no Ruff findings with `--no-cache`, and no mypy findings across 709
source files; final frozen full suite `5069 passed, 37 skipped`, with the same nine
pre-existing `ProfileCorpusBuilder` deprecation warnings. No git, live xLights, or
provider calls were made during remediation, and this author does not self-approve the
result.

### Final CLI wiring correction (2026-08-14)

The final re-review found that the typed `InjectionPartialError` reporter had been
attached to the read-only `getModels` try block instead of the mutation try block. The
dead read handler was removed and the typed catch now immediately wraps the actual
`workflow.inject` / `workflow.regenerate_section` await, before the generic exception
handler.

The helper-only output test was replaced with a real `run_pipeline_async` regression.
It drives the live command path through successful offline layout/planning fakes, forces
`LiveInjectionWorkflow.inject` to raise `InjectionPartialError`, asserts exit code 1,
and pins the confirmed injected prefix, confirmed deletions, exact failed payload,
underlying error, and recovery text. Red evidence showed only the generic safe-stop
message before the catch was moved. Post-fix evidence: CLI plus xLights unit selection
`56 passed`; focused injection/command-path selection `15 passed`; frozen format check
1,313 files, no-cache Ruff, and mypy across 709 source files all passed. No git, live
xLights, provider call, commit, or self-approval occurred.
