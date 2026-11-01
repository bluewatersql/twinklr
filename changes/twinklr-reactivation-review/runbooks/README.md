# Owner runbooks: remaining empirical exits

Step-by-step commands for the reactivation-review exits that need real data, a live
provider, a running xLights, or human judgment. The task specs under
[`../build/specs/`](../build/specs/) are the authority; these runbooks put them into
practice. Current gate status lives in [`../build/plan/HANDOFF.md`](../build/plan/HANDOFF.md).

| # | Runbook | Exits it closes | Paid? | Blocked on |
|---|---|---|---|---|
| 01 | [Ollama cloud smoke](01-ollama-cloud-smoke.md) | Phase 4 Ollama exit (P4-T2), using `glm-5.3:cloud` | Ollama cloud plan, 1 request | Nothing (daemon running and signed in) |
| 02 | [Phase 2K catalog growth](02-phase-2k-catalog-growth.md) | P2K-T1 coverage, **P2K-T2 mining + 8 decisions**, P2K-T3 curation, P2K-T4 style fingerprints | T3 only | Your real layout, sequence archives, style-group declaration |
| 03 | [P4-T7 MH idiom mining](03-p4-t7-mh-idiom-mining.md) | Optional P4-T7 feasibility memo | No | Accepted P2K-T2 evidence (runbook 02) and an accepted private MH corpus manifest |
| 04 | [xLights GUI and human acceptance](04-xlights-gui-and-human-acceptance.md) | P1P-T12 import suite and judgment, P2P-T5 preview, P2P-T12 injection, P3-T6 GUI check, P3-T8 show evaluation | Some steps | Local windowed xLights 2026.15 and an expendable show folder |
| 05 | [Phase 2P and 3 live evidence](05-phase-2p-and-3-live-evidence.md) | Baseline live run, P2P-T6 calibration, P2P-T13 three-arm, P2P-T7 Demucs, P2P-T10/T11 probes, P3-T4 decision | Yes | OpenAI key; T13 needs an owner-local experiment backend |

## Suggested order

1. **01**: the cheapest run, and it unblocks the strict Phase 4 exit.
2. **05 §2 baseline live run**: confirms your moved artifacts and configs work live
   before you spend anything else.
3. **04**: the xLights checks were waiting for a working end-to-end show, which now
   exists. The P2P-T5 preview output also feeds the P2P-T6 calibration in 05.
4. **02 P2K-T2 first, before other Phase 2K steps.** Its idempotence check hashes the git
   diff, so any tracked-file change between its two runs invalidates the evidence.
5. **05 §3 P2P-T6**, then **§4 P2P-T13** (needs accepted T6 calibration).
6. **03**, only if you want the optional spike after 02 is accepted.

## Before you start

- **Moving your artifacts in.** Each runbook has an "Inputs" section that names the exact
  paths. Audio, rigs, layouts, corpora and generated output are gitignored local data
  (`data/`, `artifacts/`, `config.json`, `job_config.json`, `fixture_config.json`). Never
  commit them. Commit only the evidence files the runbooks name.
- **`uv run` and the package index.** The lockfile resolves through the configured package
  index. Run `uv sync --extra dev --all-packages` (= `make install`) once while that index is
  reachable. A bare `uv sync` removes pytest. If a later `uv run` stalls
  trying to re-sync, use `uv run --frozen` (some runbooks already do), or call
  `.venv/bin/<tool>` directly.
- **Clean tree for evidence.** Several steps record `git rev-parse HEAD` or hash the
  working-tree diff. Commit or stash unrelated edits first.

## Evidence locations

- **Show, vision and human-judgment results** (`eval-report` output, judge scores,
  judgments, calibration) go in `evaluations/<date>-<slug>/`, with a row in
  [`evaluations/INDEX.md`](../../../evaluations/INDEX.md), per AGENTS.md and
  `evaluations/README.md`.
- **Provider, tooling and data-pipeline evidence** (smoke logs, probe notes, Demucs
  timings, mining manifests, GUI import logs) goes in
  `changes/twinklr-reactivation-review/evidence/<date>-<slug>/`.
- After a run, have an agent update the spec status, HANDOFF, `changes/ACTIVE.md` and
  `context/current-state.md` from the recorded evidence. Merged tooling or offline tests
  are never acceptance on their own.

## Permanent boundaries (every runbook honors these)

- P3-T4's sealed two-attempt ledger is closed. No third attempt.
- P3-T7's image proof is terminal and is never rerun.
- WhisperX/TorchCodec runtime stays deferred under FFmpeg 9.
- xLights work runs only against an expendable show folder or scratch sequence. The
  xLights automation API has no authentication.
- Live paid steps run only within the cap and authorization their spec states.

## Open owner decisions and tooling gaps

Each runbook ends with the decisions it leaves to you and the spec requirements that have
no tooling yet. The main blockers:

- **P2P-T13** needs an owner-local `ExperimentBackend`. None ships.
- **P3-T8** live show judge and record assembly exist only as library functions, with no
  CLI.
- **P2K "both supply arms"** has no tool that admits mined candidates into
  `catalog/templates`.
- **P2P-T10** `live_smoke` test named in its spec does not exist.
- **P3-T4** needs your call on whether the post-refactor live MH run supersedes it.
