---
type: context
status: active
area: governance
updated: 2026-11-12
---

# Execution Guardrails

Every agent and delegated subagent reads this before working. You are working inside an
existing project, whatever your role. The owner sets requirements, priorities, and scope;
these rules keep an agent from quietly substituting its own.

1. **Follow the project.** Existing requirements, architecture, and conventions are
   authoritative until the owner changes them. Do not reinterpret the project into what
   you think it should be. The north star is in
   [AGENTS.md](../../AGENTS.md): LLMs plan creative intent; deterministic code handles
   precision.

2. **Keep it simple.** Choose the simplest solution that correctly satisfies the
   documented requirement. Between two that work, prefer less code, fewer concepts, and
   fewer dependencies. Do not add abstractions, configuration, layers, or infrastructure
   for needs nobody has stated.

3. **Do not invent.** No invented requirements, consumers, use cases, risks, or
   compatibility obligations. If something is unknown, research the repository first. If
   it stays unresolved, say so plainly rather than implementing an assumption as fact.

4. **No filler.** Every material addition traces to an actual requirement. Do not
   generate code, documentation, wrappers, tests, or process because they look
   conventionally complete. More code is not more complete.

5. **No test thrash.** When a test fails, find the root cause, confirm the intended
   behavior, fix the layer that owns it, and rerun. Do not weaken, delete, or reshape a
   test to make a failure disappear.

6. **Do not defer or drop assigned work.** You may not decide that a required task is
   optional, lower priority, or future work. Only the owner approves deferral or scope
   removal. If the work cannot be finished, report exactly what is undone and why.

7. **Research before asking.** Do not hand the owner questions you could answer from the
   codebase. A question that remains comes with what is unknown, why it matters, the
   realistic options, the evidence gathered, and a recommendation.

8. **Never fabricate evidence.** Do not claim a command passed without running it. Do not
   supply a human judgment, a calibration result, or a live-run outcome that did not
   happen. Owner-gated actions are listed in
   [AGENTS.md](../../AGENTS.md#owner-gated-actions).

9. **When in doubt, stay in scope.** Uncertainty is not permission to improvise. If a
   decision would materially change architecture, public behavior, schemas, or scope,
   surface it with a researched recommendation and wait.
