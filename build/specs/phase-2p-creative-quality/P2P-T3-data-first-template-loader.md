# P2P-T3 — Data-first template loader

Phase: 2P (Creative Quality, Measured) · Lane: S (schema/channel, serial) · Executor: opus · Verifier: opus · Depends on: P2P-T2

## Objective

Make the template library loadable from data. The registry accepts JSON/YAML
`TemplateDoc` documents alongside the 37 Python builtins; a converter emits the
data form from the Python form; both forms coexist indefinitely so migration is
progressive and no big-bang re-authoring is required. This is what turns P2P-T2's
"re-author 37 Python files" cost into a data edit, and it is the structural step that
later lets a moving-head template and a display recipe be the same kind of object.

## Evidence & background

Findings: **D1 design** (widen the channel), **P4 template census / §7**
(template authoring as Python code vs data), **P4-F24/F25** (the library is a real
domain asset; the cost of adding template #38).
Sources: `changes/twinklr-reactivation-review/reviews/phases/moving-heads-rendering.md`
§7, §9, §10, P4-F16's conclusion, P4-F24/F25;
`.../reviews/reactivation-proposal.md` D1, §2.3.

The review's recommendation, quoted:

> **Template authoring as Python code vs. data.** All 37 templates are Python modules
> registered by import side effect. Adding template #38 means: create a file, import
> ~15 symbols, construct a nested `TemplateDoc` (~90 lines, of which ~55 are
> boilerplate imports and structure), add it to `templates/builtins/__init__.py`, and
> reinstall the package. There is no schema file, no validation CLI, no hot reload,
> no way for a non-Python user to contribute. Since the models are already Pydantic,
> a YAML/JSON representation with `TemplateDoc.model_validate` is a near-free
> alternative that would (a) make the library user-extensible, (b) allow
> diffing/reviewing templates as data, (c) enable a template linter that would have
> caught P4-F5 and P4-F6 mechanically. **Recommend: keep the Python form as an
> authoring convenience, but make the loader data-first.** This is the single
> highest-leverage modernization in the phase and it is small.

P4-F16's dependent conclusion:

> the bulk is template re-authoring, which argues strongly for the data-first
> template loader recommended in §7 — do that first and the 37-template re-authoring
> becomes a data edit rather than 37 Python diffs.

Verified in-tree structure the executor builds on:

- `TemplateRegistry` (`sequencer/moving_heads/templates/library.py`) stores
  **factories**, not instances: `register(factory, *, template_id=None,
  aliases=())` materializes once for validation + metadata, honors `t.enabled`
  (logs and skips disabled templates), rejects duplicate ids, and keeps
  `TemplateInfo` for listing without materializing. Callers always get a fresh
  `Template` (deep-copy defaults confirmed as a strength, `library.py:93`).
- `TemplateDoc` is already a Pydantic model (`sequencer/models/template.py`) with
  `extra="forbid"` throughout and `TemplateMetadata` carrying `tags`,
  `recommended_sections`, `energy_range`, `description`.
- Census: 37 registered builtins; 34/37 geometry-movement-dimmer combinations
  unique; 17 geometry types, 20 movement types, 5 dimmer types; annotations 37/37
  complete with zero sparse fields. **This is a real library, not a template pile** —
  the loader must not lose any of it.

The two defects a data-form linter would have caught mechanically (P4-F5, P4-F6)
are fixed by P1P-T5; the linter's value here is preventing their reintroduction and
catching the same class in user-contributed templates.

Line numbers are hints from baseline `aa8d325`; re-verify before editing.

## Current behavior

- Templates are Python modules under
  `packages/twinklr/core/sequencer/moving_heads/templates/builtins/`, registered by
  import side effect via `builtins/__init__.py`.
- There is no schema file, no validation CLI, no way to add a template without
  editing Python and reinstalling the package.
- Nothing in the repo reads a template from data.

## Target behavior

1. **The registry accepts data documents.** A loader reads `TemplateDoc` JSON (and
   YAML if trivially free via the existing dependency set — do not add a YAML
   dependency for this alone) from a configured directory and registers each as a
   factory, using the same validation, `enabled` handling, duplicate-id rejection and
   `TemplateInfo` extraction the Python path uses. One registry, two sources.
2. **Precedence is explicit and documented**: builtin Python templates load first;
   data templates load second; a data template with a colliding `template_id` is a
   loud error by default, with an explicit override flag if the design wants
   user-shadowing of builtins. Decide and document — silent shadowing is the failure
   mode to avoid.
3. **A converter emits the data form from the Python form.** A CLI/script walks the
   registry and writes one document per template, round-trip-exact:
   `TemplateDoc.model_validate(json.loads(dump(doc))) == doc` for all 37.
4. **A template linter** runs over any template regardless of source and checks the
   structural properties whose absence caused verified defects — at minimum:
   multi-step templates' step timings partition their cycle (P4-F5 class), no step
   schedule overruns `cycle_bars` (P4-F6 class), `energy_range` present and ordered,
   `recommended_sections` non-empty, remainder policy declared. Wire it into
   `make validate` or the P1P-T1 golden suite.
5. **Progressive migration path.** No template is required to move. The 2–3
   templates P2P-T2 migrated to carry color/shutter/gobo axes are converted to data
   form as the proof case; the rest stay Python until someone has a reason to move
   them.
6. **Convergence note recorded, not implemented.** Write into the loader module
   docstring (and `context/` at closeout) the observation from D1's design
   discussion: *a data-first moving-head template is structurally a recipe — one
   catalog, two renderers, later.* This task does not unify them; it makes the later
   unification possible and records why.

### Non-goals

- Converting all 37 templates to data (explicitly progressive).
- Unifying moving-head templates with display recipes / `EffectRecipe` (the
  convergence is noted, not built; P1K-T3 owns the catalog format and must NOT
  invent a new one).
- A template-authoring UI, hot reload, or a package-external plugin mechanism.
- Changing `TemplateDoc`'s shape. If the data form needs a field the model lacks,
  that is a P2P-T2 concern, not a loader concern.

## Implementation approach

Files/symbols (re-verify first):

- `packages/twinklr/core/sequencer/moving_heads/templates/library.py` —
  `TemplateRegistry.register`, `TemplateInfo`, `_norm_key`; add the data-source
  registration path beside the factory path.
- `packages/twinklr/core/sequencer/moving_heads/templates/__init__.py` /
  `builtins/__init__.py` — where builtin registration happens today.
- New: a loader module (data-document discovery + validation + registration) and a
  converter entry point. Follow the repo's existing CLI conventions; do **not**
  create a `scripts/build/*` tool — CC-2 records 60 tests written for six such
  scripts that never existed, and that class is being retired, not extended.
- `packages/twinklr/core/sequencer/models/template.py` — read-only reference for the
  document schema.
- Config: where the data-template directory lives. Coordinate with P1K-T3's tracked
  catalog home if that has landed — same data-home question, one answer; if 1K has
  not merged, pick a location and flag it in the handoff for reconciliation.

Sequencing constraints copied verbatim from the plan:

> - **Verification currency**: evidence in specs is from baseline `aa8d325`.
>   Executors must re-verify cited line numbers before editing (the tree will drift
>   as phases land) — specs cite symbol + file, with line numbers as hints only.
> - `make validate` equivalents (check-only forms until P0-T4 lands the guard) must
>   pass at every merge; golden tests (once P1P-T1 exists) must pass for any lane
>   touching render/export code.

Repository-hygiene constraint from `AGENTS.md`: generated data-form templates are
project knowledge only if they are the source of truth for a template. Round-trip
exports produced for verification are scratch output — write them to the session
scratchpad, not into the tree.

## Acceptance criteria

1. `TemplateRegistry` registers templates from data documents through the same
   validation path as Python factories, including `enabled` handling and duplicate-id
   rejection.
2. Round-trip exactness: for all 37 builtins, converting to data form and re-loading
   yields a `TemplateDoc` equal to the Python-constructed one (field-by-field, not
   just id equality).
3. Precedence and collision behavior are implemented and documented in the module
   docstring; a colliding id produces a loud failure (or a documented, flagged
   override).
4. The template linter runs over both sources and fails on a template that overruns
   its `cycle_bars` or leaves `energy_range` empty. It is wired into the validate/
   golden path.
5. **Golden-diff BEFORE/AFTER: byte-identical.** Loading a template from its
   round-tripped data form produces the same emitted settings strings as loading the
   Python builtin. This is the task's central correctness claim.
6. The 2–3 axis-carrying templates from P2P-T2 exist in data form and render
   identically from either source.
7. The convergence note ("one catalog, two renderers, later") is recorded in the
   loader docstring.
8. `make validate` check-only forms pass.

## Tests

TDD — failing first:

1. `test_all_builtins_round_trip_through_data_form` — parametrized over all 37
   registered templates; the single highest-value test in this task.
2. `test_data_template_registers_and_renders` — a template that exists **only** as a
   data document is selectable and renders.
3. `test_duplicate_template_id_across_sources_is_loud` — pins the precedence
   decision, including the error message.
4. `test_disabled_data_template_is_skipped` — mirrors the Python path's `enabled`
   behavior.
5. `test_linter_rejects_overrunning_template` — construct a template whose steps
   exceed `cycle_bars` (the P4-F6 shape) and assert the linter fails it.
6. `test_linter_rejects_missing_annotations` — empty `energy_range` /
   `recommended_sections`, the columns P2P-T13's deterministic arm joins on.
7. Golden render equality test (criterion 5).

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest tests/unit/sequencer -q
uv run pytest -k "template and (loader or round_trip or linter)" -q
uv run pytest -k golden -q
```

No paid API calls, no LOCAL-ONLY steps.

## Effort & risk

**M.** Main risk: round-trip inexactness hiding in tuple-vs-list, enum-vs-string, or
`None`-vs-absent asymmetries — the kind of drift that renders identically today and
diverges after an unrelated Pydantic bump. Mitigation: assert model equality (not
serialized-string equality) across all 37 in a parametrized test, and add the golden
render equality check so a silent semantic drift also fails a byte comparison.
Second risk: the data-home location conflicting with P1K-T3's tracked catalog —
mitigated by flagging it in the handoff rather than inventing a second home.
