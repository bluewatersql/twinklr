---
type: learning
status: active
created: 2026-11-17
updated: 2026-11-17
confidence: confirmed
tags: [caching, identity, config, upgrades, cost]
---

# Removing or Renaming a Hashed Model Field Re-Keys Caches and Refuses Old Records

Several identities in Twinklr are hashes of a Pydantic `model_dump`, not of the file a
user wrote. Removing a field from such a model, or renaming one, changes the hash for
every user even when their files and the rendered output are unchanged. Verified on
`feat/mh-true-up-p3` at `24c22b79`.

| Identity | What it hashes | Effect of a changed dump |
|---|---|---|
| Session id (`derive_session_id` → `config_fingerprint`, `core/caching/identity.py`) | `twinklr run`/`display`: app and job configs; `twinklr show`: those and the fixture group (`cli/show_cmd.py`, `cli/main.py`) | Every cached agent stage misses once: the next run of each song plans again and pays |
| Moving-head planner cache key (`MovingHeadPlannerOrchestrator.get_cache_key`) | Includes each offered template's description | A description change re-plans the moving heads (paid) |
| Live plan (`rig_sha256`, `job_sha256`, `cli/main.py`) | `rig.model_dump_json()`, `job_config.model_dump_json()` | `twinklr regenerate` refuses every sequence injected before the change until `twinklr inject` runs again |
| Render fingerprint (`sequencer/moving_heads/identity.py::render_fingerprint`) and record `template_sha256` | Template and fixture-group dumps, revision string | `eval-report` on an older checkpoint reports `RENDER_FINGERPRINT_MISMATCH`; pins and goldens need their fingerprints re-recorded (frames unchanged) |

## What happened

In the single-renderer cutover, removing `moving_heads.mode` and `transitions` from the
job model (C1.2) changed every session id and live-plan job digest; removing old fixture
fields (C1.3) changed every `twinklr show` session id and every live-plan rig digest; and
dropping a tag from the template descriptions (C1.4) re-keyed the moving-head planner
stage. The first C1.3 record said caches were unaffected; the independent review found
the session-id and `regenerate` consequences, and the owner was told before merge.

## Practice

When a change removes or renames a field of a model that is dumped into a hash, sweep
every caller of `derive_session_id`, `config_fingerprint` and `model_dump` on that model
(cache keys, record digests, fingerprints), list the paid re-plans and refusals in the
change record, and tell the owner before merge. Do not add a compatibility key that keeps
the old dump: that is a second path (shared guardrail 9).

## Related

- [C1.2 breaking changes](../../changes/2026_11_12_mh_true_up/evidence/2026-11-16-c1-2-deletion/README.md#7-breaking-changes),
  [C1.3 breaking changes](../../changes/2026_11_12_mh_true_up/evidence/2026-11-16-c1-3-model-narrowing/README.md#5-breaking-changes),
  [C1.4 user-visible changes](../../changes/2026_11_12_mh_true_up/evidence/2026-11-17-c1-4-renames/README.md#2-user-visible-changes)
- [Moving heads have one renderer](../decisions/mh-single-renderer.md)
