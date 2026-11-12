# Complete a Handoff

Use at the end of every substantive work session on an active change.

Fill in [changes/_templates/handoff.md](../../changes/_templates/handoff.md) in the change
folder, replacing the previous handoff. The bar: a new agent can continue from the handoff
alone, without any prior chat.

- State the status plainly. Disclose failed or skipped validation.
- Give exact validation commands with their actual results.
- List files created, modified, and deleted.
- Record decisions, assumptions, and deviations from the plan.
- Record branch, commit, and PR references.
- Name the next action and any pending owner decision.
- Update the change's row in [changes/ACTIVE.md](../../changes/ACTIVE.md).
- If the session produced durable knowledge, run [session-closeout.md](session-closeout.md).

A long-running campaign may keep an append-only dated log, but its first section is always
the current "start here" state.
