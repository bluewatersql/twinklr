---
type: learning
status: active
created: 2026-11-01
updated: 2026-11-12
confidence: confirmed
tags: [live-run, providers]
---

# Lessons from the first post-refactor live run (2026-08-29/30)

These come from the post-refactor-validation Phase 3 live moving-head run. Details and
evidence are in
[live-run-prereqs.md](../../changes/post-refactor-validation/notes/live-run-prereqs.md).
Each item below was fixed or verified on `main`. Lessons from later live runs carry their
own date.

- **GPT-5 reasoning models reject `temperature`.** Sending `temperature` together with a
  reasoning effort returns a terminal HTTP 400. The capability policy now strips
  temperature for the whole `gpt-5` reasoning line and keeps `reasoning_effort`
  (`packages/twinklr/core/agents/providers/capabilities.py`; `91677ab`, `9bd9461`). Any
  new model family needs a capability entry before its first live call. This same class
  caused P3-T4 attempt 2 to fail.
- **Reasoning latency exceeds short timeouts.** A 60 s agent timeout tripped the provider
  retry deadline on high-effort calls. The default is now 300 s (`d15ee03`,
  `config/models.py`). Thinking models also spend output tokens on reasoning, so size
  `max_tokens` with headroom.
- **Local config files drift from the schema.** `fixture_config.json` and
  `job_config.json` are gitignored and stale copies can hold fields the current schema
  rejects. Re-validate them before every live run; schema errors surface before any spend.
- **Degenerate geometry can abort a whole render.** Zero-width transitions and
  zero-duration emission segments are now dropped upstream (`a8ce12b`) and skipped
  defensively at the adapter (`08ce6d5`).
- **Claude cannot compile Twinklr's planner schemas (2026-11-12).** Claude's structured
  outputs return HTTP 400 `The compiled grammar is too large` for every planner schema
  (audio_profile, macro, group, holistic corrector, moving-head). It happens even for
  `audio_profile`, which has 7 union and 0 optional parameters, well within the documented
  explicit limits of 16 and 24. The judge, lyrics,
  enricher and vision schemas compile. The rejection depends only on the schema, comes
  back in 0.3 s, and generates no tokens.
  - The Anthropic adapter resends once with the schema carried only by the prompt, and
    remembers the rejection (`f0ae0da`).
  - Before claiming a new or enlarged schema is server-enforced on Claude, probe it once.
  - See the
    [evidence](../../changes/twinklr-reactivation-review/evidence/2026-11-12-claude-provider-live/README.md).
- **Ollama Cloud ignores `response_format` (2026-11-11).** The schema must travel in the
  prompt, and cloud models wrap their JSON in a Markdown fence. The runner injects the
  schema, and the providers unwrap a whole-response fence.
- **Corporate TLS interception.** Behind an intercepting proxy, the Python HTTP stack
  needs the proxy CA via `SSL_CERT_FILE`. This depends on the environment, not on code.

Related: [current-state](../../context/current-state.md) · the campaign
[HANDOFF](../../changes/twinklr-reactivation-review/build/plan/HANDOFF.md).
