---
title: Phase 3 live end-to-end run — prerequisites, blockers, and result
status: done
date: 2026-08-29
change: post-refactor-validation
---

# Phase 3 live end-to-end run — RESULT: PASS

The refactored engine ran a **live** end-to-end moving-head show on
`data/music/11 - Need A Favor.mp3` (public OpenAI, owner's real 4-MH rig) and emitted a
valid `.xsq` whose technical sophistication **meets or exceeds** the pre-refactor
baseline. Four schema/provisioning blockers and **two real code bugs** were found and
fixed along the way (see below). Total live spend ≈ **$1–2** (well under the $25 budget;
~93k tokens for the successful run).

## Sophistication vs. baseline (Phase 1 metrics extractor)

| Metric | Baseline (pre-refactor) | Live (post-refactor) |
|---|---|---|
| Placed effects | 262 | **396** |
| Distinct DMX settings (effectdb) | 262 | **365** |
| Value-curve channels | 622 | **1306** |
| Distinct effect types | DMX | DMX |
| Max layers | 2 | 2 |
| Timing grid | 20 ms | 20 ms |
| element_count | 11 | 4 |
| max_dmx_channel | 16 | 13 |

More placed effects, more distinct DMX settings, and ~2× the value-curve channels
(smoother continuous motion). `element_count`/`max_dmx_channel` differ only because the
coerced 4-MH rig carries no semantic-group models (effects land on 4 individual models) —
not a sophistication regression. This satisfies the owner's bar: same level of
advanced/technical implementation detail.

## Code bugs found and fixed (TDD, red-first)

1. **GPT-5 line rejects `temperature`** (`agents/providers/capabilities.py`).
   Sending `temperature` alongside a reasoning effort is a terminal HTTP 400 on OpenAI
   reasoning models. The macro planner (job-config planner override onto the 5.2 line +
   spec-default `medium` effort) hit this. P2-5 only stripped temperature for the `gpt-5.6`
   prefix; the fix broadens the model-capability prefix to the whole `gpt-5` reasoning line
   so every sibling reasoning model has temperature stripped while `reasoning_effort` is
   preserved. Non-reasoning models (gpt-4.1/gpt-4o) keep temperature.
2. **Zero-duration emission segments** (`sequencer/moving_heads/export/xsq_adapter.py`).
   `FixtureSegment` permits `t1_ms == t0_ms` but `EmissionRequest` requires
   `0 <= start < end`. The transition planner produced 12 zero-width overlaps
   (`overlap_start == overlap_end`) for adjacent sections, aborting the whole render. The
   adapter now skips zero-duration segments (with a warning), consistent with its existing
   empty-channel / unmapped-fixture skips. (Upstream follow-up: the transition planner
   should not emit zero-width overlaps in the first place.)

## Environment / config blockers resolved (no code change)

- **TLS**: the OpenAI SDK (httpx/certifi) failed with `CERTIFICATE_VERIFY_FAILED`
  (self-signed cert in chain) behind a TLS-intercepting proxy that `curl` trusts via the
  macOS keychain. Fixed for the run shell by building a CA bundle from the keychains +
  certifi and exporting `SSL_CERT_FILE` (`artifacts/live-validation/ca-bundle.pem`). No
  app code was changed; consider documenting this for other proxied dev machines.
- **Stale `fixture_config.json`**: rejected by the current schema (removed fields
  `channel_count`, `dmx_start_address`, `dmx_universe`, `movement_speed`, and nested
  `orientation.*`). Iteratively coerced to `fixture_config.valid.json`.
- **Stale `job_config.json`**: `schema_version` must be `'3.0'`; removed fields `debug`,
  `include_notes_track`, `planner_features`. Coerced to `job_config.live.json`.
- **60s default agent timeout** (`AgentConfig.timeout_seconds`) is too low for `gpt-5.x`
  reasoning models (profile alone took ~47s; macro exceeded 60s). Worked around by
  bumping the scratch job-config agent timeouts to 300s. **Recommended code fix**: raise
  the default (e.g. to match the 300s retry-policy default) so reasoning-model stages do
  not flake.

## Original provisioning note (historical)

All **offline** prerequisites were complete; the paid run was initially blocked on a live
provider provisioning decision. The owner rotated the key and chose public OpenAI. The
first `.env` key returned 401; the rotated `sk-svcac…` key is valid and its catalog
includes `gpt-5.2`, `gpt-5-mini`, and the `gpt-5.6-sol/terra/luna` family — so the
configured models were never the problem; TLS + config drift were. No budget was spent
reaching the provisioning conclusion (proven with a $0 models-list / `curl` probe).

## Blocker (evidence-backed, $0 spend)

- Network egress works: `curl https://api.openai.com/v1/models` completed in ~3.5s.
- The `.env` `OPENAI_API_KEY` returns **HTTP 401** against `api.openai.com` — i.e.
  it is not a valid public-OpenAI key (rotated, or belongs to a gateway).
- Configured models are **not public-OpenAI models**: `job_config.json` uses
  `gpt-5.2` (plan/impl/refine) and `gpt-5-mini` (judge); `OPENAI_MODEL="gpt-5.2"`.
  The `terra`/`luna`/`sol` family named elsewhere is likewise gateway-style.
- The repo configures **no gateway `base_url`**: `AppConfig.llm_base_url` defaults
  to `https://api.openai.com/v1`, there is **no `config.json`**, and `.env` sets no
  base URL. So as-configured, a live `twinklr run` 401s on the first LLM call.
- The Ollama provider path requires a **loopback** `base_url`
  (`AppConfig` validator: "Ollama llm_base_url must be an HTTP(S) loopback
  endpoint"), so "cloud-hosted Ollama" needs a local proxy to be usable.

**To unblock, the owner must supply one working live configuration**, e.g.:
- an OpenAI-compatible **gateway base_url + valid key** whose catalog includes the
  planner/judge models, or
- a **local Ollama** endpoint (loopback) with the intended models pulled, or
- a valid **public-OpenAI key + public model ids** (e.g. `gpt-4.1`, `gpt-4o`).

## Completed offline prep (ready to execute the moment provider is supplied)

- **Owner rig coerced to current schema.** `fixture_config.json` was stale by
  fields the current schema rejects as "removed because they never affected
  output": top-level `channel_count`, `dmx_start_address`, `dmx_universe`,
  `movement_speed`; and nested `orientation.{resting_position,
  tilt_above_horizon_deg, tilt_up_dmx}`. An iterative strip produces a valid
  4×`FixtureInstance` group that `expand_fixtures()` + `rig_profile_from_fixture_group`
  accept. Written to `artifacts/live-validation/fixture_config.valid.json` (gitignored).
  → This is itself a real finding: the owner's real MH rig config cannot be
  loaded by the current build without this coercion.
- **Scratch live job config staged**: `artifacts/live-validation/job_config.live.json`
  (copy of `job_config.json` with `fixture_config_path` → the coerced rig;
  `max_iterations=2` to bound cost).
- **Audio confirmed present**: `data/music/11 - Need A Favor.mp3` — the same song as
  the tracked MH regression baseline, so the live `.xsq` is directly comparable via
  the Phase 1 parity harness (`tests/regression/xsq_metrics.py`).

## Run command (once a working provider is configured)

```bash
# provider config = a working config.json (base_url + key) OR exported env
uv run --frozen twinklr run \
  --audio "data/music/11 - Need A Favor.mp3" \
  --config artifacts/live-validation/job_config.live.json \
  --out artifacts/live-validation/run-need-a-favor \
  --app-config config.json
```

Then extract metrics from the emitted `*.xsq` and compare to
`tests/regression/baselines/11_need_a_favor.metrics.json` (structural parity +
comparable effect volume). Capture token/cost from the run's LLM logs against the
$25 total budget (≤$5/run target).
