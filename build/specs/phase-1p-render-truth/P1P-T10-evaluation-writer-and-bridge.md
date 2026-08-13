# P1P-T10 — Evaluation writer + bridge

Phase: 1P (Render Truth) · Lane: I (instrumentation/cache, parallel) · Executor: sonnet · Verifier: opus · Depends on: P1P-T4, P1P-T5, P1P-T9

## Objective

Close the loop the project has never closed: make a run write a checkpoint, make the
existing `eval-report` command reachable from the `twinklr` CLI, and commit the first
evaluation result plus the first recorded human judgment in the repository's history.
Nothing in the system has ever been able to say whether a generated show is any good; this
task makes it possible, and then does it once.

## Evidence & background

Findings: **SF-4** = **P6-F3** (corrected by verifier git archaeology) + **P6-F4**.

Line numbers are hints from baseline `aa8d325`. Re-verify before editing.

### The writer was deleted, not never built (P6-F3, REVISED). Verbatim:

> Verifier git archaeology overturns the original framing. A working checkpoint writer
> existed — `utils/checkpoint.py` plus an orchestrator call site, introduced at `b6fdfd2`,
> writing exactly the format `eval-report` reads today, with a committed proof artifact —
> and was deleted 2026-01-23. It was replaced by an adapter that nothing ever called
> (introduced around `2d48b91`, dead on arrival), and the whole capability was removed at
> `38d810d`. This is an **abandoned migration that silently dropped a working capability**,
> the same class of defect as phase 7's dead-config findings (P7-F4/F5), not a feature
> that was simply never finished. Restoration is **cheaper than originally scoped**: ~10
> lines, checkable against the historical reference artifact still visible in git history.
> **Trap for whoever restores it**: the inner plan schema has drifted since the deleted
> artifact was written — the historical checkpoint format used a `templates:[...]` list
> shape; today's model uses `template_id` XOR `segments`. Historical checkpoint artifacts
> are **not replayable as-is**; the restored writer must serialize TODAY's `PlanSection`
> model, not resurrect the old format. `JobConfig.checkpoint` (zero readers anywhere) is
> named as a dead-config member in this scope, alongside the previously-identified
> `PipelineContext.checkpoint_dir`. The CLI-bridging point from the original finding is
> unchanged: the click command already exists in full (`cli.py:18-132`); the `twinklr`
> console script is argparse-only with exactly one subcommand (`run`, `cli/main.py:331-353`)
> and no dispatch pattern to extend from except that one example.

And the scoping, verbatim:

> The concrete remediation scope is: (1) restore a
> checkpoint-writer stage to the moving-heads pipeline serializing TODAY's `PlanSection`
> model (not the deleted historical format — schema-drift trap above), ~10 lines against
> the reference artifact; (2) add an `eval-report` argparse subcommand or click-bridge to
> `cli/main.py` (~20-30 lines by inspection of the existing `run` subcommand pattern).
> Disposition: Stage 8 roadmap should scope this as two named small tasks, explicitly
> citing the historical reference commit and the schema-drift trap so the restoration
> doesn't resurrect the wrong format.

### What the harness can and cannot do (P6-F4, ACCEPTED). Verbatim:

> Confirmed: the harness measures only renderer
> self-consistency (physics bounds, cross-section continuity deltas, template-declared
> compliance heuristics, clamp %, loop discontinuity) with no ground truth or golden
> comparison anywhere in its model surface. A `ComparisonReport`/`ComparisonMetrics` schema
> for exactly the N-run comparison a 3-arm experiment needs is declared and exported
> (`models.py:299-323`, `__init__.py:6-7,49-50`) but **has zero producers anywhere in the
> repo** …
> (1) no batch/multi-checkpoint mode — the CLI
> takes exactly one checkpoint per invocation; (2) the comparison/aggregation function must
> be built from scratch, not wired — its schema is a stub; (3) no diversity/anti-repetition
> metric exists …; (4) no mechanism exists to collect or
> store human ratings — the "mandatory blind human ranking" Stage 2 proposes has zero
> tooling today and would need to be built as a wholly separate capability …

**The `ComparisonReport` builder and a general human-rating capability are explicitly NOT
this task** (P6-F4 names them as separate pre-work for the 3-arm experiment). This task
records **one** human judgment in a simple committed form.

Re-verified in the current tree:
`packages/twinklr/core/reporting/evaluation/cli.py:18` is
`@click.command("eval-report")`; `collect.py` provides `load_checkpoint` (reading a JSON
dict) and `extract_plan`, which does `ChoreographyPlan.model_validate(checkpoint_data["plan"])`
— i.e. **the reader already expects today's model**, which is exactly why the writer must
serialize today's model. `cli/main.py:337` is
`sub = p.add_subparsers(dest="cmd", required=True)` with `run` as the only subcommand.
`rerender.py` exists and drives the production `RenderingPipeline`.

## Current behavior

- No code writes a checkpoint. `artifacts/**/checkpoints/plans/*.json` — the input
  `eval-report` reads — is produced by nothing.
- `eval-report` exists as a complete click command that no console script exposes; the
  `twinklr` entry point has one subcommand (`run`).
- `JobConfig.checkpoint` and `PipelineContext.checkpoint_dir` have zero readers.
- No evaluation result has ever been committed. There is not one recorded human opinion
  about a generated show anywhere in the repository.

## Target behavior

1. The moving-heads pipeline writes a checkpoint at the orchestrator seam, serializing
   **today's** `ChoreographyPlan`/`PlanSection` model, in the shape
   `collect.load_checkpoint` + `collect.extract_plan` already read (`{"plan": {...}, ...}`
   plus run metadata).
2. `twinklr eval-report ...` works from the console script, bridging to the existing click
   command (or reimplemented as an argparse subcommand following the `run` pattern —
   whichever keeps one code path, not two).
3. One evaluation result is generated from a real run and **committed** to the repository,
   together with a recorded human judgment in a simple, durable, reviewable form.
4. Checkpoint writing is controlled by a config field that is actually read — either
   `JobConfig.checkpoint` gains its first reader here, or it is deleted and a new,
   read field replaces it. No third state.

**Non-goals.** Do not build the `ComparisonReport`/`ComparisonMetrics` producer. Do not
build a general human-rating capture tool or a side-by-side preview. Do not add a
diversity/anti-repetition metric. Do not add batch/multi-checkpoint mode. Do not attempt
to read or replay historical checkpoint artifacts from git history — they are **not
replayable** (see the trap below).

## Implementation approach

Files/symbols to touch:
- `packages/twinklr/core/agents/sequencer/moving_heads/orchestrator.py` (or the
  `stage.py`/`rendering_stage.py` seam, whichever is the true plan-produced boundary) —
  the ~10-line writer.
- `packages/twinklr/cli/main.py` — subcommand dispatch (`:331-353` at baseline) to reach
  `eval-report`.
- `packages/twinklr/core/reporting/evaluation/cli.py` — the existing click command
  (`:18-132`), unchanged if bridged.
- `packages/twinklr/core/pipeline/context.py` / `config/models.py` — the `checkpoint` /
  `checkpoint_dir` fields: wire or delete.
- A committed evaluation artifact plus the human judgment record (location: alongside the
  change's artifacts under `changes/` or a dedicated `evaluations/` directory — pick one
  and say why in the handoff; it must be reviewable and durable, not gitignored `data/`).

Design decisions already made (do not relitigate):
- **Serialize today's model.** The historical `templates:[...]` format is dead; the reader
  already validates against `ChoreographyPlan`.
- **Bridge, don't fork.** `eval-report`'s implementation stays where it is; the CLI gains a
  dispatch path to it.
- **One human judgment, recorded simply.** A short structured markdown record (what was
  rendered, which rig, what the human thought, a numeric overall score, the date) is
  sufficient and is the repository's first. Do not build tooling for it.

Sequencing constraints (copied verbatim from `build/plan/00-overview.md`):

> Checkpoint writer must serialize **today's** `PlanSection` (historical artifacts are not
> replayable) (P1P-T10).

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases land)
> — specs cite symbol + file, with line numbers as hints only.

From `build/plan/02-phase-1p-render-truth.md`:

> **Lane I (instrumentation/cache, parallel — `agents/`, `caching/`, `pipeline/`)**:
> T9 → T10.

Dependency note (from the same doc): this task depends on **P1P-T4 and P1P-T5** so that
the thing being evaluated is *true* — evaluating a render whose sections are up to two
seconds early, whose blackouts are full brightness, and whose short sections are empty
would produce a recorded human judgment about a known-broken artifact and poison the first
data point.

**P0-T7 interaction:** phase 0 deletes `checkpoint`/`checkpoint_dir` fields as dead config,
noting they are *"superseded by P1P-T10's writer"*. Confirm what P0-T7 actually removed
before wiring; if the fields are gone, introduce a single well-named replacement rather
than resurrecting both.

## Acceptance criteria

- [ ] A completed moving-heads run writes a checkpoint file whose `plan` field validates
      via `ChoreographyPlan.model_validate` — i.e. `collect.extract_plan` reads it with no
      changes to `collect.py`.
- [ ] The written checkpoint contains **no** `templates: [...]` list-shaped section entry.
      Verifiable by asserting each section carries `template_id` XOR `segments`, matching
      today's model.
- [ ] `twinklr eval-report --help` works from the installed console script.
- [ ] `twinklr eval-report` run against the checkpoint from a real render produces a report
      without hand-editing the checkpoint.
- [ ] Exactly one code path implements `eval-report` (no duplicated click/argparse
      implementations).
- [ ] Checkpoint writing is controlled by a config field with a production reader; `grep`
      shows no remaining declared-but-unread checkpoint config.
- [ ] **A generated evaluation result is committed to the repository** — the first in its
      history — with the run's inputs identified (audio, rig, plan, commit SHA).
- [ ] **A human judgment is committed** alongside it: what was watched/inspected, the
      judgment, a numeric overall score, and the date.
- [ ] `make validate` check-only equivalents pass.

**Note on golden diffs:** this is a Lane-I task and must not change render output. The
P1P-T1 golden suite must be **byte-identical** before and after this change; a golden diff
here is a failure, not an accepted change.

## Tests

| Test | Behavior pinned |
|---|---|
| `test_checkpoint_written_on_run` | The writer exists and fires at the seam |
| `test_checkpoint_roundtrips_through_collect` | `load_checkpoint` → `extract_plan` succeeds with no adapter |
| `test_checkpoint_uses_current_plan_schema` | The schema-drift trap: `template_id` XOR `segments`, no `templates:[...]` |
| `test_checkpoint_disabled_by_config` | The controlling field is read |
| `test_eval_report_subcommand_registered` | The bridge exists |
| `test_eval_report_runs_on_written_checkpoint` | End-to-end: writer output is valid `eval-report` input |
| Golden suite (P1P-T1) | Byte-identical — this task changes no render output |

**Test budget:** the automated tests use the deterministic plan fixture from P1P-T2 — no
LLM call. Producing the **committed** evaluation result requires one real run:

- **LOCAL-ONLY:** one full `twinklr run` against a real song, which makes paid LLM calls.
  Budget: **one run**. This is the only paid call authorized by this spec. It is not part
  of CI and must not be repeated for iteration — iterate against the deterministic fixture,
  then do the real run once.
- **LOCAL-ONLY:** the human judgment requires a human watching or inspecting the result.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .

uv run pytest tests/unit/reporting -v
uv run pytest tests/unit/agents/sequencer -v
uv run pytest tests/golden -v          # must be unchanged

uv run twinklr eval-report --help

# schema-drift check the verifier runs against the committed artifact
uv run python -c "
import json,sys
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
d=json.load(open(sys.argv[1]))
p=ChoreographyPlan.model_validate(d['plan'])
assert not any('templates' in (s.model_dump() if hasattr(s,'model_dump') else s) for s in p.sections)
print('ok', len(p.sections), 'sections')" <path-to-committed-checkpoint>

# LOCAL-ONLY (paid, one run only, excluded from CI):
# uv run twinklr run --audio <song.mp3> --config <job_config.json> --out artifacts/eval-first
# uv run twinklr eval-report --checkpoint artifacts/eval-first/checkpoints/plans/final.json ...
```

## Effort & risk

**Effort: S** for the code (~10 + ~25 lines); **M** overall, because the committed result
and human judgment require a real run and a person.

**Main risk: resurrecting the historical format.** The deleted writer is visible in git
history and is the obvious reference — and it writes the **wrong** shape. Mitigation: the
acceptance criterion asserts the current schema directly; read `collect.extract_plan`
(which already validates `ChoreographyPlan`) as the contract, and treat the historical
commit only as evidence that ~10 lines suffice.

**Second risk: evaluating a still-broken render.** Mitigation: the task depends on P1P-T4
and P1P-T5; do the real run **after** those merge. If the phase's merge order forces the
run earlier, record in the human-judgment artifact exactly which fixes were in the tree at
that SHA, so the first data point is interpretable later.

**Third risk: the committed artifact becomes stale project truth.** Mitigation: the record
names its commit SHA and inputs, and lives as a dated artifact (history), not as a claim
about current behavior — consistent with the repository's change-management protocol that
"a closed change must never be the only home of current project truth".
