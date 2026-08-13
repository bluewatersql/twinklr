# P3-T7 — Assets revival (D13)

Phase: 3 (Show Convergence / M3) · Lane: A (assets) · Executor: sonnet · Verifier:
opus · Depends on: P2P-T10 (model retarget)

⚖ **Owner-decision-bearing.** This task turns on a paid image-generation path. The
owner reviews: the per-run spend cap value and its default, whether the capability is
opt-in or on-by-default, and the activation surface (flag/config key) that replaces
today's dead `enable_assets` gate.

## Objective

`agents/assets` is ~2,500 LOC of coherent, well-tested, completely unreachable code
that generates imagery for xLights Pictures effects. D13 revives it as a part-2
capability. This task fixes the three verified defects that make its paid work unsafe
to repeat — a catalog that silently loses the record of everything already paid for, a
reuse key that collides across songs, and a `gather` that throws away paid siblings —
moves the image calls inside the provider framework on `gpt-image-2`, and adds a
per-run spend cap and a cache that actually holds.

## Evidence & background

Findings: **P3-F28a** (LOW — dormant code) and **P3-F28b** (HIGH — no cost controls; a
reactivation gate), split at verification; **P3-M-J**, **P3-M-K**, **P3-M-L** (all
HIGH, assets, reactivation-gated); **P3-F29** (the reachable paid path is a script, not
the stage), **P3-F19** (path traversal), **P3-F30** (provider-type confusion),
**P3-F31** (absolute paths documented as relative), **P3-F32** (unimplemented
scaffolding). Decision **D13**. Detail:
`.../reviews/phases/llm-agents-and-planning.md` §4.8 and §10;
`.../reviews/verification.md` §"Phase 3".

### D13, quoted

> **D13 (new, was quarantined) — Assets/image generation is a part-2 capability.**
> xLights adding first-party AI image generation is *evidence the need is real*
> (Pictures effects want imagery). Revive `agents/assets` in M3 with its verified
> defects fixed (non-atomic error-swallowing catalog, cross-song reuse-key collisions,
> gather-without-return_exceptions), on `gpt-image-2` (deadline: image-1.5 retires
> 2026-12-01), inside the provider framework. The "spend hazard" framing is withdrawn;
> normal cost controls (per-run cap + cache) suffice.

### The re-bill mechanism — use THIS one

> **RE-BILL MECHANISM CORRECTED.** The author claimed FAILED entries are excluded from
> reuse (`models.py:326,350`) so post-billing validation failures
> (`generator.py:239-248`) get re-billed. **That mechanism is rejected**:
> `_process_image_bytes` resizes the decoded image to the requested dimensions before
> `_validate_image` compares them, so the dimension check is tautological and the
> post-billing FAILED path it depends on does not arise in practice. The **real**
> re-bill risk is the catalog itself (**P3-M-L**): it is the sole record of paid work,
> is written non-atomically, is saved only after all generation completes
> (`stage.py:216`), and `load_catalog` swallows every parse error and silently starts
> fresh (`catalog.py:61-66`). Any of those three — mid-run failure, torn write, or a
> corrupt file — discards the record of everything already paid for and causes a full
> regeneration on the next run. There is also no `output_path.exists()` short-circuit
> before calling the API.

> **P3-M-L — the catalog is the sole record of paid work and is written unsafely**
> `HIGH` (assets, reactivation-gated) · `CONFIRMED` · **FIX**
> `save_catalog` (`catalog.py:71-84`) does a direct `write_text` — no
> temp-file-plus-rename, so a crash mid-write leaves a truncated JSON file.
> `load_catalog` (`:42-67`) catches **every** exception and silently returns a fresh
> empty catalog on any parse error. It is written once, after all generation
> (`stage.py:216`). Any of mid-run failure, torn write, or corruption discards the
> record of all paid work and triggers full regeneration. This is the correct mechanism
> behind P3-F28b's re-bill risk, replacing the author's rejected dimension-validation
> story.

> **Do not implement the rejected story.** Nothing in this task should "fix" image
> dimension validation as a cost control. `_process_image_bytes` resizes before
> `_validate_image` compares; the check is tautological and the failure path it
> implies does not arise.

Verified at baseline: `agents/assets/catalog.py:42-67` — `load_catalog` wraps the read
in `try: … except Exception: logger.warning("Failed to load catalog from %s, starting
fresh", …)` and falls through to `return AssetCatalog(catalog_id="default")`.
`catalog.py:71-84` — `save_catalog` does `catalog_path.write_text(json.dumps(data,
indent=2), …)` with no temp-file-plus-rename. `agents/assets/stage.py:216` —
`save_catalog(catalog, catalog_path)` runs once, after all generation.

### The cross-song reuse-key collision

> **P3-M-K — asset reuse keys collide across songs**
> `HIGH` (assets, reactivation-gated) · `CONFIRMED` · **FIX**
> The pre-enrichment reuse key is `spec_id + width + height` (`catalog.py:119-149`) and
> `spec_id` derives from motif/directive identifiers (`request_extractor.py:213,382`)
> that carry **no song or run scope**. Two different songs producing the same motif id
> therefore share a cached image. Combined with the `.lower()`/space-folding filename
> collapse (P3-F19), one file can back several logically distinct catalog entries.

Verified: `request_extractor.py:203-213` — `_build_spec_id(motif_id, category)` returns
`f"asset_{category.value}_{motif_id}"`; `:382` — narrative specs use
`spec_id=f"asset_{directive.category}_{directive.directive_id}"`. Neither carries song
or run identity. `models.py:330-350` — `find_by_spec_id(spec_id, width, height)` is the
pre-enrichment lookup; `catalog.py:119-149` (`check_reuse_by_spec_id`) is its caller.
`generator.py:52-62` — `_build_output_path` uses `spec.motif_id or spec.spec_id` with a
single `.replace(" ", "_").lower()` transformation.

### The discarded-paid-work gather

> **P3-M-J — asset enrichment `gather` without `return_exceptions` discards paid
> sibling work** `HIGH` (assets, reactivation-gated) · `CONFIRMED` · **FIX**
> `asyncio.gather(*[_enrich_one(s) for s in image_specs_to_enrich])` (`stage.py:181`)
> and the generation gather (`:209`) both omit `return_exceptions=True`, while
> `enrich_spec` raises on any failure (`prompt_enricher.py:150`). One failure
> propagates out, the stage returns `failure_result`, and **every sibling call already
> paid for in that batch is discarded** — with no catalog write (P3-M-L), so the next
> run repeats and re-bills all of it.

Verified: `stage.py:181` and `:209` are bare `asyncio.gather(...)`;
`prompt_enricher.py:148-155` raises `RuntimeError` when the agent result is
unsuccessful or of an unexpected type.

### The cost-control gate (P3-F28b)

> `gpt-image-1.5`, always 1024×1024 (`models.py:129-130`, `image_client.py:60-61`),
> `n=1` hardcoded (`:183`), and **no cost cap, budget check, dry-run, or confirmation
> gate** (grep-verified). Image count is bounded only by `GroupPlanSet.
> narrative_assets`, which has no `max_length` (`group_plan.py:137`) — **an
> LLM-authored list length directly determines the number of paid API calls**.
> `Semaphore(5)` (`stage.py:197`) limits rate, not total.

Verified: `sequencer/planning/group_plan.py:137` and `:186` both declare
`narrative_assets: list[NarrativeAssetDirective] = Field(default_factory=list)` with no
`max_length`. Both sites need the bound.

### The activation path (what the flag actually is today)

From the phase plan's notes for spec authors:

> T7 keeps `enable_assets`-style gating but documents the real activation path (the old
> flag was gated off everywhere; the paid path was a demo script's --live).

From P3-F28a / P3-F29: `AssetCreationStage` is constructed at exactly one site,
`pipeline/definitions/display.py:167-178`, behind `enable_assets: bool = False`
(`display.py:56`); the only non-test `build_display_pipeline` caller passed `False`
(`scripts/demo_sequencer_pipeline.py:565`); `cli/main.py:19` imported only
`build_moving_heads_pipeline`. Meanwhile:

> `scripts/demo_asset_pipeline.py` bypasses the stage, imports the generator and client
> directly (`:31-47`), and constructs a real `AsyncOpenAI` under `--live` (`:678`,
> `:776-778`). … Stage 4 must treat this script, not `enable_assets`, as the paid-call
> hazard.

Note P3-T3 wires the display pipeline into the CLI with `enable_assets` still False;
this task is what makes flipping it safe.

### Secondary defects to fix in the same pass

- **P3-F19 path traversal** (latent until the flag flips, then live): `_build_output_path`
  (`generator.py:52-62`) builds the filename from `spec.motif_id or spec.spec_id` with
  only `.replace(" ", "_").lower()`; `/`, `..`, and leading `/` pass through, and
  `mkdir(parents=True, exist_ok=True)` (`image_client.py:105`) creates whatever it
  resolves to. Both feeders are LLM-authored (`motif_id` from `section.motif_ids` /
  `param_overrides["motif_hint"]`, `spec_id` from `directive.directive_id`, constrained
  only by `min_length=1`).
- **P3-F30 provider-type confusion**: `stage._build_image_client` (`:273-282`) guards on
  `hasattr(provider, "_async_client")`, true for `AnthropicProvider` too, and would hand
  an `AsyncAnthropic` to `OpenAIImageClient`; a broad `except Exception` downgrades a
  credentials failure to `"No image client provided"` with 100% FAILED entries.
- **P3-F31 absolute-vs-relative paths**: `models.py:189,212` document "relative to
  assets/ root"; `image_client.py:109`, `generator.py:253`, `text_renderer.py:103` write
  absolute paths, so `catalog.py:106`'s existence check misses every cache hit if the
  tree moves — "a silent full-regeneration (and full re-bill) trigger".
- **P3-F32 scaffolding**: `AssetSpec.{matched_template_id, text_timing_ms, token_budget,
  format}`, `CatalogEntry.embedding`, `AssetCategory.{IMAGE_PLATE, TEXT_LYRIC, SHADER}`,
  `enrich_spec(builtin_prompt=…)` never passed non-`None`.

## Current behavior

- The stage is unreachable; the only way to spend money is a demo script's `--live`.
- If it were reachable: unbounded image count driven by an LLM-authored list, no cap,
  no dry-run, catalog written once at the end non-atomically, parse errors swallowed,
  reuse keys shared across songs, and a single enrichment failure discarding every paid
  sibling in the batch.
- Image client is `gpt-image-1.5` (retires 2026-12-01), constructed by reaching into a
  provider's private `_async_client`.

## Target behavior

1. **Catalog is durable and honest.**
   - `save_catalog` writes atomically (temp file in the same directory + `os.replace`).
   - The catalog is saved **incrementally** — after each successful generation, or at
     minimum after each batch — never only at the end. A run killed halfway must leave
     a catalog recording everything paid for up to that point.
   - `load_catalog` distinguishes "absent" (start fresh, INFO) from "present but
     unreadable" (**raise**, or quarantine the file and raise). Silently starting fresh
     on a corrupt catalog is the re-bill mechanism and must be impossible.
2. **Reuse keys are song/run-scoped.** `spec_id` (or the reuse key derived from it)
   carries song identity, so two songs producing the same motif id do not share an
   image unless sharing is explicitly intended. If cross-song reuse is desirable for
   some categories, it is opt-in and named, not accidental.
3. **Filenames are safe and collision-free.** `_build_output_path` sanitizes to a
   restricted charset and rejects (not strips) path separators, `..`, and absolute
   prefixes; distinct spec ids cannot collapse to one filename. A traversal attempt
   raises with the offending value in the message.
4. **No paid work is discarded.** Both gathers use `return_exceptions=True`; partial
   failures are recorded per-spec (FAILED entries with the error), the catalog is
   written, and the stage reports partial success rather than throwing away the batch.
5. **Cost controls.**
   - A **per-run spend cap** (config-driven, with a conservative default) counted in
     both images and estimated dollars; when the cap would be exceeded the run stops
     requesting and reports what it skipped.
   - A **hard bound on image count** independent of the LLM: `narrative_assets` gains a
     `max_length`, and the stage clamps regardless.
   - A **dry-run mode** that reports exactly what would be generated and the estimated
     cost, making zero API calls.
   - An `output_path.exists()` short-circuit before any API call.
6. **Cache actually hits.** Catalog paths are stored relative to the assets root (as
   documented) and resolved against the current root at read time, so moving the
   artifacts tree does not trigger a full regeneration.
7. **Inside the provider framework, on `gpt-image-2`.** The image client is constructed
   through the provider framework rather than by reaching into `provider._async_client`;
   a non-OpenAI provider produces a clear, actionable error rather than an
   `AttributeError` after enrichment has already been paid for. Model id comes from
   config (P2P-T10's consolidation), defaulting to `gpt-image-2`.
8. **Honest activation surface.** One documented, config-driven way to enable the
   capability, wired end-to-end from the CLI through `build_display_pipeline`. The
   documentation states the default (off), the cap, and where images land. The
   `--live`-bypassing demo script is deleted or made to route through the same guarded
   path — it must not remain a second, uncapped door.
9. **Dead scaffolding removed.** The P3-F32 list is deleted, not left as
   documented-looking capability. (`CC-1`'s dead-config class and `P7-M2`'s "user guide
   is not a reliable behavior description" are the standing reasons.)

**Non-goals**

- Do **not** implement image-quality evaluation or a vision judge for generated imagery
  (P3-T8 owns show-level evaluation; asset aesthetics are out of scope).
- Do **not** build the builtin-template matching feature (`builtin_prompt`) — delete the
  scaffolding instead.
- Do **not** change how the display composition consumes resolved assets
  (`engine.py:827-910`, the Pictures overlay path) beyond what the path/relative-path
  fix requires.
- Do **not** flip the default to on. That is the owner's decision (⚖).

## Implementation approach

Files expected to change (all under
`packages/twinklr/core/agents/assets/` unless noted): `catalog.py` (atomic write,
incremental save, strict load), `stage.py` (gathers, cap, dry-run, client
construction, incremental save), `generator.py` (path building, exists-check),
`image_client.py` (model from config, relative paths), `models.py` (scaffolding
deletion, relative-path semantics), `request_extractor.py` (song-scoped spec ids),
`prompt_enricher.py` (scaffolding parameter), plus
`packages/twinklr/core/sequencer/planning/group_plan.py` (`max_length` on
`narrative_assets` — note there are **two** declaration sites, `:137` and `:186`, and
both need the bound), `packages/twinklr/core/pipeline/definitions/display.py` (the
activation surface), `packages/twinklr/cli/main.py` (the flag/config wiring), and
`scripts/demo_asset_pipeline.py` (delete or route through the guarded path).

Design decisions already made — do not relitigate:

- The re-bill mechanism is the catalog (M-L). The resize/validation story is **rejected**.
- Cost controls are "normal" — per-run cap plus cache. D13 explicitly withdraws the
  "spend hazard" framing; do not build an elaborate budgeting subsystem.
- `gpt-image-2`, from config, via the provider framework. The 2026-12-01 retirement of
  image-1.5 is the deadline.
- Gating stays flag-shaped (`enable_assets`-style) but must be *reachable* and
  *documented* — the review's criticism is that the old flag was gated off everywhere
  while the real paid path was a script.

Sequencing constraints copied verbatim from `build/plan/00-overview.md`:

> Model retarget must set `reasoning.effort` explicitly and include the out-of-framework
> call site `normalization/llm_review.py` (P2P-T10).

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases
> land) — specs cite symbol + file, with line numbers as hints only.

> Nothing in this program authorizes pushes/PRs to remotes or paid API calls beyond
> each spec's stated test budget; live-LLM and xLights-GUI tests are marked
> `LOCAL-ONLY` in specs and excluded from CI.

> ⚖-marked tasks (owner-decision-bearing) say so at the top and name what the owner
> reviews.

From `build/plan/06-phase-3-show-convergence.md`: "**Lane A (assets)**: T7
(agents/assets) — independent until T5." Rebase on P3-T5 if it merges first.

## Acceptance criteria

1. **Atomicity**: killing the process mid-`save_catalog` (simulated by patching the
   write) leaves the previous catalog intact and readable — never a truncated file.
2. **Incremental durability**: a run that fails on the Nth generation leaves a catalog
   containing the N-1 successful entries. Test by injecting a failure.
3. **Corrupt catalog is loud**: a malformed `asset_catalog.json` causes a raise (or a
   quarantine-and-raise), not a silent empty catalog. **This test fails on today's
   code.**
4. **Song scoping**: two runs for different songs producing the same motif id generate
   two distinct assets with distinct catalog entries and distinct files.
5. **Traversal rejected**: a `directive_id` of `"../../../../etc/cron.d/x"` raises with
   the value named; nothing is created outside the assets root.
6. **Partial failure preserves siblings**: with 5 specs where the 3rd raises, the other
   4 results are retained, recorded in the catalog, and reported; the stage does not
   return a bare failure that discards them.
7. **Cap enforced**: with the cap set to 2 and 5 specs pending, exactly 2 API calls are
   attempted (assert on the mocked client) and the run reports 3 skipped.
8. **Hard bound**: a `GroupPlanSet` with 500 `narrative_assets` cannot produce 500
   requests; `max_length` rejects it at model validation and the stage clamps
   defensively.
9. **Dry run**: dry-run mode makes **zero** calls on the mocked client and prints the
   would-generate list with an estimate.
10. **Exists short-circuit**: a spec whose `output_path` already exists makes no API
    call.
11. **Relative paths**: catalog entries round-trip through a moved assets root and still
    resolve — cache hits survive the move.
12. **Provider safety**: constructing the image client under an Anthropic-configured
    session raises a clear error naming the provider requirement, **before** any
    enrichment call is made.
13. **Model**: the configured image model defaults to `gpt-image-2` and is read from
    config, not hardcoded. `grep -rn "gpt-image-1.5" packages/` returns nothing outside
    docstrings/changelogs.
14. **Activation is real**: enabling the capability through the documented config path
    causes `AssetCreationStage` to appear in the built pipeline; the default remains
    off; `scripts/demo_asset_pipeline.py` no longer offers an uncapped `--live` door.
15. **Scaffolding gone**: the P3-F32 members are deleted; grep confirms no readers
    remain.

## Tests

All automated tests use a **mocked image client** and make zero paid calls. The assets
package's tests are already "the best-isolated in the tree (grep-verified: no live
network)" — keep that property.

1. `tests/unit/agents/assets/test_catalog_durability.py` — atomicity (#1), incremental
   save (#2), strict load (#3).
2. `tests/unit/agents/assets/test_reuse_keys.py` — song scoping (#4), relative-path
   round trip (#11).
3. `tests/unit/agents/assets/test_output_paths.py` — traversal rejection (#5),
   filename collision resistance.
4. `tests/unit/agents/assets/test_partial_failure.py` — sibling preservation (#6).
5. `tests/unit/agents/assets/test_spend_controls.py` — cap (#7), hard bound (#8),
   dry-run (#9), exists short-circuit (#10).
6. `tests/unit/agents/assets/test_client_construction.py` — provider safety (#12), model
   from config (#13).
7. `tests/unit/pipeline/test_assets_activation.py` — activation surface (#14), default
   off.
8. Regression: the existing 9 asset test modules (~2,267 lines) must pass or be updated
   deliberately; tests asserting deleted scaffolding are removed with a note.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .

uv run pytest tests/unit/agents/assets/ -v
uv run pytest tests/unit/pipeline/test_assets_activation.py -v

uv run pytest tests/ -q      # no NEW failures vs the verification.md baseline

# spend-safety greps (must be part of verification, not just review)
grep -rn "gpt-image-1.5" packages/ scripts/
grep -rn "asyncio.gather" packages/twinklr/core/agents/assets/   # all must pass return_exceptions=True
grep -rn "_async_client" packages/twinklr/core/agents/assets/    # must be empty
```

LOCAL-ONLY, paid:

- One live generation run to confirm `gpt-image-2` works end-to-end through the
  provider framework, the catalog records it, and a second run reuses the cache with
  **zero** additional calls. **Test budget: at most 4 generated images (~$0.20 at
  current image pricing), run once, by the owner or with explicit owner approval.** The
  second (cache-hit) run must cost $0 — that is the point of the test.
- Record in the PR body: images generated, cost, and the cache-hit confirmation.

Every other verification step is $0. No CI job may be able to reach the image API.

## Effort & risk

**Size: M.** Many small, well-understood fixes in one coherent package, plus the
activation wiring. Executor tier is sonnet (mechanical/bounded) with an opus verifier
because the failure mode is financial and silent.

**Main risk: reviving the path with a cost control that does not actually bound
spend.** The count is driven by an LLM-authored list today; a cap that is checked in
the wrong place (after enrichment, say) still bills for enrichment. *Mitigation*:
acceptance #7 asserts on **attempted API calls** at the mocked client, and the hard
bound (#8) is enforced at model validation, before any call.

**Secondary risk: fixing the wrong re-bill mechanism.** The original review's story was
rejected at verification; an executor reading only the phase doc's first draft would
harden dimension validation and leave the catalog exactly as unsafe as it is.
*Mitigation*: the corrected mechanism is quoted at the top of this spec with an explicit
"do not implement the rejected story" instruction, and acceptance #3 pins the real one.

**Third risk: the traversal fix arriving after activation.** `enable_assets=True` makes
P3-F19 live. *Mitigation*: acceptance #5 is in the same task as the activation wiring;
the capability cannot be enabled by this task's own path without the sanitizer present.
