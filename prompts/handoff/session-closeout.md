# Session Closeout and Memory Promotion

Use when closing a change or a significant session to decide what knowledge outlives the
task. This is the only path from session discoveries into `memories/` and `context/`.

1. **Harvest.** Review the work — change notes, validation records, surprising failures,
   owner rulings — and list what a future agent would otherwise have to rediscover.
2. **Filter.** Reject transient debugging state, TODOs, raw error output, speculation,
   anything the repository already records (code, tests, Git history), and agent-native
   memory that cannot be verified against repository evidence. Stage an unverified item in
   `memories/inbox/` only if it is worth revisiting, with the missing verification named.
3. **Classify and place.**

   | Discovery | Destination |
   |---|---|
   | The system now works differently | The owning `context/` page, and `context/current-state.md` if operationally significant |
   | A choice future agents must understand | `memories/decisions/` (decision, context, rationale, consequences) |
   | A non-obvious behavior, with evidence | `memories/learnings/` |
   | A durable limitation that shapes design | `memories/constraints/` |
   | A validated reusable technique | `memories/patterns/` |
   | A refined procedure | The relevant `prompts/` file |
   | State of in-flight work | The change's `handoff.md` |

4. **Update, don't duplicate.** Search `context/` and `memories/` first and update the
   existing owner. Delete memories proven wrong.
5. **Record provenance.** Start from [templates/memory.md](../../templates/memory.md) or
   [templates/decision.md](../../templates/decision.md); the frontmatter schema is in
   [context/INDEX.md](../../context/INDEX.md#metadata-convention). Date each entry and
   link the originating change and related code.
6. **Close the loop.** Update `memories/INDEX.md` and `context/INDEX.md` if entries
   changed. If the change is complete, move its row in
   [changes/ACTIVE.md](../../changes/ACTIVE.md) to "Recently closed" and confirm nothing
   authoritative remains only inside the change folder.
