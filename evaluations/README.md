# Evaluations

Committed results from `twinklr eval-report` — dated, self-contained, reviewable evidence
of what the render pipeline actually produced at a given commit, plus (when available) a
human's judgment of the show.

Each subdirectory is one run, named `YYYY-MM-DD-<short-slug>/`, and contains:

- the checkpoint the run evaluated (`checkpoint.json`)
- the automated `eval-report` output (`report.json`, `report.md`, `plots/`)
- a `README.md` naming the run's inputs (audio, rig, plan, commit SHA)
- a `judgment.md` — the human's assessment, or a `PENDING-OWNER` stub if no one has
  watched the render yet. Never fabricate this: an agent producing a run must not also
  supply the opinion in it.

## Why this directory exists

Before P1P-T10, nothing in the project had ever recorded whether a generated show was any
good — see `changes/twinklr-reactivation-review/reviews/phases/corpus-intelligence.md`
(P6-F3/P6-F4). This directory is where that evidence accumulates. It is **history**, not
current project truth: an entry documents what one run at one commit produced, not a
standing claim about the pipeline's present behavior. Consistent with the repository's
change-management protocol, do not treat an entry here as project truth once the code has
moved on — check its recorded commit SHA before relying on it.

## What does *not* belong here

- The `ComparisonReport`/N-run comparison harness (unbuilt — see P6-F4). When it exists,
  its multi-run output may warrant its own convention; this directory is single-run
  results only.
- Durable decisions, learnings, or constraints about the evaluation *harness itself* — those
  belong in `memories/` per `AGENTS.md`'s knowledge-placement table, with a link back to
  the run that surfaced them.
- Gitignored artifacts (`data/`, `artifacts/`) — those are local/generated and never
  committed. Everything under `evaluations/` is intentionally durable and reviewable.

See [`INDEX.md`](INDEX.md) for the list of runs.
