# Phase 5 — Display Rendering & xLights I/O

_Stage 3 phase review. Baseline `aa8d325` (main, clean). Authored 2026-08-13 by the
phase-5 author (opus), read-only against source. Every claim below cites
`path:line` observed at this baseline. Absence claims ("no consumer", "dead") are
exhaustive-grep inference over `packages/`, `tests/`, `scripts/`, `docs/` and are
marked INFERRED where load-bearing. No code was executed by the author — the items
flagged **Stage 4** need a live run to settle._

**Phase verification status: VERIFIED (2026-08-13, opus critic, non-author).**
_11 ACCEPTED, 4 REVISED, 0 REJECTED, 6 verifier-added findings (P5-M1…M6) adopted.
Revisions applied in place and attributed inline; verification record:
[../verification.md](../verification.md) §"Phase 5". Four changes are substantive
enough that readers of the first draft must re-read them: **V1 is strengthened** (the
"needs hardware evidence" caveat was wrong — the repo declares the convention itself),
**V-contract is corrected on two facts** (`--xsq` is required, so the template branch
runs on every shipped run; and `profiling/` uses `XSQParser`, so the parser survives
the contract), **P5-F3 drops HIGH→MEDIUM with an inverted mechanism**, and **P5-F11 is
now CONFIRMED by the Stage 4 run**._

---

## 1. Scope & exclusions

**In scope (18,711 LOC across 5 trees):**

| Tree | LOC | Notes |
|---|---|---|
| `core/sequencer/display/` | ~8,300 | composition/, effects/ (protocol, registry, settings_builder, 24 handlers), export/ (writer, effectdb_registry), models/, palette/, templates/effect_map.py, renderer.py, recipe_renderer.py, xlights_mapping.py |
| `core/sequencer/templates/group/` | ~2,600 | recipe, store, catalogs, converter, affinity, target_expander, models/ (incl. the DisplayGraph→ChoreographyGraph migration) |
| `core/sequencer/theming/` | ~1,900 | catalog, models, builtins (themes/palettes/motifs/tags) |
| `core/sequencer/models/` | ~1,400 | template.py, moving_heads/rig.py, transition.py, enum.py, context.py |
| `core/formats/xlights/` | ~1,900 | sequence/{parser,exporter,models,compat,timeline}, layout/ |

**Explicitly excluded / N/A:**

- `core/agents/assets/` — owned by phase 3 per plan.md; this review does not assume
  its behavior. Asset overlay *consumption* (`engine.py:827-910`) is in scope; asset
  *generation* is not.
- `core/sequencer/moving_heads/` — phase 4. Two exceptions, read under the phase-5
  charter because they are the export boundary: `moving_heads/xsq_export.py` and
  `moving_heads/export/{xsq_adapter,dmx_settings_builder}.py`, which are the sole
  writers into `formats/xlights`. Findings about template *authoring* on that side
  remain phase 4's.
- `core/sequencer/vocabulary/` — phase 4 owns the contract; cited here only as a
  consumer (`duration.py:34-40`, `coordination.py:22-26`).
- Dimensions marked N/A for this phase: network/auth surfaces (none present),
  concurrency (all code here is synchronous and single-threaded), persistence
  (none — the only I/O is XML read/write and a JSON sidecar).

---

## 2. Purpose, entry points, contracts, state, invariants, dependencies, consumers

### 2.1 What this phase is

Two independent renderers converge on one file-format layer:

```
 moving-heads path (CLI-reachable)          display path (NOT CLI-reachable)
 FixtureSegment[]                            GroupPlanSet
   → XsqAdapter                                → CompositionEngine → RenderPlan
   → DmxSettingsBuilder (settings str)         → XSQWriter (handler dispatch,
   → EffectPlacement (dataclass)                  EffectDB + palette dedup)
   → xsq_export.export_to_xsq  ──────┐      ──────┘
                                     ↓
                          XSequence (Pydantic)
                                     ↓
                            XSQExporter → .xsq
```

**Entry points.**
`export_to_xsq()` (`moving_heads/xsq_export.py:28`) is the only export reachable from
`twinklr run`. `DisplayRenderer.render()` (`display/renderer.py:135`) is the display
entry point, called only from `DisplayRenderStage` (`pipeline/display_stages.py`),
which is only in `build_display_pipeline` — which `cli/main.py` never calls
(re-verified this phase; consistent with discovery §2).

**Contracts.**

- *Timing*: `BeatGrid` is the declared sole timing authority
  (`engine.py:126-128`). All display ms values pass through `TimingResolver`, which
  snaps to a 20 ms grid (`timing_resolver.py:164-174`). §5 shows the authority is
  broken in the window-expansion path.
- *Categorical vocabulary*: planners emit `PlanningTimeRef` (bar/beat) and
  `EffectDuration` (5 categories); the renderer owns every numeric. This is the
  accepted decision `memories/decisions/llm-plans-intent-renderer-implements-precision.md`,
  and in this phase it is implemented faithfully — see §9.
- *Settings string*: comma-separated `KEY=VALUE`, prefixes `E_` (effect), `B_`
  (buffer), `T_` (transition), `C_` (palette). Built by `SettingsStringBuilder`
  (`display/effects/settings_builder.py:33-44,182-188`) for display and by
  `DmxSettingsBuilder` (`moving_heads/export/dmx_settings_builder.py:42-90`) for
  moving heads. **These two builders share no code.**
- *Element naming*: `XLightsMapping.resolve()` (`display/xlights_mapping.py:63`)
  group-first, model fallback, then the raw choreo id.

**State & invariants.**
`CompositionEngine` carries mutable per-run state (`_layer_blend_modes`,
`_section_map`); `XSQWriter` is stateless per call but constructs fresh dedup
registries each `write()` (`writer.py:121-122`). Documented invariants that hold:
palette colors are validated `#RRGGBB` (`display/models/palette.py:71-78`), active
slots 1–8 (`:80-87`), `RenderEvent.intensity` ∈ [0,1], `EffectDBRegistry` reserves
index 0 (`export/effectdb_registry.py:36-39`). Documented invariants that do **not**
hold: "SEQUENCED = one group at a time" (P5-F2) and "BeatGrid is the sole timing
authority" for expanded windows (P5-F1).

**Dependencies.** `defusedxml` (via `core/parsers/xml.py:12`), `simpleeval` 1.0.3
(`recipe_renderer.py:13`), Pydantic v2, stdlib `xml.etree` for *writing* only.

**Consumers.** `formats/xlights/sequence` is consumed by both renderers, by
`core/profiling/` (layout only), and by `scripts/validation/`. `formats/xlights/layout`
has exactly one production consumer, `profiling/layout/profiler.py:9,17`, itself
unreachable from the CLI — the layout parser is live code on a script/test-only branch.

---

## 3. Representative execution paths inspected

1. **Moving-heads export (the only shipped path)** — `export_to_xsq`
   (`xsq_export.py:28-108`): template parse (`:53-56`) — **always taken, since `--xsq`
   is required at `cli/main.py:341`** → the never-executed fresh
   `SequenceHead(version="2024.10")` otherwise (`:65-74`) → timing layers (`:77-81`)
   → `XsqAdapter.convert` (`export/xsq_adapter.py:43`) → per-segment
   `DmxSettingsBuilder.build_settings_string` (`dmx_settings_builder.py:42`) →
   `EffectPlacement` → inline conversion to `Effect` (`xsq_export.py:88-96`) →
   `XSQExporter.export` (`exporter.py:37`).
2. **Display composition** — `DisplayRenderer.render` (`renderer.py:135`) →
   `CompositionEngine.compose` (`engine.py:179`) → per-section, per-lane, per
   coordination plan → window expansion for SEQUENCED/RIPPLE/CALL_RESPONSE
   (`engine.py:388-663`) → `RecipeCompiler.compile` (`recipe_compiler.py:59`) →
   `RecipeRenderer.render` (`recipe_renderer.py:61`) → overlap resolution
   (`engine.py:975`) → `XSQWriter.write` (`writer.py:100`) → handler dispatch →
   EffectDB/palette dedup → `Effect` on element layer.
3. **Parse → export round trip** — `XSQParser.parse` (`parser.py:47`) →
   `_parse_tree` (`:95`) → allow-listed models → `XSQExporter._build_tree`
   (`exporter.py:68`), regenerating the whole document.
4. **Fresh-sequence display export** — `DisplayRenderStage`
   (`pipeline/display_stages.py:239-248`) constructing an `XSequence` from nothing
   with `version="2024.01"`. This is the repo's only *generate-fresh* emitter and is
   directly load-bearing for V-contract (§10).

---

## 4. Implementation assessment

**Structure is good; the interior is uneven.** Module boundaries are clean and the
dependency direction is consistent (models ← composition ← renderer ← stage). Pydantic
models are used properly (frozen where appropriate, `extra="forbid"` on the display
models — in deliberate contrast to the parser models' `extra="ignore"`). Docstrings are
unusually complete. **Zero TODO/FIXME/HACK markers exist anywhere in the 18.7k LOC of
this phase** (grep over all five trees) — which reads less like "no known debt" than
like debt that was never written down, given §5.

**Effect handlers are a data table wearing 24 costumes.** All 24 handlers
(`display/effects/handlers/`, note: 24, not the 23 in the phase charter) implement the
same shape: read `event.parameters` with `.get(name, default)`, emit one
`builder.add(xlights_key, value)` per parameter, add buffer style, return. The only
computation in the entire package is `on.py:55` (`int(event.intensity * 100)`) and the
only conditional emission is `ripple.py:96-99`. Registration is explicit and correct —
24 imports, 24 `registry.register` calls, no duplicates, no orphans
(`handlers/__init__.py:52-96`). ~95% of ~2,200 handler LOC is mechanical and collapsible
to a per-effect `[(param, key, default)]` table. This is cheap, low-risk, and would
delete ~2,000 lines.

**The composition engine is where the real logic lives, and it is where the real bugs
are.** `engine.py` (1,096 lines) does target resolution, lane→layer allocation, window
expansion for three coordination modes, palette/intensity/transition resolution, asset
overlay emission, and overlap arbitration. Four defects (P5-F1, F2, F3, M2) all sit in
the seams between that engine and its collaborators — the timing resolver, the layer
allocator, its own instance state — rather than inside any one function. That is the
signature of a component whose collaborators changed underneath it while its own code
kept working on the old assumptions.

**The parser/exporter pair is competent for a fresh-write use and structurally wrong for
a merge use.** The parser is defensive in the right places (defusedxml, explicit
required-field errors, skip-with-warning on malformed effects) and the exporter is a
faithful inverse *of the parser's own model*. The problem is that the model is an
allow-list and the exporter regenerates the document — see §5 and P5-F5.

**Two parallel writers, quantified.** `XsqAdapter` (413 lines) + `DmxSettingsBuilder`
(329) versus `XSQWriter` (431) + `SettingsStringBuilder` (194) + `EffectDBRegistry` (74)
+ `PaletteDBRegistry` (62). Genuinely shared: the `XSequence` model and `XSQExporter`
(~740 lines). Genuinely duplicated: settings-string assembly (two independent
comma-joiners with independent, incompatible escaping stories — i.e. none), EffectDB
index management (`XSQWriter` dedups via a registry; `XsqAdapter` calls
`xsq.append_effectdb` per segment with **no dedup at all**, `xsq_adapter.py:191,322`),
and element/layer placement. The split is not arbitrary — DMX-channel output and
buffer-effect output really are different problems — but ~250 lines of the duplication
is accidental, and the dedup asymmetry is a concrete output-size regression on the
shipped path.

---

## 5. Tests & validation assessment

**Numbers.** 49 test files / ~9,950 LOC cover this phase — a healthy ratio against
18.7k LOC of source, and much better than discovery's package-level view suggested for
*display*. The distribution is what matters:

| Area | Direct tests | Assessment |
|---|---|---|
| `display/composition/` | 11 files | Real assertions, good edge cases (see caveat below) |
| `display/effects/` | registry, settings_builder, handlers/ | Adequate for mechanical code |
| `display/export/` | writer, effectdb_registry | Good |
| `templates/group/` | 13 files | Best-covered area in the phase |
| `theming/` | **0 direct** | Exercised only incidentally |
| `formats/xlights/sequence/` | **1** (`test_timeline.py`) | Parser, exporter, and `xsq.py` models have **no direct test** |
| `formats/xlights/layout/` | 0 direct (indirect via profiling) | — |

**Three findings about the tests themselves:**

1. **Three display tests cannot run in a fresh checkout.**
   `tests/unit/sequencer/display/composition/test_engine.py`,
   `.../test_sequenced.py` (`:63-72`), and
   `tests/unit/sequencer/display/test_renderer_overlay.py` build a `RecipeCompiler`
   from `TemplateStore.from_directory(repo/data/templates)`. `data/` is gitignored
   (`.gitignore:49`, confirmed by `git check-ignore`) and `data/templates` does not
   exist. `TemplateStore.from_directory` reads `index.json` unguarded
   (`templates/group/store.py:96-97`), so these raise `FileNotFoundError` at fixture
   time. Three more such tests exist outside this phase's scope (feature_engineering,
   scripts). **CONFIRMED by the Stage 4 run: 52 failures trace to the missing
   `data/templates`** — an order of magnitude beyond this review's initial "~6 test
   files" estimate. The consequence stands and sharpens: the coordination-mode expansion
   logic — the site of P5-F1 and P5-F2 — is untested in CI-equivalent conditions, which
   is precisely why both defects survived.
2. **The one security test tests the library, not the code.**
   `tests/unit/sequencer/display/test_recipe_renderer_security.py:28-54` calls
   `simple_eval` directly with the same allow-lists the production code uses, and
   `:13-20` asserts on the *source text* of `_evaluate_param`. Neither exercises
   `RecipeRenderer._evaluate_param`, so neither would catch the actual behavior:
   a malicious or malformed expression is swallowed by
   `except Exception: return pv.min_val or 0.0` (`recipe_renderer.py:121-122`) and
   produces a silently-wrong parameter with no warning — the per-layer warning
   collector at `:74-78` never sees it.
3. **No round-trip or golden test exists for `.xsq`**, confirming discovery. There is
   also **no sample `.xsq` file anywhere in the repository** (`find -name '*.xsq'`
   returns nothing; the only `<xsequence>` literals are the 22-byte stubs in
   `tests/unit/profiling/test_ingestor.py:75`). This is the single most consequential
   testing gap in the phase and it is what makes V4 unanswerable from the repo (§10).

---

## 6. Critical assessment

The display package is better engineered than the moving-heads path and less correct
than it looks. Its abstractions are the right ones — a `RenderPlan` intermediate, a
handler protocol, dedup registries, a trace sidecar — and they are the abstractions you
would keep in a rewrite. But three things undercut it:

**(a) The categorical vocabulary is applied twice, and the second application destroys
the first.** Window expansion computes exact millisecond schedules, then converts them
*back* into 1-indexed integer bar/beat and one of five duration buckets before handing
them to the timing resolver, which re-expands them. That is not "the renderer owns the
numerics" — that is the renderer computing numerics, discarding them, and recomputing
worse ones. P5-F1.

**(b) Outputs are computed and dropped in at least four places.**
`RenderedLayer.resolved_color` (the entire per-layer color-source resolution) is never
read by the compiler; `timing_offset_beats` is never read; `E_SLIDER_Mix` is injected
into `RenderEvent.parameters` where no handler will ever read it; and every recipe
parameter whose key does not happen to match a handler's `.get()` name vanishes
silently. This is the same failure mode Stage 2 identified in the agent layer — work
produced, no sink — reproduced inside the renderer, and it is why "wire the display
pipeline up and see" would produce plausible-looking output that is not what the
recipes describe.

**(c) The knowledge that would let anyone notice is absent.** No sample `.xsq`, no
round-trip test, no golden output, no committed preview, and the recipe corpus is
gitignored. Every claim about display output quality in this repository is unfalsifiable
from the repository. That is the reason to defer, and it is a stronger reason than the
one Stage 2 gives.

**What the code does not deserve criticism for:** the XML hygiene is genuinely good
(defusedxml everywhere, `ElementTree` handles attribute escaping so there is no
XML-injection path even with unescaped settings values), the simpleeval sandbox is
correctly configured, and the layered model/protocol design is sound.

---

## 7. Comparison with simpler / modern alternatives

- **Handlers → data table.** 24 near-identical classes replaceable by one dispatcher
  plus a declarative table. Deletes ~2,000 LOC, removes the "did someone forget to
  register it" class of bug entirely, and makes range validation a one-line
  cross-cutting concern instead of 24 omissions.
- **Parser/exporter → preserve-unknown or write-only.** The industry-standard answer
  to "round-trip a third-party XML format" is either (i) keep the original tree and
  patch nodes in place (`lxml` with the source tree retained, ~200 lines), or (ii)
  don't round-trip at all. Twinklr does neither: it models a subset and regenerates
  the whole document, which is the one option that silently loses data. Stage 2's
  proposed contract is option (ii), and §10 finds it cheap.
- **Settings strings → a typed value object.** A `SettingsString` type with a
  `set(key, value)` API that rejects `,` and `=` in values, plus per-effect parameter
  schemas, would close P5-F6 and P5-F7 together. xLights itself has no escaping
  mechanism in this format, so *rejection* (not encoding) is the correct design.
- **Coordination expansion → keep milliseconds.** The expansion functions already
  compute exact ms. Having them return `(start_ms, end_ms)` placements directly, with
  the categorical path used only for planner-authored placements, removes P5-F1
  entirely and is a smaller change than any alternative.
- **`ChoreographyGraph`** is already the modern replacement for `DisplayGraph`; the
  migration just needs finishing (P5-F10).

---

## 8. Documentation & context claims

| Claim | Source | Status |
|---|---|---|
| `.xsq` round-trip fidelity | product goal, discovery §4 | **CONFIRMED DEFECT**, and this phase enumerates the specific losses (P5-F5) beyond the generic `extra="ignore"` argument |
| Two conflicting version stamps | discovery §7 | **CONFIRMED**: `2024.10` at `moving_heads/xsq_export.py:67`, `2024.01` at `pipeline/display_stages.py:243`. Refinement: both are *fresh-sequence* defaults; when a template `.xsq` is supplied the template's own version is preserved verbatim (`parser.py:164-166` → `exporter.py:132`), so the stamp risk applies only to generate-fresh output |
| No version-compat logic | discovery §3 | **CONFIRMED** — `version` is a plain `str` field (`models/xsq.py:150`), read once for display (`get_version()`), never branched on |
| `EffectPlacement` "migration dataclass permanent on the hot path" | discovery §5 | **REFINED**: it is a plain `@dataclass` (`models/effect_placement.py:9-18`) constructed once per emitted effect on the shipped path — O(N), not multiplied. The dead half is worse than reported: `sequence/compat.py:7` (`effect_placement_to_effect`) has **zero callers**, superseded by inline duplicate logic at `xsq_export.py:88-96`, and `xsq.py::iter_effect_placements` is reachable only from `sequencer/analyzer.py`, which has no callers at all |
| TRIM overlap policy | discovery §5 | **CONFIRMED**, with a defect (P5-F12) |
| Trace sidecar is a strength | discovery §5 | **CONFIRMED** — `writer.py:42-57,266-292` + `renderer.py:229-246`; the best observability artifact in the phase |
| Recipe data gitignored / store empty | discovery §5 | **CONFIRMED** and worse than "inconvenient": it breaks three tests (§5) and is the reason recipe→handler parameter conformance cannot be checked at all |
| `DisplayGraph`→`ChoreographyGraph` unfinished | discovery §5 | **CONFIRMED**, ~95% done, cheap to finish (P5-F10) |
| Display pipeline unreachable from CLI | discovery §2 | **CONFIRMED** independently this phase |
| xLights format changes are additive; every additive field is one more `extra="ignore"` drop | modernization M6 / Stage 2 §2 | **CONFIRMED and sharpened**: the decay is not only in `extra="ignore"`. Whole sections absent from the parser's five modeled root children are dropped structurally, and `<Jukebox>` is regenerated *empty* regardless of input (`exporter.py:97`) |
| "LLM plans intent; renderer implements precision" | `memories/decisions/...` | Holds for the display renderer's *interface*; P5-F1 shows the renderer then degrades its own precision internally. The decision record is not wrong; the implementation partially defeats it |
| `docs/overview.md:24` six-channel claim | Stage 2 §finding 2 | See V1 verdict (§10) — the export layer's behavior is worse than "unwired" |

---

## 9. Architecture worth preserving

1. **`RenderPlan` as an inspectable intermediate** (`display/models/render_plan.py`) —
   composition decisions are a data structure before they are XML. Any rewrite should
   keep this.
2. **The XSQ trace sidecar** (`writer.py:266-292`, `renderer.py:229-246`) — every
   emitted effect carries `event_id / placement_id / section_id / lane / group_id /
   template_id / element / layer / start / end`. This is exactly the artifact needed to
   answer "why is this effect here", and it is the only quality-evidence mechanism in
   the phase. Preserve, and extend to the moving-heads path.
3. **XML hygiene** — `defusedxml` used consistently through one wrapper
   (`core/parsers/xml.py:12,64,89`), and `ElementTree` attribute escaping on write.
4. **Dedup registries** (`EffectDBRegistry`, `PaletteDBRegistry`) — correct, tested,
   and the right shape; the moving-heads path should adopt them.
5. **Palette model validation** (`display/models/palette.py:71-87`) — frozen,
   `extra="forbid"`, hex-format and slot-range validators. Closes the palette-string
   injection surface by construction.
6. **`XLightsMapping`** — externalizing choreo-id→element-name out of the graph model
   was the right call and is what makes the `ChoreographyGraph` migration finishable.
7. **The generate-fresh emitter** (`pipeline/display_stages.py:239-248`) — the repo's
   only from-nothing `.xsq` construction, and the seed of the Stage 2 contract (§10).

---

## 10. CANDIDATE FINDINGS

Severity: CRITICAL / HIGH / MEDIUM / LOW. Confidence: HIGH / MEDIUM / LOW.
Disposition: FIX / FIX-BEFORE-REACTIVATION / DELETE / DEFER / KEEP / STAGE-4.

---

### P5-F1 — Window expansion round-trips exact milliseconds through integer bar/beat and 5-bucket durations, destroying sub-beat timing

**Severity: HIGH · Confidence: HIGH · Disposition: FIX-BEFORE-REACTIVATION (of the display path)**

`_expand_sequenced/_expand_ripple/_expand_call_response` compute exact ms schedules
(`engine.py:495-523, 551-603, 620-663`), then convert every placement through
`_ms_to_planning_ref` (`engine.py:688-707`) and `_ms_to_duration`
(`engine.py:709-741`) before handing it to `TimingResolver`, which re-derives ms from
those categories (`timing_resolver.py:52-65, 105-123`).

- `_ms_to_planning_ref` floors to integer beats (`engine.py:701-702`:
  `int(total_beats // beats_per_bar)`, `int(total_beats % beats_per_bar)`). **Every
  sub-beat offset is lost.** A RIPPLE with `phase_offset=0.5` on 1-beat steps produces
  group starts at 0.0, 0.5, 1.0, 1.5 beats → floors to beats 0, 0, 1, 1 → groups
  collapse into pairs and the ripple becomes a two-step unison.
- `_ms_to_duration` buckets into HIT/BURST/PHRASE/EXTENDED/SECTION, and
  `_resolve_beat_count` with the default `duration_bias=0.5` re-expands them to
  exactly 1, 4, 12, or 24 beats (`timing_resolver.py:126-148`, `DURATION_BEATS` at
  `vocabulary/duration.py:34-40`). A computed 3-beat SEQUENCED slot becomes a 1-beat
  effect; a 5-beat slot becomes 4.
- Independently, expansion uses a constant `60000/tempo_bpm`
  (`engine.py:675, 697, 728`) while `TimingResolver` reads `BeatGrid.beat_boundaries`
  (`timing_resolver.py:64`). On any track with tempo drift these disagree, so the
  "BeatGrid is the sole timing authority" invariant (`engine.py:126-128`) does not
  hold for expanded placements.
- **`_ms_to_planning_ref` is not the inverse of `resolve_start_ms` even in the ideal
  case** (verifier addition, and the sharpest form of this finding). The forward
  function measures from ms=0 using a constant beat length; the reverse indexes into
  `beat_boundaries`, whose origin is `beat_boundaries[0]` — the first detected beat,
  which is generally **not** 0. The two therefore differ by a constant offset before any
  tempo drift is considered, and the result is then floored. **Every expanded placement
  can shift by a full beat**, uniformly across the song, on perfectly steady-tempo
  material. This is not a rounding artifact; the round trip is simply not a round trip.

**Assessment relationship:** new; not in discovery or Stage 2. Directly relevant to
Stage 2's "the renderer owns every numeric" framing — here the renderer discards its
own numerics. Interacts with modernization M6: any change to the 20 ms grid assumption
(`timing_resolver.py:164-190`) compounds this, so the two must be sequenced together.
**Fix:** have the expanders return absolute ms and give `_compose_placement_compiled`
an ms-native path. The categorical round trip is needed only for planner-authored
placements. ~1 day. **Constraint (P5-M6): the fix must preserve the intentional
`section_start_bar=0` convention** used when no section bar map is present
(`engine.py:250-252`) — expansion deliberately works in section-relative time
(`engine.py:416-418`) and `_compose_placement_compiled` re-applies the section offset.
An ms-native path that forgets this will double-apply or drop the offset and break every
placement, including the ones that work today.
**Stage 4:** cannot be observed without running the display pipeline (blocked by the
absent recipe corpus) — this is a static finding a verifier can confirm by reading, and
the verifier did re-derive it exactly.

---

### P5-F2 — `SEQUENCED` does not sequence: every group is continuously active

**Severity: HIGH · Confidence: HIGH · Disposition: FIX-BEFORE-REACTIVATION**

`_expand_sequenced` (`engine.py:479-531`) documents "non-overlapping round-robin slots,
one group at a time" (`:487-491`). The code gives group *i* a first slot starting at
`window_start + i*step_ms` (`:496-497`) with duration `step_ms * group_count`
(`:501`), then advances by the same amount (`:522`) — so each group's slots are
**contiguous**, and every group is lit continuously from its staggered start to the
window end. With 3 groups and a 2-beat step, all three groups are simultaneously active
from beat 4 onward. The only sequencing visible to a viewer is the first stagger.

After P5-F1's duration bucketing this degrades further (a 3-beat slot becomes a 1-beat
HIT), so actual output is a function of two interacting bugs.

**Assessment relationship:** new. Refutes any assumption that the display pipeline's
coordination modes are functionally complete.
**Fix:** slot *i* of group *g* = `[start + (i*N + g)*step, +step)`. ~1 hour, plus a
test. Note that the existing `test_sequenced.py` cannot currently run (§5), which is
how this survived.

---

### P5-F3 — `lane_plan.blend_mode` is structurally incapable of reaching RHYTHM/ACCENT output

**Severity: MEDIUM** (was HIGH in the first draft) **· Confidence: HIGH · Disposition: FIX**

_Mechanism corrected by the verifier; the first draft had the direction of the collision
backwards. The defect is real but its effect is **silent discard**, not contamination._

`_compose_section` records each lane's blend mode keyed by the **legacy simple**
allocator index (`engine.py:256-264` → `LayerAllocator.allocate`, giving BASE=0,
RHYTHM=2, ACCENT=4 from `_COMPAT_LAYER_MAP`, `layer_allocator.py:48-52`). Events are
placed using the **sub-layer** allocator (`engine.py:359` → `allocate_sub_layer`,
giving BASE 0–4 by visual depth, RHYTHM 6–10, ACCENT 12–16,
`layer_allocator.py:23-38`).

The two index spaces do not merely collide — **they barely intersect**. Lane blend modes
are only ever written to keys 0, 2, and 4, all of which lie inside the BASE lane's
block. RHYTHM emits on 6–11 and ACCENT on 12–17, where no lane blend mode is ever
registered. So:

- **`lane_plan.blend_mode` can never reach RHYTHM or ACCENT output at all.** Those
  layers take their blend mode from the recipe (`ce.layer_blend_mode`), and the planner's
  lane-level choice is silently dropped. This is the finding.
- Within the BASE block, ordering decides who wins. `_compose_section` registers key 0
  before composing that lane's coordination plans, so BASE/BACKGROUND takes the lane
  value and its recipe blend mode is discarded. Keys 2 and 4 are normally claimed *first*
  by BASE's own FOREGROUND/TEXTURE recipes during that same iteration, so when the RHYTHM
  and ACCENT iterations later try to register there, the `if blend_key not in
  self._layer_blend_modes` guard (`engine.py:361-362`) rejects them — **the recipe wins
  and the lane value is discarded**, which is the opposite of what the first draft
  claimed.
- Residual, conditional: if a BASE lane emits nothing at FOREGROUND/TEXTURE depth in an
  early section, keys 2/4 stay free and a later lane's value can occupy them, so a
  subsequent section's BASE/FOREGROUND events would inherit a RHYTHM blend mode. This
  cross-section contamination is possible but not the normal path. It is aggravated by
  P5-M2 (the map is never reset between `compose()` calls).

**Assessment relationship:** new; severity revised down on verification because the
dominant effect is a dropped planner input rather than wrong blend modes on emitted
layers.
**Fix (unchanged):** delete the `_compose_section` blend-tracking loop (the sub-layer
path at `:358-362` already covers every emitted layer) or key it by
`allocate_sub_layer`. Then decide deliberately whether `lane_plan.blend_mode` should
override recipe blend modes — today the question has never been answered, only avoided.
~1 hour.

---

### P5-F4 — `XSQWriter` corrupts a pre-existing sequence by two independent mechanisms

**Severity: HIGH (latent) · Confidence: HIGH · Disposition: FIX**

**Vector 1 — index invalidation.** `_sync_effectdb` assigns
`sequence.effect_db = EffectDB(entries=registry.get_entries())` (`writer.py:406-408`)
and `_sync_palettes` assigns `sequence.color_palettes = [...]` (`writer.py:423`). Both
**replace**, not merge. In xLights, `<Effect ref="N">` and `palette="N"` are positional
indices into exactly these two lists. Any effect already present keeps its old index and
now resolves to a Twinklr entry — silent, total corruption of the user's existing
effects, not merely loss.

**Vector 2 — layer-0 interleaving** (verifier addition). Independently of the registries,
`_write_group` calls `sequence.ensure_element(element_name)` (`writer.py:176`) and then
places every event through `sequence.add_effect(..., layer_index=compact_idx)`
(`writer.py:256`), where compaction starts at 0. `add_effect` **appends** to the existing
layer's effect list (`models/xsq.py:296-313`). If that element already carries the user's
own effects on layer 0, Twinklr's effects are appended into the same layer, interleaved
in list order, with **no overlap resolution whatsoever** — `_resolve_overlaps`
(`engine.py:975`) runs during composition over Twinklr's own events only and has no
knowledge of what is already in the sequence. The result is temporally overlapping
effects on one xLights layer, which is invalid in a way the writer cannot detect.

Both vectors are latent for the same reason: the shipped display stage constructs a
fresh sequence (`pipeline/display_stages.py:239-248`). But the stage accepts an
externally supplied `sequence` from context/extras, and `DisplayRenderer.render`'s
contract says "XSequence to write effects into" (`renderer.py:149-151`). The
moving-heads path — the one that *does* always receive a user template (V-contract,
Correction 1) — avoids vector 1 because `XsqAdapter` appends rather than replaces
(`xsq_adapter.py:191,322`), at the cost of no deduplication at all (P5-F15); it does
**not** avoid vector 2's shape, though its own layer assignment (0 regular / 1
transitions) makes collision less likely.

**Assessment relationship:** new; strengthens discovery's "template content loss"
defect with two distinct and more severe mechanisms (corruption vs. omission).
**Fix:** seed both registries from the parsed sequence's existing `EffectDB` and
`ColorPalettes` before writing, and place Twinklr effects on layers above the highest
occupied one. Sequence this as **one change with P5-F15**, since the seeding step is
literally the shared prerequisite. ~half a day. Or make it unreachable by adopting the
generate-fresh contract (V-contract), which is why this finding is load-bearing for
Stage 8.

---

### P5-F5 — Template-content loss: the specific, enumerated losses

**Severity: HIGH · Confidence: HIGH · Disposition: FIX (or eliminate by contract)**

Discovery established the mechanism (`extra="ignore"` × 9 + full regeneration). This
phase enumerates what concretely disappears on a parse→export round trip.

**These losses are unconditional on every shipped run** (corrected on verification).
`--xsq` is a required CLI argument (`cli/main.py:341`), so the template-parsing branch
at `xsq_export.py:53-56` is taken every time `twinklr run` executes. There is no
opt-in and no code path in production that avoids them. The list below is not a
description of what *could* happen to a user who supplies a template — it is what
happens to every user, every run, today.

1. **`<Jukebox>` is regenerated empty**, unconditionally, and is not parsed at all
   (`exporter.py:96-97`). Any user jukebox state is destroyed.
2. **Root children outside the five modeled sections are dropped structurally** — the
   parser reads only `head`, `nextid`, `EffectDB`, `ColorPalettes`, `ElementEffects`,
   plus `DisplayElements` for name recovery (`parser.py:118-136`). Anything else in the
   document (e.g. `DataLayers`) has no representation and is not re-emitted.
3. **`DisplayElements` per-element state is hardcoded on write**: `visible="1"`,
   `collapsed="0"` for every element (`exporter.py:166-183`), and the parser reads only
   `type` and `name` (`parser.py:372-374`). Collapse state, render-disabled flags, and
   row ordering are lost; timing tracks are also re-emitted *before* models regardless
   of their original order (`exporter.py:164-183`).
4. **Multi-layer timing tracks are flattened.** The parser concatenates the effects of
   *every* `EffectLayer` in a timing element into one flat marker list
   (`parser.py:263-271`), and the exporter writes exactly **one** `EffectLayer` back
   (`exporter.py:219-227`). xLights lyric timing tracks are conventionally three layers
   (phrases / words / phonemes); after a round trip they become one layer containing all
   three sets of markers, overlapping. This is the most user-visible loss in the list.
5. **`SequenceHead` is a 14-field allow-list** (`models/xsq.py:147-165`); head elements
   outside it are dropped.
6. **The 1 ms marker heuristic**: `end_time_ms == time_ms + 1` is normalized to `None`
   on read (`parser.py:301-303`) and regenerated as `start+1` on write
   (`exporter.py:238-241`) — lossless in practice but a genuine semantic guess.
7. Effect-level *attributes* are the one thing that does survive: unknown attributes are
   captured into `Effect.parameters` (`parser.py:468-493`) and re-emitted
   (`exporter.py:325-327`). Credit where due.

**Assessment relationship:** CONFIRMS and substantially refines discovery §4/§5 and
critic B3.

---

### P5-F6 — Settings strings have no escaping; the separator is injectable

**Severity: MEDIUM · Confidence: HIGH · Disposition: FIX**

`SettingsStringBuilder.add` does `f"{key}={value}"` (`settings_builder.py:43`) and
`build` does `",".join(...)` (`:188`). `DmxSettingsBuilder` does the same
(`dmx_settings_builder.py:90`). No quoting, no rejection, no validation. Any value
containing `,` fragments the string into fabricated key/value pairs; any value
containing `=` shifts the parse.

Reachable inputs: the Pictures filename, which comes from a generated-asset path
(`handlers/pictures.py:63,84` ← `engine.py:869,882`); `event.buffer_style`, an
unconstrained `str` (`models/render_event.py:73-76`); and every string parameter in
`event.parameters`, which is `dict[str, Any]` sourced from recipe JSON.

**Not** an XML-injection issue: `ElementTree` escapes attribute values and element text,
so the emitted document stays well-formed. The damage is confined to xLights'
own settings parser.
**Fix:** reject `,`/`=`/control characters in `add()` and raise, since xLights offers no
escape mechanism. ~2 hours.

---

### P5-F7 — Handler parameters are unvalidated and unclamped despite documented ranges

**Severity: MEDIUM · Confidence: HIGH · Disposition: FIX (with the handler-table refactor)**

Every handler reads `params.get(key, default)` and emits the value unchanged.
Docstrings declare ranges that nothing enforces — e.g. `bars_handler.py:46-47`
documents `bar_count: int (1-100)` and `:67` reads it with no bound; the same pattern
holds across all 24. String choice params (`"Palette"`/`"Rainbow"`, warp types, wave
types) are documented as enums and checked against nothing. An out-of-range or
misspelled value flows into the settings string and xLights' behavior on receiving it is
undefined from Twinklr's side.

Combined with P5-F6, validation and escaping are the same fix at the same choke point.

---

### P5-F8 + P5-M1 — Recipe outputs are computed and discarded; unrecognized effect types render silently as flat `On`

**Severity: MED-HIGH** (raised on verification by the merge of P5-M1) **· Confidence: HIGH · Disposition: FIX**

`RecipeRenderer` produces `RenderedLayer` with `resolved_color`, `density`, and
`timing_offset_beats` (`recipe_renderer.py:24-38`). `RecipeCompiler._layer_to_compiled_effect`
(`recipe_compiler.py:123-170`) reads `effect_type`, `resolved_params`, `mix`,
`blend_mode`, and `layer_depth` — and **never reads `resolved_color` or
`timing_offset_beats`**. Grep confirms: outside the model definition, `resolved_color`
appears only in tests (`tests/integration/test_recipe_end_to_end.py:235-237`,
`test_fe_unified_pipeline_e2e.py:649-650`) and `timing_offset_beats` only in a
`recipe_builder` prompt docstring (`recipe_builder/generation.py:139`). The entire
per-layer `ColorSource` resolution (`recipe_renderer.py:130-140`) is dead computation;
color comes from `context.palette` instead.

Separately, `recipe_compiler.py:151` injects `"E_SLIDER_Mix": int(layer.mix * 100)` into
`RenderEvent.parameters`, but no handler reads any key containing "Mix" (grep over
`display/effects/` returns zero matches) — layer mix never reaches the output. And
because handlers read only their own hardcoded parameter names, any recipe param whose
key does not match is silently dropped with no diagnostic. `effect_map.py:49` asserts
"Keys match the parameter names handlers read via `params.get()`" for the *preset*
tables, but recipe-authored params bypass those tables entirely
(`recipe_compiler.py:144-146` sets `base_params = {}` when the recipe supplies a real
effect type). Since `data/templates` is gitignored, **conformance cannot be checked from
the repository at all**.

**P5-M1 (verifier-added, merged here): an unrecognized effect type renders silently as a
flat `On`.** `HandlerRegistry.dispatch` (`display/effects/registry.py:93-108`) looks up
`event.effect_type`; on a miss it falls back to the default handler — set to the `On`
handler at `handlers/__init__.py:94` — emitting only a `logger.warning`. That warning
goes to the log and **nowhere else**: it is not added to `EffectSettings.warnings`, so it
never reaches `WriteResult.warnings` (`writer.py:226`), never reaches
`RenderResult.warnings`, and never reaches the trace sidecar. `RenderEvent.effect_type`
is a plain `str` (`models/render_event.py`) populated from recipe JSON or, on the
placeholder path, from `resolve_effect_type` — neither validated against
`registry.registered_types`.

This is the concrete answer to "what does wrong output actually look like here": a
recipe naming an effect Twinklr does not implement (a typo, an xLights effect with no
handler, an LLM-invented name) produces a **valid `.xsq` full of flat `On` blocks** —
correctly timed, correctly colored, visually wrong, and with no artifact anywhere in the
output that says so. Combined with the silently-dropped parameters above, the display
path's failure mode is uniformly "plausible output, no signal".

**Fix:** validate `effect_type` against the registry at compile time and fail loudly, or
at minimum propagate the fallback into `EffectSettings.warnings` and the trace sidecar.
~2 hours, and it is the highest-value observability fix in the phase.

**Assessment relationship:** new; structurally identical to Stage 2's central finding
(irreplaceable output with no sink), reproduced inside the renderer.

---

### P5-F9 — `effect_resolver.py` is dead: the declared replacement was written, tested, and never wired

**Severity: MEDIUM · Confidence: HIGH (INFERRED from exhaustive grep) · Disposition: DELETE or WIRE**

`display/composition/effect_resolver.py` (504 lines, third-largest file in the phase)
states in its own module docstring: *"This replaces the old keyword-matching
`resolve_effect_type()` in `effect_map.py`"* (`:11-13`). Its only export,
`resolve_effect` (`:370`), has exactly one importer repo-wide:
`tests/unit/sequencer/display/composition/test_effect_resolver.py:9`. Meanwhile
`effect_map.resolve_effect_type` — the thing it "replaces" — is still the live call
(`recipe_compiler.py:141`), and `effect_map.py` is 1,079 lines.

So the phase carries 1,583 lines implementing two generations of the same
responsibility, with the newer, motif-primary, three-tier design fully built and
inert. This is a **third** straddling migration in this phase alongside
DisplayGraph→ChoreographyGraph and `compat.py` (P5-F16).

---

### P5-F10 — DisplayGraph→ChoreographyGraph is complete in production; only dead leftovers remain

**Severity: MEDIUM · Confidence: HIGH · Disposition: FIX (low cost, high clarity return)**

`ChoreographyGraph` (`templates/group/models/choreography.py`) is what all 18 non-test
production consumers use, including `cli/main.py:27,62-63,127`. `DisplayGraph`
(`models/display.py`, 419 lines) has **zero production instantiations** outside its own
module and the converter. Its remaining references are **three** re-export sites
(corrected line refs): `templates/group/models/__init__.py:8` (docstring), `:28`
(import), `:76-77` (the comment "legacy — being replaced by ChoreographyGraph" and the
`__all__` entry), plus `agents/sequencer/group_planner/__init__.py:67,100` — and one
stale comment in `engine.py:442` that says "from the DisplayGraph" while operating on
`self._choreo_graph`.

`models/compat.py` is a real one-way converter, not a shim: `choreo_graph_from_display_graph`
(`:21-56`) drops `display_name`, `element_type`, and `parent_group_id`, and sets
`tags=[]` with a docstring admitting tags "must be added manually" (`:49`). No reverse
converter exists. ~110 lines of sort/summary logic are copy-pasted between the two
models (`display.py:299-411` ≈ `choreography.py:200-308`).

**Both converters have zero production callers.** `choreo_graph_from_display_graph` and
`xlights_mapping_from_display_graph` appear only in
`tests/unit/sequencer/templates/group/test_compat.py`. The first draft described
`compat.py` as the legacy model's "only live non-test consumer" — it is not live at all.
The migration is therefore not 95% complete with a bridge still in use; it is **complete
in production, with an unused bridge and an unused model left behind.**

**Cost to finish:** delete `display.py` + `compat.py`, remove three re-export sites,
retire 3 test files, fix one comment. Under half a day, and cheaper than the first draft
implied since nothing must be migrated off the converter first. `DisplayGraph`'s
hierarchy support (`parent_group_id` with cycle validation) is the only capability not
carried forward — confirm it is unwanted before deleting.

---

### P5-F11 — The gitignored recipe corpus breaks 52 tests in a fresh checkout

**Severity: MEDIUM · Confidence: CONFIRMED (Stage 4 run) · Disposition: FIX**

See §5.1. `tests/unit/sequencer/display/composition/test_engine.py`,
`.../test_sequenced.py:63-72`, `tests/unit/sequencer/display/test_renderer_overlay.py`
call `TemplateStore.from_directory(repo/data/templates)`; `store.py:96-97` reads
`index.json` with no existence guard; `data/` is gitignored (`.gitignore:49`) and the
directory is absent. Three further files outside this phase do the same.

Consequence beyond the failing tests: the coordination-mode expansion logic (P5-F1,
P5-F2) has no runnable coverage, which is the proximate reason those defects persisted.

**Stage 4 outcome — CONFIRMED.** The prediction ("~6 test files error at
collection/fixture time") was borne out and then some: the Stage 4 run reports **52
failures traced to the missing `data/templates`**. This is environmental-by-design, not
a regression, and should be recorded as such against
`memories/learnings/known-test-failures.md` — whose four stale entries this supersedes.
The scale also reframes the finding: this is not a handful of skippable tests, it is the
largest single block of red in the suite, and it means the display subsystem's true test
coverage is unknown rather than merely partial.

---

### P5-F12 — TRIM overlap policy deletes coverage it did not need to delete

**Severity: MEDIUM · Confidence: HIGH · Disposition: FIX**

`_resolve_overlaps` (`engine.py:975-1020`) trims each event against `events[i+1]` from
the **original** sorted list. _Mechanism corrected on verification: the harm does not
come from trimming against neighbours that are later dropped as eclipsed, but from
trimming against **short neighbours that survive**._

Given A=[0,100), B=[10,20), C=[50,200) sorted by start: A is trimmed to end at B's start
(10), B survives untouched as [10,20), and C is kept as [50,200). The interval 20–50 ms
is now dark — A was trimmed to make room for a 10 ms neighbour and never restored for
the gap that neighbour left behind. A long base event nested around a short accent loses
its entire tail to a 10 ms interruption. The eclipse branch (`:1014-1016`) is a separate
and comparatively benign case.

Also worth flagging: the "later event wins" policy is applied without regard to lane or
intensity, so a WHISPER accent can truncate a PEAK base event.

**Fix:** resolve against the *running* resolved list and re-extend the trimmed event
after the neighbour ends, or split it. ~2 hours.

---

### P5-F13 — Parser robustness: unbounded input, and malformed content degrades silently

**Severity: LOW–MEDIUM · Confidence: HIGH · Disposition: FIX (cheap hardening)**

Trust boundary: `.xsq` and `xlights_rgbeffects.xml` are user-supplied. XXE and
entity-expansion are correctly blocked — `defusedxml` via one wrapper
(`core/parsers/xml.py:12,64,89`), used by both the sequence parser (`parser.py:45,68`)
and the layout parser (`layout/parser.py:11,44,65`). Residual issues:

- **No size, element-count, or depth limit.** The whole document is loaded into a DOM
  and then into Pydantic models; a real xLights show sequence can be tens to hundreds
  of MB, and the model layer multiplies that. Local-user input, so DoS is not the
  threat — memory exhaustion on a legitimate large file is.
- **Malformed content degrades silently rather than failing.** Effects missing
  `name`/`startTime`/`endTime`, or with non-integer times, are skipped with a
  `logger.warning` (`parser.py:431-440`); timing markers likewise (`:308-310`). The
  caller receives a valid-looking `XSequence` that is quietly missing content, with no
  count in the return value.
- The layout parser drops all top-level sections outside a 4-entry allow-list
  (`layout/parser.py:31-40, 98-100`), debug-logged only.

**Fix:** a size guard plus a `ParseReport` (skipped counts, dropped sections) returned
alongside the model. ~half a day.

---

### P5-F14 — simpleeval sandbox is sound; the guarding test is not, and failures are silent

**Severity: LOW · Confidence: HIGH · Disposition: FIX (the test and the swallow)**

`RecipeRenderer._evaluate_param` (`recipe_renderer.py:106-128`) calls
`simple_eval(expr, names={energy,density}, functions={min,max,abs,round})` on
simpleeval 1.0.3 (`uv.lock:2042-2044`; declared `>=1.0` at
`packages/twinklr/core/pyproject.toml:30`). This is a correct configuration: name and
function allow-lists are closed, and simpleeval's own defaults block underscore-prefixed
attribute access and guard `**`/string-multiplication.
**Assessment: this is not a meaningful code-execution risk as configured.**

**The first draft's supporting argument was wrong and is struck.** It claimed the
expression source is human-authored offline content, "not LLM-emitted at runtime". In
fact `ParamValue.expr` **is LLM-authored**: `recipe_builder`'s generation step
model-validates raw LLM JSON into `EffectRecipe`, so the real chain is
**LLM → JSON → `ParamValue.expr` → `simple_eval`**. That is a genuine trust boundary and
should be named as one in any security summary, rather than assumed away. The
conclusion (LOW) survives **on the sandbox configuration alone** — which is the right
reason, and the only reason. Two properties keep it there: the boundary is crossed
offline during curation rather than during a pipeline run, and the allow-lists are
closed. If either changes — runtime recipe generation, or a widened `functions` dict —
this finding must be re-rated.

Two real problems remain: (a) the guarding test exercises the *library*, not the code,
and asserts on source text (`test_recipe_renderer_security.py:13-20, 28-54`) — it would
pass unchanged if `_evaluate_param` were rewritten to use `eval` under a different name;
(b) any expression error is swallowed into `return pv.min_val or 0.0`
(`recipe_renderer.py:121-122`) with no warning reaching `RecipeRenderResult.warnings`,
so a broken recipe silently renders as a minimum-value effect.

These two compound in a way worth stating plainly: **the test asserts the opposite of
production behavior.** It asserts that a dangerous expression *raises*
(`test_recipe_renderer_security.py:43-54`) — which is true of `simple_eval` in
isolation. In production that raise is caught and converted into a silent default value.
Nothing anywhere observes it. So the one test named "security" documents a behavior the
system does not have. Keep simpleeval; pin it explicitly; rewrite the test against
`_evaluate_param`; surface the swallow as a warning.

---

### P5-F15 — Two parallel writers: ~250 lines of accidental duplication and an asymmetric EffectDB policy

**Severity: MEDIUM · Confidence: HIGH · Disposition: FIX (partial convergence)**

Quantified in §4. The consequential half is not the line count but the policy split:
`XSQWriter` deduplicates EffectDB entries through `EffectDBRegistry`
(`writer.py:121,238`), while `XsqAdapter` calls `xsq.append_effectdb` once per segment
with no dedup (`xsq_adapter.py:191,322`). On the shipped moving-heads path, N segments
produce N EffectDB entries even when identical — a straightforward file-size and
xLights-load-time regression.

**The harvest is not drop-in** (verifier correction; the first draft's "~2 hours"
understated it). `EffectDBRegistry` as written starts empty and hands out indices from
its own zero base (`export/effectdb_registry.py:36-44`). Dropping it into the
moving-heads path — which *always* parses a user template (V-contract, Correction 1) —
would re-index against a non-empty existing `EffectDB` and produce exactly the
corruption described in P5-F4 vector 1. **The registry must first be seeded from the
parsed template's `EffectDB`, which is precisely the P5-F4 fix.** Sequence them as one
change: seed, then share. ~half a day for both together, and do not land the dedup
first.

---

### P5-F16 — Dead conversion helper superseded by an inline duplicate

**Severity: LOW · Confidence: HIGH · Disposition: DELETE**

`formats/xlights/sequence/compat.py:7` (`effect_placement_to_effect`) has zero callers
repo-wide; `xsq_export.py:88-96` reimplements the same conversion inline. Delete
`compat.py` and use the helper, or delete the helper. Related dead code discovered in
passing: `sequencer/analyzer.py::SequenceAnalyzer` has no callers anywhere including
tests, which makes `xsq.py::iter_effect_placements` (`:334-356`) and
`effect_type_histogram` (`:358-367`) unreachable in production.

---

### P5-F17 — Version stamps: conflicting defaults, no compatibility logic, but template versions are preserved

**Severity: LOW-MEDIUM** (lowered — see M6b below) **· Confidence: HIGH · Disposition: FIX (cheap, do it regardless)**

`version="2024.10"` (`moving_heads/xsq_export.py:67`) vs `version="2024.01"`
(`pipeline/display_stages.py:243`). `SequenceHead.version` is a plain `str`
(`models/xsq.py:150`) with no parsing, comparison, or branching anywhere. **Refinement
over discovery:** both are *fresh-sequence* defaults — when a template `.xsq` is
supplied, its own version string is parsed (`parser.py:164-166`) and re-emitted verbatim
(`exporter.py:132`). Since `--xsq` is required (`cli/main.py:341`), **the shipped path
today always re-emits the user's own stamp** and never emits either constant.

**Lowered on the M6b evidence.** Stage 6 follow-up research finds xLights' documented
version cutoff is pre-2020 only and warns rather than rejects, so neither constant would
block a load today. What keeps this open: the constants become live the moment the
generate-fresh contract lands (making the stamp the product's whole compatibility
story); the cutoff can ratchet; and M6b flags unknown/synthetic stamp handling as
unverified. The disagreement extends beyond the version string to `sequenceTiming` and
quantization behavior — see P5-M3, which is the more consequential half of this finding.

---

### P5-M2 — `_layer_blend_modes` is never reset between `compose()` calls

**Severity: MEDIUM (latent) · Confidence: HIGH · Disposition: FIX**

_Verifier-added._ `CompositionEngine._layer_blend_modes` is initialized once in
`__init__` (`engine.py:173`) and never cleared in `compose()` (`:179-224`), which
accumulates into it via the `if key not in` guards (`:263-264, 361-362`). A second
`compose()` call on the same engine instance therefore inherits every blend-mode
decision from the first run, and — because the writes are first-wins — the *stale*
values take precedence over the new plan's.

Latent today: `DisplayRenderer.render` constructs a fresh `CompositionEngine` per call
(`renderer.py:178-187`), so no shipped path reuses one. It is a trap for exactly the two
things this subsystem needs next — batch rendering and A/B comparison runs — where
reusing the engine is the obvious optimization and the corruption would be silent and
order-dependent.
**Fix:** reset the dict at the top of `compose()`, or make it a local threaded through
the call chain. ~15 minutes. Interacts with P5-F3: fixing F3's key collision without
fixing this leaves the cross-section contamination path open across runs.

---

### P5-M3 — The two fresh emitters disagree on timing grid as well as version, and the shipped path quantizes not at all

**Severity: LOW-MEDIUM · Confidence: HIGH · Disposition: FIX + STAGE-4**

_Verifier-added; extends P5-F17 from version stamps to the whole head contract._ Beyond
the `2024.10` / `2024.01` split, the two from-nothing emitters also disagree on
`sequenceTiming`: `50 ms` at `moving_heads/xsq_export.py:72` versus `20 ms` at
`pipeline/display_stages.py:246`. That value declares the sequence's frame grid to
xLights.

The deeper asymmetry is what each path then *does* with it. The display path snaps every
time value to a 20 ms grid (`timing_resolver.py:164-190`), consistent with its declared
timing. **The moving-heads path applies no quantization at all** — segment boundaries
flow to `Effect.start_time_ms`/`end_time_ms` as computed, while the head declares a 50 ms
grid. Effects therefore land off-grid relative to the file's own declaration on the only
shipped path. Whether xLights snaps, renders off-grid, or misbehaves is unknown.

**Stage 4:** add to the golden-diff protocol (V4) — after saving from xLights, check
whether effect start/end times were rewritten. That diff answers it definitively.

---

### P5-M4 — Palette index 0 is emitted as an absent attribute

**Severity: LOW · Confidence: HIGH · Disposition: STAGE-4 (golden-diff checklist)**

_Verifier-added._ `XSQExporter._build_effect` writes the palette attribute only when it
is truthy and not `"0"` (`exporter.py:309-311`). `PaletteDBRegistry` does **not** reserve
index 0 (`display/palette/registry.py:26,43-44` — unlike `EffectDBRegistry`, which does),
so the first registered palette is index 0 and is assigned as `palette="0"`
(`writer.py:245,252`). Every effect using the sequence's most common palette therefore
emits **no `palette` attribute at all**.

This may be correct — xLights may treat an absent attribute as index 0 — or it may cause
those effects to fall back to a default palette. The asymmetry between the two registries
suggests the reservation convention was applied to one and forgotten on the other.
**Stage 4:** add to the golden-diff checklist; a single saved file answers it.

---

### P5-M5 — `SequenceAnalyzer` dead-chain (INFO)

**Severity: INFO · Confidence: HIGH · Disposition: DELETE**

_Verifier-added, extending P5-F16._ The dead chain is longer than first reported:
`sequencer/analyzer.py::SequenceAnalyzer` has no callers anywhere including tests, which
makes `xsq.py::iter_effect_placements` (`:334-356`) and `effect_type_histogram`
(`:358-367`) unreachable in production — and those are the only consumers of
`EffectPlacement` outside the export loop. Deleting `SequenceAnalyzer`,
`sequence/compat.py`, and the two `xsq.py` methods together removes the entire
`EffectPlacement` read-back surface, leaving it a pure export-loop dataclass.

---

### P5-M6 — Constraint on the P5-F1 fix (flag, not a defect)

**Severity: N/A (implementation constraint) · Confidence: HIGH · Disposition: CARRY TO STAGE 8**

_Verifier-added._ Recorded inline against P5-F1 and repeated here so the roadmap does not
lose it: the `section_start_bar=0` fallback (`engine.py:250-252`) and the
section-relative expansion convention (`engine.py:416-418`) are **intentional**. An
ms-native rewrite of window expansion that does not preserve them will double-apply or
drop the section offset in `_compose_placement_compiled` and break placements that
currently resolve correctly. Any P5-F1 fix must ship with a test that pins section-offset
behavior for both the mapped and unmapped cases.

---

### P5-F18 — Positive findings (KEEP)

**Severity: N/A · Confidence: HIGH · Disposition: KEEP**

Enumerated in §9. Summary: `RenderPlan` intermediate; XSQ trace sidecar; consistent
`defusedxml`; dedup registries; validated frozen palette model; `XLightsMapping`
externalization; the generate-fresh emitter; zero TODO markers across 18.7k LOC;
correct, complete handler registration.

---

## 11. Stage 2 claim verdicts

### V1 (export half) — what happens to color/gobo/shutter in the emitted DMX effect

**VERDICT: REFINES Stage 2 — and the reality is materially worse than "unwired".**

They are **written as explicit zeros**, not omitted and not left untouched.

`DmxSettingsBuilder.build_settings_string` emits, for every channel from 1 to
`max_channel`, both an inversion flag (`dmx_settings_builder.py:69-70`) and a value
(`:77-83`):

```python
for ch in range(1, max_channel + 1):
    if ch in channel_curves:
        parts.append(f"E_SLIDER_DMX{ch}=0")          # curve present
    else:
        parts.append(f"E_SLIDER_DMX{ch}={int(channel_values.get(ch, 0))}")
```

`max_channel` is floored at 16 and rounded up to a multiple of 16 (`:247-257`), so a
16-channel fixture always receives all 16 sliders. `channel_values` is populated only
from `segment.channels` (`:55-56, 92-147`). `ChannelName.SHUTTER`, `.COLOR`, and `.GOBO`
appear in exactly two files repo-wide — `dmx_settings_builder.py:162-164` and
`moving_heads/channels/state.py:230-232` — and **both are lookup tables, not
producers**. No code path ever puts a SHUTTER, COLOR, or GOBO entry into
`segment.channels`.

Therefore every emitted DMX effect contains `E_SLIDER_DMX{shutter}=0`,
`E_SLIDER_DMX{color}=0`, `E_SLIDER_DMX{gobo}=0`.

**Why this is worse than omission — and the repo says so itself.** The first draft of
this review called the shutter risk "unverifiable from the repo" and deferred it to a
Stage 4 hardware check. **That caveat was wrong** (verifier correction; phase 4 derived
the same result independently and this review defers to it). Twinklr's own configuration
layer declares the convention explicitly, three times over:

- `config/fixtures/dmx.py:16-17` — `ShutterMap.closed: int = 0`,
  `ShutterMap.open: int = 255`.
- `config/fixtures/dmx.py:94-95` — `shutter_default: int = 255`, with the field
  description *"Default shutter value (usually open)"*.
- `sequencer/moving_heads/libraries/shutter.py:53-54` — `DMX_CLOSED = 0`,
  `DMX_OPEN = 255`.

**All three have zero production readers** (consistent with Stage 2's dead-config-class
finding and phase 7's P7-M2). So the exporter unconditionally forces to `0` the exact
channel the repository's own configuration defaults to `255` and documents as "usually
open" — and the field that would have fixed it exists, is validated, and is never read.
This is no longer a hypothesis about unknown hardware; it is a contradiction internal to
the codebase, and it is the single highest-impact defect this phase found.

Stage 4's remaining job is therefore narrow: confirm that the author's *physical*
fixtures follow the convention the repo already assumes. It is no longer establishing
intent. Color=0 and gobo=0 remain usually benign (open white / no gobo).

**Coordination with phase 4:** phase 4 owns the template side (0 of 37 templates
reference these channels) and derived the shutter conclusion independently; where the
first draft of this phase and phase 4 disagreed, the conflict is resolved in phase 4's
favor and this section is aligned to it. The joint statement is: *no template writes
them, and the exporter does not leave them alone — it forces them to 0 on every effect,
overriding a documented default of 255.*

Adding color is therefore not purely additive plumbing on the export side:
`_get_dmx_channel_number` and `_get_inversion_dict` already handle all six channels
correctly (`dmx_settings_builder.py:149-231`), so the export layer needs **zero
structural changes** — but the current zero-fill is an active behavior, not an absence,
and any "add color" work must decide what non-choreographed channels should emit (hold /
omit / configured default). `JobConfig.is_channel_enabled()`, `ChannelDefaults`, and
`shutter_default` are exactly the mechanism designed for this and never connected;
reading them at `dmx_settings_builder.py:77-83` instead of defaulting to `0` is a
small, well-scoped fix and should be sequenced ahead of any template work.

---

### V4 (static half) — what a Twinklr `.xsq` contains vs what xLights requires

**VERDICT: REFINES Stage 2. The comparison Stage 2 asks for cannot be made from the
repository, and that absence is itself the finding.**

**What a Twinklr-emitted `.xsq` contains** (from `exporter.py:68-118`, in document
order):

| Element | Content | Notes |
|---|---|---|
| `<xsequence>` attrs | `BaseChannel`, `ChanCtrlBasic`, `ChanCtrlColor`, `FixedPointTiming`, `ModelBlending` | 5 attributes, defaults 0/0/0/1/true |
| `<head>` | 14 fixed children incl. `version`, `mediaFile`, `sequenceDuration` (seconds, 3 dp), `sequenceTiming` | `2024.10` (MH) / `2024.01` (display) when fresh |
| `<nextid>` | int, default 1 | never incremented by Twinklr |
| `<Jukebox>` | **always empty** | `:97` |
| `<ColorPalettes>` | omitted entirely when empty; MH path emits none | display path emits deduped `C_*` strings |
| `<EffectDB>` | always present; index 0 reserved empty on the display path only | MH path: one entry per placement, no dedup |
| `<DisplayElements>` | one `Element` per timing track then per model, all `visible="1" collapsed="0"` | |
| `<ElementEffects>` | timing tracks (single `EffectLayer` each) then models with their layers | |

**What xLights requires:** unknown from this repository. There is **no sample `.xsq`
anywhere in the tree**, no golden file, no fixture, no round-trip test. The only
in-repo model of "what xLights writes" is `XSQParser`'s allow-list — and comparing the
exporter against the parser is circular, because the exporter was written as that
parser's inverse. The parser's own hard requirements (`<head>` present, `version`,
`mediaFile`/`MediaFile`, `sequenceDuration` non-empty: `parser.py:119-121, 164-180`) are
a statement about Twinklr, not about xLights.

**Concrete risk list for the Stage 4 "2024.10 stamp on 2026.15" test**, ordered by
likelihood of breaking the open:

1. **Missing root sections that 2026-era xLights expects.** Twinklr emits 7 root
   children. Two years and ~40 releases of additive changes (modernization M6: embedded
   images 2026.03, relative paths 2026.04, face definitions 2026.14) mean the current
   writer emits sections xLights may treat as mandatory on load. Highest-probability
   failure mode, and now the clear front-runner given item 2's downgrade.
2. ~~**The version string itself.**~~ **Largely resolved by M6b — downgraded.** Stage 6
   follow-up research establishes that xLights' documented version cutoff is **pre-2020
   only, and produces a warning rather than a rejection** (introduced 2026.04). A
   "2024.10" stamp is therefore acceptable to current xLights, and this is no longer a
   likely blocker. Two residuals keep it on the list at low priority: the boundary can
   ratchet in future releases, and M6b flags the treatment of *synthetic or unknown*
   stamp values as still unverified — which matters because Twinklr emits a hardcoded
   constant rather than a real release string. Update the stamps anyway; it is free.
3. **`<Jukebox/>` empty vs. expected structure** — an empty element where a populated
   one is expected is a classic loader crash.
4. **`nextid` never advanced past 1** while effects exist; if xLights uses it to
   allocate ids on edit, collisions on first save are plausible.
5. **Settings-string key validity.** Every `E_*` key is hardcoded against a 2024-era
   understanding of each effect's widget names. Renamed or removed keys degrade
   silently (xLights typically ignores unknown keys), which would look like "opens fine
   but the effect is wrong" — the hardest failure to detect. Test by *inspecting an
   effect's parameters in the xLights UI*, not merely by opening the file.
6. **`ref`/`palette` index integrity** — verify the display path's reserved index 0
   convention against what xLights actually does with `ref="0"`.
7. **Timing-track layer count** (P5-F5.4) — if any test uses a template with a lyric
   track, expect visible corruption.

**Recommended Stage 4 protocol:** (a) generate a `.xsq`; (b) open in current xLights and
record whether it loads, warns, or migrates; (c) **save from xLights and diff the
saved file against the generated one** — that diff is the only ground truth in existence
for what xLights actually requires, and it is worth committing as the repository's first
golden fixture regardless of outcome.

---

### V-contract — feasibility of a generate-fresh / minimal-xsq / import-mediated contract

**VERDICT: CONFIRMS Stage 2. The code cost is low, but two factual claims in the first
draft of this review were wrong and the corrections change what the decision *means*.**

**Correction 1 — `--xsq` is REQUIRED, so the template branch is the only branch that has
ever run.** The first draft called the template parse "a single *optional* call site".
It is not optional: `cli/main.py:341` declares
`run.add_argument("--xsq", required=True, help="Path to input .xsq template")`. Every
shipped run therefore takes the `if template_xsq and Path(template_xsq).exists()` branch
at `xsq_export.py:53-56`. The generate-fresh `else` branch (`:62-74`) **has never
executed in production** — and it could not survive if it did: it sets `media_file=""`
(`:68`), while `XSQParser` treats a missing or empty `mediaFile` as a *fatal* parse error
(`parser.py:168-170`). Twinklr's only from-nothing moving-heads emitter produces a file
its own parser rejects.

Two consequences. First, **P5-F5's seven losses are unconditional today**, not
conditional on a user opting into a template — every run parses the user's `.xsq`,
regenerates it, and drops that content. Second, the contract is not "delete an unused
branch"; it is **removing a required, always-exercised input from the CLI**, which is a
user-facing product decision (Stage 8) on top of a small code change.

**Correction 2 — the parser survives the contract; it is detached from export, not
deleted.** The first draft said `profiling/` uses only the *layout* parser. Wrong:
`profiling/profiler.py:13` imports `XSQParser` and `:48` instantiates it
(`self._xsq_parser = xsq_parser or XSQParser()`). `XSQParser` therefore keeps a real
consumer under the contract. The correct statement is that the contract removes the
parser **from the export/trust path**, leaving it as an analysis-only component — still
a large risk reduction (it stops mediating the user's own show file), but not the
"write-only surface" simplification Stage 2's framing implies.

**Corrected picture of parser entanglement in export — still low, and now complete.**
Three export-path callers exist, not one:

| Caller | Site | Under the contract |
|---|---|---|
| Moving-heads export | `xsq_export.py:53-56` (required input) | branch deleted |
| Display render stage | `pipeline/display_stages.py:239-248` — **already generate-fresh** | unchanged |
| Eval re-render | `reporting/evaluation/rerender.py:131` passes `template_xsq=xsq_path` | needs the same treatment; easy to miss |

The display path already does the right thing. **The code cost of the contract remains
one branch per caller — but there are three callers, and the third
(`rerender.py:131`) is inside the subsystem Stage 2 wants promoted first, so the two
work items are coupled.**

**What would a minimal valid `.xsq` emission require?** Structurally, nothing new — the
existing `_build_tree` already emits a self-contained document. Three real gaps:

1. **A correct, current version stamp** (P5-F17), which requires the V4 empirical test
   first. This is the only hard dependency.
2. **`mediaFile` handling.** The fresh MH path sets `media_file=""` (`xsq_export.py:68`)
   while the parser treats a missing/empty `mediaFile` as a *fatal* parse error
   (`parser.py:168-170`). Twinklr therefore currently emits files its own parser would
   reject — a two-line fix, and a sharp illustration of the missing round-trip test.
   Under the contract this stops being a latent curiosity and becomes the **first thing
   that would break**, because the never-executed branch becomes the only branch.
3. **A decision about `DisplayElements` content.** Under generate-fresh, Twinklr emits
   only its own models; xLights' effect-import must then match them by name against the
   user's layout.
4. **Reconciling the two fresh emitters**, which currently disagree on both the version
   stamp and the timing grid (P5-M3). Whichever survives becomes the product's entire
   output contract, so the disagreement must be resolved deliberately rather than by
   whichever caller happens to win.

**Is `DisplayElements` preservation still needed?** **No.**
`_ensure_all_display_elements` (`parser.py:348-391`) exists solely to carry the user's
untouched models through a parse→export cycle so that regeneration does not delete them.
Under generate-fresh there is no user document to preserve, and the method becomes dead
code to delete along with it. This is a clean simplification, and it removes the
"partial mitigation" caveat recorded against the xLights row in `manifest.md`.

**Additional support for the contract from this phase:** P5-F4 (both corruption
vectors) and all seven losses in P5-F5 — which, per Correction 1, are occurring on
**every run today** — become *unreachable by construction* under generate-fresh. The
contract does not merely reduce risk here; it deletes an entire defect class along with
the code that produces it, and it is the only remedy that makes the P5-F4/P5-F15 seeding
work unnecessary rather than merely deferred. Estimated cost: **1–2 days** of code plus
the Stage 4 empirical dependency — well under any preserving-parser alternative. The
*decision* cost is higher than the code cost, because it removes a required CLI input.

**Residual risk — substantially de-risked since this phase was drafted.** The contract
depends on xLights' effect import accepting a minimal externally-generated `.xsq`. The
Stage 6 follow-up (modernization §M6b) has since established from primary sources that
**effect import does accept xLights donor sequences carrying effects and timing tracks**,
with two conditions: the target models must already exist in the user's view, and
name-mapping is the friction — mitigated by shipping an `.xmap` hint file or using
xLights' auto/AI mapping. One residual remains unverified and belongs in the Stage 4
test: whether a bare `.xsq` imports without an accompanying `xlights_rgbeffects.xml`
(the docs state that requirement only for the zip path).

M6b also surfaces two options this phase did not consider, and Stage 8 should weigh them
against the contract rather than assuming export is the only route:

- **`.xtiming`-only** — timing tracks import standalone, with no model mapping at all.
  Given that `timeline.py` is already on the CLI path, correct, and the best-tested file
  in `formats/xlights/` (§5), this is a genuinely small deliverable that would put
  Twinklr's deterministic audio analysis in front of a user without touching any of the
  defects in this review.
- **Direct `addEffect` injection** via xLights' HTTP automation API against `getModels`
  output — inverts the integration from "export a file and hope" to "drive the host
  app", eliminating name-mapping at the root. It would make most of `formats/xlights`
  unnecessary. Note M6b's security flag: that API has no documented authentication.

The generate-fresh contract remains the right target for the export path; it is no
longer the only path worth costing.

---

## 12. My own view: is deferring the display pipeline right?

**Yes, defer — but Stage 2's stated reasons are not the load-bearing ones, and
"defer" must not be read as "delete".**

Stage 2 defers display as "a coherent second product whose revival re-opens image
spend". Both are true and neither is decisive. The decisive reasons are in this review:

1. **The composition engine's timing contract is broken in two independent ways that
   interact** (P5-F1, P5-F2), with a third defect silently dropping a planner input
   (P5-F3) and a fourth silently substituting a flat `On` for any effect type it does
   not recognize (P5-F8/M1). Output would look plausible and be wrong — coordination
   modes that don't coordinate, ripples that don't ripple, placements shifted a full
   beat, lane blend modes that never arrive. Nobody would notice without an xLights
   preview and a trained eye, because **nothing in the output says so**: the one
   substitution that does get detected is logged and then dropped before it reaches
   `WriteResult`, the trace sidecar, or any artifact a human sees.
2. **The tests that would have caught this cannot run** (P5-F11), because the recipe
   corpus is gitignored. Wiring display to the CLI without first restoring a corpus and
   fixing the tests means shipping a renderer with no runnable coverage of its core
   logic.
3. **Recipe content is unverifiable** (P5-F8). Even with the corpus restored, there is
   no enforcement that recipe parameter names match handler expectations, and no
   diagnostic when they don't.

**Is display closer to shippable than Stage 2 credits?** In *engineering maturity*, yes
— materially. It has 9,950 LOC of tests, the best observability in the repo (the trace
sidecar), clean layering, and the only from-nothing `.xsq` emitter. In *correctness*,
no — it is further away, because the defects are in the composition logic rather than in
plumbing.

**What wiring it to the CLI would actually take** (assuming the defects are fixed):

| Work | Estimate |
|---|---|
| A `twinklr display` subcommand + config surface | 1 day |
| A real `ChoreographyGraph` source — currently 74 hardcoded lines in `cli/main.py:62-135` whose own comment admits layout parsing is future work. The layout parser exists (`formats/xlights/layout/`) and is unwired; connecting it is the honest fix | 2–3 days |
| Restore/generate a recipe corpus — `data/templates` must exist and be non-empty or the stage fails at `display_stages.py:266`. Either commit a small tracked starter catalog or make `recipe_builder` reproducible | 2–5 days, **the real blocker** |
| Fix P5-F1/F2/F3 + tests | 2–3 days |
| Fix P5-F8 (wire or delete `resolved_color`/`timing_offset_beats`/mix; validate recipe params) | 1–2 days |
| Asset path decisions (`enable_assets` default False; image spend) | phase 3's call |

**≈ 8–14 days**, dominated by the corpus problem — which is a *data* problem, not a code
problem, and which no amount of code review can resolve.

**The one thing that should not be deferred:** the display package's export half —
`XSQWriter`, `EffectDBRegistry`, `PaletteDBRegistry`, `build_palette_string`, and the
fresh-sequence emitter — is the reference implementation for the very contract Stage 2
recommends for the *shipped* path. Deferring the display *pipeline* while harvesting its
*writer* (dedup registries into the moving-heads path, P5-F15; the fresh-sequence
pattern into `xsq_export.py`, V-contract) is strictly better than deferring both.

---

## 13. Unresolved questions & cross-phase dependencies

**Requires Stage 4 (runtime):**

1. Does a generated `.xsq` open in xLights 2026.15, and what does xLights write back
   when it saves? (V4 protocol above.) The saved-file diff also answers P5-M3
   (quantization) and P5-M4 (absent palette attribute) at no extra cost.
2. ~~Confirm the collection-time errors from the absent `data/templates`.~~
   **CONFIRMED** — 52 failures in the Stage 4 run (P5-F11).
3. **Shutter-zero: physical confirmation only.** V1 no longer needs Stage 4 to
   establish intent — the repo declares `open=255` / `closed=0` and defaults
   `shutter_default=255` in three places with zero readers. Stage 4's remaining job is
   to confirm the author's physical fixtures follow that convention. (Note: the first
   draft mistakenly cross-referenced "P5-F1" here; the finding at issue is **V1**.)
4. Does a bare `.xsq` import into xLights without an accompanying
   `xlights_rgbeffects.xml`? (M6b's one open residual; gates the V-contract.)

**Cross-phase seams:**

- **Phase 4 (moving heads)** owns the template side of V1; this phase owns the export
  side. Joint conclusion recorded above — phase 4 should cite it rather than re-derive
  it. Phase 4 also owns `vocabulary/duration.py`, whose 5-bucket `DURATION_BEATS` is the
  proximate cause of half of P5-F1; any change there must be coordinated.
- **Phase 3 (agents)** owns `agents/assets/`; this phase reviewed only the *consumption*
  of resolved assets (`engine.py:827-910`). The Pictures filename is the most concrete
  reachable input to the settings-string injection surface (P5-F6) — phase 3 should
  confirm whether asset filenames are LLM-derived.
- **Phase 1** owns `pipeline/display_stages.py` as a stage definition; this phase
  reviewed its rendering behavior and its `2024.01` stamp. The unguarded
  `TemplateStore.from_directory` at `:266` sits on that boundary.
- **Phase 7** owns `cli/main.py`; the hardcoded 74-line choreography graph
  (`cli/main.py:62-135`) is the blocker for any display CLI wiring, and the unwired
  layout parser is its natural replacement.

**Open questions this phase could not answer:**

- What is actually in a recipe? `data/templates` is absent, so recipe quality,
  parameter-name conformance, and expression usage are all unknown. Discovery unknown #4
  stands unresolved and is now blocking four separate findings (P5-F8/M1, F11, F14,
  and the effect-type validation fix). The Stage 4 result (52 failures) makes this the
  phase's top blocker.
- ~~Does xLights' effect import accept a minimal externally-generated `.xsq`?~~
  **Largely answered by M6b**: yes for donor sequences carrying effects and timing
  tracks, subject to pre-existing models and name mapping. Narrowed residual in the
  Stage 4 list above.
- Was `effect_resolver.py` abandoned or merely unfinished? No commit-message or
  change-doc evidence was sought (history is phase 7's); the answer determines DELETE
  vs. WIRE for 504 lines.

---

## 14. Phase verification status

**VERIFIED — 2026-08-13, opus critic (non-author), with security-reviewer participation
per plan.md's network/LLM/XML trust-boundary rule.**

**11 ACCEPTED · 4 REVISED · 0 REJECTED · 6 verifier-added findings adopted (P5-M1…M6).**

| Verdict | Items |
|---|---|
| ACCEPTED | P5-F1 (re-derived exactly), F2 (re-derived; one-line fix confirmed), F5, F6, F7, F8, F9, F13, F16, F17, F18 |
| REVISED | **P5-F3** (HIGH→MEDIUM, mechanism inverted), **P5-F10** (converters fully dead; cheaper), **P5-F12** (conclusion held, mechanism corrected), **P5-F14** (conclusion held, provenance argument struck) |
| STRENGTHENED | **V1** (caveat removed; repo declares the convention itself), **P5-F4** (second corruption vector), **P5-F11** (→CONFIRMED, 52 Stage 4 failures), **P5-F15** (seeding prerequisite) |
| CORRECTED | **V-contract** (two factual errors: `--xsq` required; `profiling/` uses `XSQParser`) |
| REJECTED | none |

**Adopted verifier findings:** P5-M1 (merged into P5-F8, raising it to MED-HIGH),
P5-M2, P5-M3, P5-M4, P5-M5, P5-M6.

**Confirmed clean by the verifier** (no changes required): the §2 architecture maps, the
§10 V4 emitted-file table, the §4 XML-hygiene assessment (defusedxml correct on both
paths; no XML-injection path even with unescaped settings values), the counts in §5
including zero TODOs across 18.7k LOC, the absence of any sample `.xsq` in git history,
and the §12 defer-but-harvest recommendation — the verifier concurs, subject to the
P5-F15 seeding prerequisite.

**Hygiene corrections applied:** two off-by-one line references in the P5-F10
`DisplayGraph` re-export citations (now `templates/group/models/__init__.py:8,28,76-77`
plus `agents/sequencer/group_planner/__init__.py:67,100`); the stray "P5-F1"
cross-reference in §13 item 3, which should have read "V1"; and the handler count, which
is 24 rather than the 23 named in the phase charter.

**Post-verification note:** the Stage 6 modernization document has since gained §M6b
(xLights integration surfaces). Its findings are incorporated where they bear — the V4
risk list (version stamp downgraded: documented cutoff is pre-2020 and warns rather than
rejects), the V-contract residual risk (effect import confirmed to accept donor
sequences; `.xtiming`-only and `addEffect`-injection surfaced as alternatives), and
P5-F17 (severity lowered). These are refinements from newer evidence, not verifier
corrections, and are attributed to M6b inline.
