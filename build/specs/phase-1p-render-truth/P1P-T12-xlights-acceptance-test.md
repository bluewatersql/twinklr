# P1P-T12 — xLights acceptance test

Phase: 1P (Render Truth) · Lane: D (delivery) · Executor: sonnet · Verifier: opus · Depends on: P1P-T11

> ## LOCAL-ONLY TASK
>
> **Every empirical step in this task is LOCAL-ONLY**: it requires xLights 2026.15
> installed and running on the owner's machine, with the HTTP automation API enabled. None
> of it runs in CI. The task's *committed deliverable* is the recorded result — the
> answers to the open contract questions, plus any regression tests that the findings
> justify.
>
> Per the plan overview: *"Nothing in this program authorizes pushes/PRs to remotes or
> paid API calls beyond each spec's stated test budget; live-LLM and xLights-GUI tests are
> marked `LOCAL-ONLY` in specs and excluded from CI."*

## Objective

Answer, empirically and once, the questions this whole review could not answer from the
repository: does xLights 2026.15 accept what Twinklr now emits? The deliverable is not
code that runs in CI — it is a recorded, committed answer to four specific questions, and
whatever guard tests those answers justify.

## Evidence & background

Findings: **M6 / M6b unknowns** (`reviews/modernization.md`), the **P1P-T1 spec items**,
**P4-F3 / P5-V1** (shutter), **P5 §V4** (the stamp/structure risk list), **P4-F6**
(overlapping effects).

### The unresolved contract question (M6b, verbatim):

> **Effect import accepts xLights donor sequences** targeting the currently open
> sequence, carrying effects + timing tracks; models must pre-exist in the view;
> mapping is the friction (mitigated by shipping `.xmap` or using AI/auto mapping).
> **UNVERIFIED: whether a bare `.xsq` without `xlights_rgbeffects.xml` imports (docs
> state the requirement only for the zip path) — Stage 4 empirical test.**

### The automation surface to drive it (M6b, verbatim):

> **The real extension points: Lua scripting (Tools > Run Scripts; `RunCommand` drives
> xlDo) and the HTTP automation API** (xFade service, port 49913/49914, POST
> `/xlDoAutomation`; no authentication documented — flag as a local attack surface).
> Key commands: `importXLightsSequence` (with `mapmethod: file|auto|both` + `.xmap`/
> `.xjmap` hint files), `addEffect` (direct effect injection into the open sequence),
> `getModels`/`getViews` (read the user's real layout), `newSequence`, `renderAll`,
> `checkSequence`, media embed/extract.

**Security note carried forward from M6b:** the automation API has *"no authentication
documented — flag as a local attack surface."* Enable it only for the duration of this
test, on a local interface, and disable it afterwards. Do not add anything to the
repository that enables it by default or that a CI job could invoke.

### The stamp question (M6 + M6b, verbatim):

> Twinklr's hardcoded sequence stamps ("2024.10"/"2024.01") are ~2 years / ~40 releases
> old. … UNVERIFIED and untestable from docs: whether 2026.15 opens a "2024.10"-stamped
> file — **Stage 4 empirical test: generate and open in current xLights.**

> **Version stamps: documented cutoff is pre-2020 only (warning, not rejection;
> introduced 2026.04)** — "2024.10" is acceptable today; the boundary can ratchet, so
> update stamps anyway (free). **UNVERIFIED: treatment of synthetic/unknown stamp values.**

P1P-T11 updates the stamp; this task verifies both the updated stamp **and** (cheaply)
what happens with an unknown/synthetic one, since Twinklr emits a hardcoded constant
rather than a real release string.

### The shutter question (P4-F3 / P5-V1). What remains empirical, verbatim (P5-V1):

> Stage 4's remaining job is therefore narrow: confirm that the author's *physical*
> fixtures follow the convention the repo already assumes. It is no longer establishing
> intent.

P1P-T6 changed the emitted bytes; this task confirms the observable result on the
>16-channel rig config.

### The overlap question (P4-F6, verbatim):

> **INFERRED downstream effect:** overlapping effects on the same xLights model on the same
> layer. … xLights does not accept two effects overlapping in
> time on one layer — Stage 4 should check whether the file loads at all when this
> template is selected.

P1P-T5 clamps the schedule so overlaps should no longer occur; this task confirms the
clamp is sufficient by loading a file rendered with `split_lr_sweep_counter` selected.

### The risk list to walk (P5 §V4, verbatim, ordered by likelihood):

> 1. **Missing root sections that 2026-era xLights expects.** … Highest-probability
>    failure mode …
> 3. **`<Jukebox/>` empty vs. expected structure** — an empty element where a populated
>    one is expected is a classic loader crash.
> 4. **`nextid` never advanced past 1** while effects exist; if xLights uses it to
>    allocate ids on edit, collisions on first save are plausible.
> 5. **Settings-string key validity.** Every `E_*` key is hardcoded against a 2024-era
>    understanding of each effect's widget names. Renamed or removed keys degrade
>    silently (xLights typically ignores unknown keys), which would look like "opens fine
>    but the effect is wrong" — the hardest failure to detect. Test by *inspecting an
>    effect's parameters in the xLights UI*, not merely by opening the file.
> 6. **`ref`/`palette` index integrity** …
> 7. **Timing-track layer count** (P5-F5.4) …

### The protocol the review prescribes (P5 §V4, verbatim):

> **Recommended Stage 4 protocol:** (a) generate a `.xsq`; (b) open in current xLights and
> record whether it loads, warns, or migrates; (c) **save from xLights and diff the
> saved file against the generated one** — that diff is the only ground truth in existence
> for what xLights actually requires, and it is worth committing as the repository's first
> golden fixture regardless of outcome.

## Current behavior

Nothing in the repository has ever been opened by xLights, as far as the review could
establish. There is no golden fixture, no round-trip evidence, and no record of whether a
Twinklr-emitted file loads.

## Target behavior

Four questions answered and recorded, plus the xLights-saved file committed as the
repository's first ground-truth fixture:

1. **Does the fresh `.xsq` import** into an open xLights 2026.15 sequence via
   `importXLightsSequence`, **with** `xlights_rgbeffects.xml` and **without** it? (The one
   unresolved contract question.)
2. **Is the version stamp accepted** — the current stamp emitted by P1P-T11, and (cheap
   extra) a synthetic/unknown value?
3. **Does the >16-channel rig config produce shutter-open output** — i.e. does the P1P-T6
   channel-default policy produce the intended physical/visual result?
4. **Does a sequence containing `split_lr_sweep_counter` load** without the overlapping-
   effects failure P4-F6 predicted (post-P1P-T5 clamp)?

Plus: the `.xtiming` file imports standalone as a timing track, and the `.xmap` reduces
mapping friction on import.

**Non-goals.** Do not build a permanent xLights-driving test harness. Do not implement
`addEffect` injection (a later phase's option). Do not "fix" anything found here in this
task — file it, with evidence, as input to a follow-up.

## Implementation approach

This is an empirical protocol plus a small amount of recorded output. Steps:

1. **Generate.** Render the deterministic plan fixture (P1P-T2) for each rig, producing
   `.xsq` + `.xtiming` + `.xmap` (P1P-T11). Also render a variant whose plan selects
   `split_lr_sweep_counter` and one that selects both blackout templates.
2. **Enable the automation API** in xLights (locally, for the duration only). Record the
   version string from xLights itself, not from documentation.
3. **Import, both ways.** Use `importXLightsSequence` with `mapmethod: file` and the
   shipped `.xmap`, first with `xlights_rgbeffects.xml` present, then without. Record
   exactly what happens each time (imports / warns / rejects, and the message).
4. **Walk the P5 §V4 risk list** for the file that does import: check root sections,
   `<Jukebox/>`, `nextid`, `ref`/`palette` indices, timing-track layer count, and —
   critically — **inspect an effect's parameters in the xLights UI**, since silently
   ignored `E_*` keys are the hardest failure to detect.
5. **Stamp probe.** Repeat the import with a synthetic stamp value to answer M6b's
   remaining unknown. Cheap; do it while set up.
6. **Shutter check.** With the `rig_shutter_high` config, verify the emitted output
   produces shutter-open behavior (visually, or via the imported effect's parameters if no
   fixture is connected).
7. **Overlap check.** Load the `split_lr_sweep_counter` variant; record whether it loads.
8. **`.xtiming` check.** Import the `.xtiming` standalone into a sequence with no model
   mapping; confirm the tracks appear with markers at the expected times.
9. **Save and diff.** Save from xLights and diff the saved file against the generated one.
   **Commit the xLights-saved file** as the repository's first ground-truth fixture,
   alongside the diff summary.
10. **Record.** Write the results into the golden suite's documentation — the phase plan
    says *"document results in the golden suite"* — as a dated, versioned record naming the
    xLights build and the Twinklr commit SHA.

Files likely touched:
- `tests/golden/` — a `XLIGHTS-ACCEPTANCE.md` (or equivalent) results record; the
  committed xLights-saved `.xsq` fixture.
- Possibly a new round-trip assertion in the P1P-T1 suite, if the saved-file diff reveals a
  structural requirement Twinklr does not meet (e.g. a missing root section). That
  assertion runs in CI; the xLights step does not.

Design decisions already made (do not relitigate):
- **The saved-from-xLights file is committed regardless of outcome** — the review calls it
  *"the only ground truth in existence for what xLights actually requires"*.
- **Inspect effect parameters in the UI**, not just "does it open" — the silent-degradation
  failure mode is the expensive one.
- **The automation API stays off** in the repository's defaults; nothing committed here may
  enable it.

Sequencing constraints (copied verbatim from `build/plan/00-overview.md`):

> Nothing in this program authorizes pushes/PRs to remotes or paid API calls beyond
> each spec's stated test budget; live-LLM and xLights-GUI tests are marked
> `LOCAL-ONLY` in specs and excluded from CI.

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases land)
> — specs cite symbol + file, with line numbers as hints only.

From `build/plan/02-phase-1p-render-truth.md`:

> **Lane D (delivery, after T2; touches `formats/`, `cli/`)**: T11 → T12.

## Acceptance criteria

- [ ] **Q1 answered and recorded:** whether the fresh `.xsq` imports with and without
      `xlights_rgbeffects.xml`, including the exact xLights message in each case.
- [ ] **Q2 answered and recorded:** whether the emitted stamp is accepted; whether a
      synthetic/unknown stamp is accepted, warned on, or rejected.
- [ ] **Q3 answered and recorded:** whether the `rig_shutter_high` render produces
      shutter-open output, with the evidence used (visual, or the imported effect's
      parameter values).
- [ ] **Q4 answered and recorded:** whether a sequence containing `split_lr_sweep_counter`
      loads (P4-F6's predicted overlap failure, post-clamp).
- [ ] `.xtiming` standalone import verified, with the marker times spot-checked against the
      detected beat grid.
- [ ] At least one effect's parameters inspected in the xLights UI and compared against the
      emitted settings string, to detect silently-ignored `E_*` keys.
- [ ] The xLights-**saved** file is committed as a fixture, with a summary of its diff
      against the generated file.
- [ ] Results are recorded in the golden suite's documentation, naming the exact xLights
      build string, the Twinklr commit SHA, the rigs used, and the date.
- [ ] Any structural requirement discovered (e.g. a missing root section) is either fixed
      in a follow-up task **or** filed with evidence; if a CI-runnable assertion is
      justified, it is added to the P1P-T1 suite and passes.
- [ ] Nothing committed enables the xLights automation API by default; no CI job invokes
      it.
- [ ] `make validate` check-only equivalents pass (this task should change little or no
      production code).

## Tests

CI-runnable tests added by this task are limited to whatever the empirical findings
justify — typically structural assertions on the emitted file, derived from the
xLights-saved ground truth:

| Test (CI) | Behavior pinned |
|---|---|
| `test_emitted_xsq_has_required_root_sections` | Only if the saved-file diff shows a section xLights adds/requires |
| `test_emitted_xsq_matches_saved_ground_truth_structure` | Structural (not byte) comparison against the committed xLights-saved fixture |

| Step (LOCAL-ONLY, not CI) | Question |
|---|---|
| Import with/without `rgbeffects.xml` | Q1 — the one unresolved contract question |
| Import with current and synthetic stamps | Q2 |
| Render + import `rig_shutter_high` | Q3 |
| Render + import `split_lr_sweep_counter` | Q4 |
| Import `.xtiming` standalone | `.xtiming` deliverable viability |
| Inspect effect params in the UI | Silently-ignored `E_*` keys |
| Save from xLights, diff, commit | Ground-truth fixture |

**Test budget:** no paid API calls (renders use the deterministic plan fixture). One
xLights installation, local only.

## Verification commands

```bash
# CI-runnable portion
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest tests/golden -v

# Generate the artifacts to import (deterministic, no API calls)
uv run pytest tests/golden --regen-goldens -q

# LOCAL-ONLY — requires xLights 2026.15 running with the automation API enabled.
# Enable for this test only; disable afterwards (no documented authentication).
#   curl -s -X POST http://127.0.0.1:49913/xlDoAutomation -d '{"cmd":"getModels"}'
#   curl -s -X POST http://127.0.0.1:49913/xlDoAutomation \
#        -d '{"cmd":"importXLightsSequence","filename":"<generated.xsq>",
#             "mapmethod":"file","mapfile":"<generated.xmap>"}'
# Then: inspect an effect's parameters in the UI, save the sequence, and diff:
#   diff <(xmllint --format generated.xsq) <(xmllint --format saved-from-xlights.xsq)
```

## Effort & risk

**Effort: S–M** — mostly setup and careful recording, not code.

**Main risk: a negative result invalidates P1P-T11's contract** — if the bare `.xsq` does
not import, Twinklr has retired `--xsq` in favor of a delivery that does not land.
Mitigation: `.xtiming` imports standalone with no mapping (M6b) and is the floor
deliverable; the documented fallbacks are the zip path carrying `xlights_rgbeffects.xml`
and, later, `addEffect` injection. Record the result and route it to a follow-up task —
**do not revert the generate-fresh contract on the strength of one failed import mode**,
since the template-merge path was actively damaging the user's file.

**Second risk: "it opens" is mistaken for "it works."** Silently-ignored `E_*` keys look
like success at load time (P5 §V4 item 5). Mitigation: the UI parameter-inspection step is
a required acceptance criterion, not an optional extra.

**Third risk: the automation API is left enabled** on the owner's machine after the test —
an unauthenticated local service. Mitigation: the protocol enables it for the duration and
disables it afterwards; nothing in the repository turns it on.
