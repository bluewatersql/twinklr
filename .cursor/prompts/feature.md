# Cursor Sprint / Task Kickoff Prompt

## MISSION
You are implementing the scoped work exactly as defined. Optimize for correctness, maintainability, and alignment with the project’s architecture and conventions.

---

## 0) Source of truth
- Treat the provided **design docs, architecture docs, and implementation plan** as the source of truth.
- If any required detail is missing or ambiguous, **stop and ask a clarification question before writing code**.
- If a doc conflicts with the repo’s current behavior or another doc, **surface the conflict** and ask which to follow.

---

## 1) Process discipline (TDD required)
- Use **strict TDD** for each behavior change:
  - Write or update tests first.
  - Implement the smallest change that makes the test pass.
  - Refactor only after tests are green.
- No “temporary” bypasses:
  - No skipped tests, disabled lint/type checks, placeholder implementations, or TODO stubs unless explicitly approved.

---

## 2) Plan adherence / scope control
- **Do not change the plan** or re-scope the work.
- Do not defer requirements or create implementation stubs without approval.
- Do not invent requirements, assumptions, APIs, or behavior.
- Do not take shortcuts.
- Do not introduce backwards compatibility unless explicitly required by the docs.
- If you believe the plan is flawed or a shortcut is tempting, **propose the concern with rationale** and wait for approval.

---

## 3) Quality bar (definition of done)
A phase is complete only when:
- `make validate` passes with:
  - **0 lint warnings**
  - **0 type-check errors**
  - **all tests passing**
- Skipping tests (or marking xfail to “get green”) is not permitted for success.

**Status vocabulary**
- **DONE** = `make validate` green + requirements met
- **PARTIAL** = some tests/impl landed, more work remaining (**handoff doc required**)
- **BLOCKED** = cannot proceed due to ambiguity/dependency (**handoff doc required**)

---

## 4) Codebase alignment
- Follow existing project conventions and structure.
- Review and obey **`.cursorrules`** and any repo standards (formatting, naming, module boundaries, error handling patterns).
- Prefer consistency with established patterns over personal preference.

---

## 5) Interface + dependency discipline
- Do not change public interfaces (function signatures, CLI flags, config schemas, file formats) unless the plan explicitly calls for it.
- Do not add new dependencies unless required by the plan.
- If either becomes truly necessary, propose alternatives and tradeoffs and wait for approval.

---

## 6) Technical debt policy
- Do not create technical debt:
  - no duplicate implementations
  - no parallel code paths
  - no re-import hacks
  - no “just for now” logic
- If an unavoidable compromise is required, **document it as an explicit anti-pattern**.

---

## 7) Hygiene while working (in-scope only)
- Keep changes tight and intentional.
- Update docstrings when behavior changes.
- Remove dead code paths you encounter **in-scope** (things you touch or that block the change).
- Avoid excessive logging; keep logs meaningful and appropriately leveled.
- Avoid out-of-scope comments/documentation.

---

## 8) Documentation + status updates (minimal + useful)
- Maintain **one status document per phase**:
  - What changed (bullets)
  - Current state (**DONE / PARTIAL / BLOCKED**)
  - Remaining tasks (ordered checklist)
  - Open questions / blockers
- Keep it concise and actionable:
  - No long prose
  - No code samples
  - No usage examples unless the plan explicitly requires them

---

## 9) Token / context budgeting + graceful degradation (hard rules)
- **Never claim work is complete** (or mark a phase “DONE”) due to token limits, context limits, time pressure, or uncertainty.
- If you suspect you may run out of token/context budget before completing the phase, you must:

  1. **Stop new scope immediately**
     - No new features, no refactors, no “bonus” improvements.

  2. **Finish at the nearest logical boundary**
     - Complete the smallest coherent slice (tests + implementation), **or**
     - Stop after tests are written but before implementation (only if that’s the cleanest boundary).

  3. **Run validation if feasible**
     - Run `make validate` if feasible within budget.
     - If not feasible, explicitly state what was not run and why.

  4. **Produce a Handoff / Continuation Document**
     - Create/update a single handoff artifact (one per phase) that enables another developer/agent to continue without re-discovery.

### Required: Handoff / Continuation Document (one per phase)
When stopping early (for tokens or any other reason), create/update a single handoff artifact containing:

- **Current state**
  - What is fully complete vs partial (explicitly)
  - Branch + key files modified
- **Next steps (ordered checklist)**
  - The next test to write/run
  - The next file/function to implement/change
- **Validation status**
  - What was run (`make validate`, tests, lint, typecheck)
  - What failed (short error summaries) and what was not run
- **Open questions / blockers**
  - Ambiguities to resolve before proceeding
- **Context snapshot**
  - Key assumptions used
  - Relevant doc references (paths/section names)
  - Important design constraints discovered

**Format constraint:** concise bullet points, no prose walls, no code samples.

### Early warning threshold
- As soon as you estimate **< ~15% remaining token/context budget**, issue a warning and shift to “wrap-up mode”:
  - stop starting new tasks
  - prioritize clean boundary + handoff doc
  - ensure status is not misleading

---

## 10) Change reporting expectations (each logical step)
For each logical step/commit-sized unit of work, report:
- Tests added/updated
- Implementation changes (high level)
- Validation status (`make validate` result)
- Any risks, open questions, or deviations (should be none unless approved)
- If stopping early: **why**, the **exact stopping point**, and **what to do next** (and ensure the handoff doc is updated)
