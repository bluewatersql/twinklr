---
type: context
status: active
area: governance
updated: 2026-11-12
---

# Evidence-First Investigation

Authority, scope, and validation rules are owned by [AGENTS.md](../../AGENTS.md);
execution guardrails by
[changes/shared/agent_guardrails.md](../../changes/shared/agent_guardrails.md). This page
covers how to investigate and prove a fix.

1. **Establish the observation.** Record the exact failing command, the relevant inputs
   and configuration, the actual output, and the expected behavior.
2. **Trace the cause.** Read the producing and consuming code, tests, and runtime
   evidence. Separate a demonstrated cause from a hypothesis and check the plausible
   alternatives. Do not diagnose from symptoms or from a prior agent's summary.
3. **Define success before editing.** Reproduce the failure where it occurs. An offline
   test proves only its own scope; a provider, xLights, or audio-runtime failure needs
   evidence from that runtime, within the owner's authorization.
4. **Fix the owning layer.** Correct the defect where it originates rather than
   compensating downstream. Avoid broad exception suppression, speculative fallbacks, and
   one-input workarounds.
5. **Check representative behavior.** Validate the original failure and the adjacent
   cases. Inspect outputs, not only exit codes. Do not weaken a test to accept a broken
   result.
6. **Report evidence and limits.** Record the cause, the exact change, validation commands
   with outcomes, and what remains uncertain in the active change.

Unverified leads may be recorded as candidates with the missing confirmation named. They
are not current truth.
