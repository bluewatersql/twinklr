# Workflow: Session Closeout & Memory Promotion

Run at the end of substantial work, before ending the session.

1. **Review discoveries.** List what this session learned or decided that a future agent
   would otherwise have to rediscover.
2. **Classify each item:**
   - Current project truth (how the system now works) → `context/`
   - Durable decision / learning / constraint / pattern → `memories/`
   - State of in-flight work → `changes/<slug>/handoff.md`
   - Transient (debug output, dead ends, speculation, TODOs) → discard, or
     `memories/inbox/` only if plausibly durable but unverified
3. **Search before writing.** Check `context/` and `memories/` for existing coverage;
   **update** the existing document instead of duplicating. Delete memories proven wrong.
4. **Write with provenance.** Start from [templates/memory.md](../../templates/memory.md)
   or [templates/decision.md](../../templates/decision.md); frontmatter schema (`type`,
   `status`, `created`/`updated`, `confidence`, `tags`) is documented in
   [context/engineering/conventions.md](../../context/engineering/conventions.md).
   Link related documents.
5. **Handle change closure.** If a change completed: promote accepted architecture into
   `context/`, mark it closed in [changes/ACTIVE.md](../../changes/ACTIVE.md), leave its
   artifacts as history. A closed change must not be the only home of current truth.
6. **Update indexes** touched by your edits: `memories/INDEX.md`, `context/INDEX.md`,
   `changes/ACTIVE.md`.
7. **Do not promote** speculation, unverified assumptions, transcripts, or
   machine-specific details into durable memory.
