---
type: change
status: active
area: engineering
created: 2026-11-01
updated: 2026-11-01
---

# Runbook 01 — Phase 4 Ollama cloud schema smoke (P4-T2)

**Closes:** the last open Phase 4 exit item: one real, schema-valid `MacroPlan` response
through Twinklr's Ollama provider path.
**Authority:** [P4-T2 spec](../build/specs/phase-4-compounding/P4-T2-local-provider-option.md),
including its *Owner amendment — 2026-11-01* section.

## What changed (owner decision, 2026-11-01)

The smoke uses **Ollama cloud, not a local model**. The default model is
**`glm-5.3:cloud`**. Requests still go to the loopback Ollama daemon
(`http://127.0.0.1:11434/v1`), which forwards `:cloud` models to Ollama's hosted service.
That means:

- No model weights are downloaded or run locally.
- The existing loopback-only `AppConfig` validator is satisfied without code changes.
- The smoke now proves the **Ollama provider + strict-schema path**. It does **not** prove
  the original "offline-December" claim, because the request needs internet access and an
  ollama.com sign-in.

## Prerequisites

- Ollama installed, with the daemon running (the macOS app, or `ollama serve`).
- Signed in to ollama.com. A cloud request counts against your Ollama cloud plan.
- Repo dependencies synced, including the dev extras that provide pytest:
  `uv sync --extra dev --all-packages` (the same as `make install`).

## Steps

1. **Confirm the daemon is up and signed in.**

   ```bash
   curl -s http://127.0.0.1:11434/api/version
   ollama signin            # no-op / confirms if already signed in
   ```

   Expected: a JSON version string. If `curl` fails, start Ollama (`ollama serve` in
   another terminal, or launch the app).

2. **Confirm the cloud model resolves.** This fetches metadata only, not weights.

   ```bash
   ollama show glm-5.3:cloud
   ```

   Expected: an architecture/capabilities block (`completion`, `thinking`, `tools`).
   Optional: `ollama pull glm-5.3:cloud` registers the cloud manifest so it shows in
   `ollama list` (size `-`). It downloads no weights.

3. **Confirm the smoke skips safely without opt-in.** This makes no network call.

   ```bash
   uv run pytest tests/local_only/test_ollama_structured_outputs.py -q --no-cov -rs
   ```

   Expected: `1 skipped` with reason `set TWINKLR_RUN_LOCAL_OLLAMA_TESTS=1 ...`.

4. **Run the smoke.** This makes exactly **one** Ollama cloud request. There is no retry, no
   schema repair, and no JSON-object fallback.

   ```bash
   mkdir -p changes/twinklr-reactivation-review/evidence/2026-11-01-p4-t2-ollama-cloud-smoke
   TWINKLR_RUN_LOCAL_OLLAMA_TESTS=1 \
   uv run pytest tests/local_only/test_ollama_structured_outputs.py -q --no-cov -rs \
     2>&1 | tee changes/twinklr-reactivation-review/evidence/2026-11-01-p4-t2-ollama-cloud-smoke/pytest.log
   ```

   Defaults, all overridable via env:

   | Variable | Default |
   |---|---|
   | `TWINKLR_OLLAMA_MODEL` | `glm-5.3:cloud` |
   | `TWINKLR_OLLAMA_BASE_URL` | `http://127.0.0.1:11434/v1` |
   | `TWINKLR_OLLAMA_TIMEOUT_SECONDS` | `300` |
   | `TWINKLR_OLLAMA_MAX_TOKENS` | `16000` (thinking tokens share this budget) |

   Change the folder date if you run on a different day.

5. **Interpret the result.**
   - `1 passed`: the response parsed into `MacroPlan` on the first and only attempt. The
     Phase 4 exit evidence is complete.
   - Failure: do **not** rerun to get a pass. Keep the log and classify the failure from
     the error. Possible classes: transport (daemon down or not signed in), timeout,
     truncation (`finish_reason=length`, so raise `TWINKLR_OLLAMA_MAX_TOKENS`), or schema
     invalidity (a real finding about this model). Decide whether to make one corrected
     attempt and record that decision next to the log.

6. **Record the evidence.** Create
   `changes/twinklr-reactivation-review/evidence/2026-11-01-p4-t2-ollama-cloud-smoke/README.md`
   with:
   - the date
   - the `ollama --version` output
   - the model id
   - the git SHA (`git rev-parse HEAD`)
   - the pass/fail result
   - one line on the cloud-not-local scope from "What changed" above

   Then ask the agent to update the P4-T2 spec status, `build/plan/HANDOFF.md`, and `changes/ACTIVE.md`.
   After that, the only open Phase 4 question is how to dispose of the optional P4-T7
   ([runbook 03](03-p4-t7-mh-idiom-mining.md)).

## Evidence checklist

- [ ] `changes/twinklr-reactivation-review/evidence/<date>-p4-t2-ollama-cloud-smoke/pytest.log`
      shows `1 passed`
- [ ] `README.md` in that folder records the model, Ollama version, git SHA, and
      cloud-not-local scope
- [ ] P4-T2 spec / HANDOFF / ACTIVE updated by a follow-up agent pass
