# Recover From a Failed Agent Run

Use when resuming after another agent's run failed, was interrupted, or left unclear state.

1. Run `git status --short --branch`. Separate unrelated user changes from the failed
   run's edits and leave the former untouched.
2. Read the latest handoff or validation record in the change folder.
3. Rerun the failing command if feasible and capture the actual output. Do not rerun a
   paid, live, or sealed one-shot step; check its evidence record instead.
4. Identify the last coherent state from repository evidence (diffs, tests, logs), not
   from the failed agent's narrative.
5. Continue from that state. Record in the change folder what was salvaged, what was
   discarded, and why.
