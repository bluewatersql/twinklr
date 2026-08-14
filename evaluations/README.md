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

Phase 2P also implements typed N-run/three-arm comparison records and an
evidence-preserving writer path. No real three-arm result belongs here yet: P2P-T6
calibration, the owner-local run, blind human ranking, and independent result review are
still pending. Offline fixtures and harness tests are not evaluation results.

## Why this directory exists

Before P1P-T10, nothing in the project had ever recorded whether a generated show was any
good — see `changes/twinklr-reactivation-review/reviews/phases/corpus-intelligence.md`
(P6-F3/P6-F4). This directory is where that evidence accumulates. It is **history**, not
current project truth: an entry documents what one run at one commit produced, not a
standing claim about the pipeline's present behavior. Consistent with the repository's
change-management protocol, do not treat an entry here as project truth once the code has
moved on — check its recorded commit SHA before relying on it.

## What does *not* belong here

- Uncalibrated fixture output, synthetic comparison data, or an incomplete
  `ComparisonReport`. A multi-run result may be committed only after the owning protocol
  validates its source artifacts, costs, calibration, blind ranking, and human evidence.
- Durable decisions, learnings, or constraints about the evaluation *harness itself* — those
  belong in `memories/` per `AGENTS.md`'s knowledge-placement table, with a link back to
  the run that surfaced them.
- Gitignored artifacts (`data/`, `artifacts/`) — those are local/generated and never
  committed. Everything under `evaluations/` is intentionally durable and reviewable.

See [`INDEX.md`](INDEX.md) for the list of runs.
