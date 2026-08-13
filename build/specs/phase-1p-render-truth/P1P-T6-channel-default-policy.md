# P1P-T6 — Channel-default policy

Phase: 1P (Render Truth) · Lane: R (render repair, serial) · Executor: sonnet · Verifier: opus · Depends on: P1P-T5

## Objective

Stop the exporter from driving every channel it did not choreograph to zero. Unwritten
channels must emit the fixture's *declared* defaults — shutter open at 255, configured
color/gobo values — or be omitted entirely, per an explicit, tested policy. This is the
finding that plausibly makes shipped shows produce no light at all on 12- and 16-channel
moving heads.

## Evidence & background

Findings: **CF-7** = **P4-F3** + **P5-V1**, with **P4-F16** for the dead configuration
surfaces this task connects or deletes.

Line numbers are hints from baseline `aa8d325`. Re-verify before editing.

### The zero-fill (P4-F3, verbatim):

> `export/dmx_settings_builder.py:77-83`:
>
> ```python
> for ch in range(1, max_channel + 1):
>     if ch in channel_curves:
>         parts.append(f"E_SLIDER_DMX{ch}=0")
>     else:
>         parts.append(f"E_SLIDER_DMX{ch}={int(channel_values.get(ch, 0))}")
> ```
>
> `max_channel` has a floor of 16 and rounds up to a multiple of 16
> (`_calculate_max_channel`, `:233-259`). `channel_values` is populated only from the
> segment's channels, which are exactly PAN, TILT, DIMMER (`step_compiler.py:198-227`).
> **Every other channel in 1–16 is emitted with an explicit value of 0**, whether or not the
> fixture maps it and whether or not the user configured a default.
>
> This repository's own model says what 0 means on the shutter: `ShutterLibrary.DMX_CLOSED =
> 0`, `DMX_OPEN = 255` (`libraries/shutter.py:53-54`).

### The three ignored declarations (P4-F3 `[V]`, verbatim):

> **[V] Three separate declarations of channel convention exist; the exporter honours none
> of them** (the third was added by the verifier):
>
> 1. `DmxChannelMapping.shutter_default = 255`, commented *"usually open"*
>    (`config/fixtures/dmx.py:94-95`) — **zero readers** anywhere.
> 2. `JobConfig.is_channel_enabled` / `ChannelDefaults` (`config/models.py:565`, `:129`) —
>    **zero readers**.
> 3. `config/adapter.py:77 get_max_channel` — computes the rig's *actual* highest DMX channel
>    across pan, tilt, dimmer, fine channels, shutter, colour and gobo (`:99-115`) — **zero
>    callers**. `DmxSettingsBuilder._calculate_max_channel` (`:233-259`) instead reinvents a
>    floor-16 / round-up-to-16 rule from only the channels it happened to write.

Re-verified in the current tree: `config/fixtures/dmx.py:16-17` (`ShutterMap.closed=0`,
`open=255`), `:94-95` (`shutter_default=255`, "Default shutter value (usually open)"),
`config/models.py:129` (`class ChannelDefaults`), `:565` (`def is_channel_enabled`),
`config/adapter.py:77` (`def get_max_channel`), and the emit loop at
`dmx_settings_builder.py:75-83` with `_calculate_max_channel` at `:233`.

### Phase 5's independent derivation (P5-V1, verbatim):

> **Why this is worse than omission — and the repo says so itself.** The first draft of
> this review called the shutter risk "unverifiable from the repo" and deferred it to a
> Stage 4 hardware check. **That caveat was wrong** (verifier correction; phase 4 derived
> the same result independently and this review defers to it). …
> So the exporter unconditionally forces to `0` the exact
> channel the repository's own configuration defaults to `255` and documents as "usually
> open" — and the field that would have fixed it exists, is validated, and is never read.
> This is no longer a hypothesis about unknown hardware; it is a contradiction internal to
> the codebase, and it is the single highest-impact defect this phase found.

And the fix guidance (P5-V1, verbatim):

> `JobConfig.is_channel_enabled()`, `ChannelDefaults`, and `shutter_default` are exactly
> the mechanism designed for this and never connected; reading them at
> `dmx_settings_builder.py:77-83` instead of defaulting to `0` is a small, well-scoped fix
> and should be sequenced ahead of any template work.

### The conditional blast radius (P4-F3 `[V]`, verbatim — carry this counter-evidence):

> **[V] Physical consequence: conditional — counter-evidence carried.** The zeroing only
> reaches a channel that falls *inside* the emitted window. Because `_calculate_max_channel`
> takes its maximum over written channels only (PAN/TILT/DIMMER) and rounds to 16, the window
> is normally 1–16. **The only fixture configuration tracked in this repository puts the
> shutter at channel 17** (`tests/unit/config/test_fixtures.py:399`, `shutter_channel=17`) —
> outside the window, so for that profile no `E_SLIDER_DMX17` is emitted at all and the
> console/model default governs. The no-light outcome therefore holds for fixtures whose
> shutter is mapped within 1–16 (common on 12- and 16-channel moving heads) and **not** for
> profiles like the one in-repo. Severity stays HIGH with the conditional stated.

The two-arm test that settles it is already implemented in P1P-T1 (shutter at 6 vs 17);
**this task changes the expectation of the `shutter_channel=6` arm and must update that
test and its golden deliberately.**

## Current behavior

- Every emitted DMX effect contains `E_SLIDER_DMX{ch}=<value>` for every channel from 1
  to `max_channel` (≥16), with `0` for every channel the renderer did not write —
  including shutter, color and gobo when they fall inside the window.
- `shutter_default`, `ChannelDefaults`, `is_channel_enabled`, and `get_max_channel` have
  zero readers/callers.
- The emitted window size is derived from the channels the renderer happened to write,
  rounded up to a multiple of 16 — not from the rig's actual channel count.

## Target behavior

An explicit, documented channel-default policy, applied at the emit loop:

1. A channel the renderer wrote → its computed value (unchanged).
2. A channel the fixture **maps** but the renderer did not write → the fixture's declared
   default (`shutter_default`, and the configured color/gobo values), not 0.
3. A channel the fixture does **not** map → omitted from the settings string entirely
   (leave it to the console), rather than emitted as 0.
4. The emitted window is derived from the rig's real channel count via
   `config/adapter.py::get_max_channel`, not from a floor-16/round-to-16 rule over written
   channels.
5. `is_channel_enabled` / `ChannelDefaults` are either **wired** into this policy or
   **deleted with an explicit note** in the same change — no third state. The phase plan
   says: *"wire `is_channel_enabled`/`ChannelDefaults` or delete them explicitly per
   rig-config design"*. The deciding question is whether the rig-config design (P1P-T2's
   files, which P1P-T11 promotes to CLI input) already expresses per-channel enablement;
   if it does, delete the `JobConfig` duplicates rather than maintaining two.

**Non-goals.** Do not add color/gobo *choreography* — no fourth template axis, no
`ColorHandler` (that is the P4-F16 "widen the channel" work, Phase 2P/3). Do not delete
`libraries/{color,gobo,shutter}.py` (the review explicitly says keep them if the channel
is widened). Do not change curve precision, dimmer values, or timing.

## Implementation approach

Files/symbols to touch:
- `packages/twinklr/core/sequencer/moving_heads/export/dmx_settings_builder.py` — the emit
  loop (`:75-83`) and `_calculate_max_channel` (`:233`).
- `packages/twinklr/core/config/adapter.py` — `get_max_channel` (`:77`) gains its first
  caller; verify its handling of fine channels and unmapped channels first (it has never
  run in production).
- `packages/twinklr/core/config/fixtures/dmx.py` — `shutter_default`, `color_map`,
  `gobo_map` become readable inputs to the policy.
- `packages/twinklr/core/config/models.py` — `ChannelDefaults` (`:129`) and
  `is_channel_enabled` (`:565`): wire or delete, per the decision above.
- The seam that carries fixture config into the exporter (whatever supplies
  `DmxSettingsBuilder` today) — the policy needs the mapping, so this may require passing
  the fixture/rig profile rather than just the segment.
- `tests/golden/**` — the shutter-6 arm's expectation changes.

Design decisions already made (do not relitigate):
- **Unmapped channels are omitted, not defaulted.** Emitting a value for a channel the rig
  does not have is how this defect started.
- **The policy lives in one place** (the emit loop's value resolution), not scattered
  across callers.
- **`get_max_channel` is the window authority.** Do not keep the floor-16 rule as a
  fallback unless a test proves a rig where `get_max_channel` returns a value that breaks
  xLights; if such a case exists, document it.

Sequencing constraints (copied verbatim from `build/plan/00-overview.md`):

> `make validate` equivalents (check-only forms until P0-T4 lands the guard) must pass
> at every merge; golden tests (once P1P-T1 exists) must pass for any lane touching
> render/export code.

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases land)
> — specs cite symbol + file, with line numbers as hints only.

From `build/plan/02-phase-1p-render-truth.md`:

> **Lane R (render repair, serial — shared files in `sequencer/moving_heads/` +
> `curves/`)**: T3 → T4 → T5 → T6.

> Merge order at phase end: G → R → A → I → D (D rebases on R for exporter touches).

Note for the executor: **P1P-T11 (Lane D) also touches the exporter** and rebases onto
Lane R. Keep this task's diff confined to channel-value resolution so that rebase stays
mechanical.

## Acceptance criteria

- [ ] With the reference rig (`shutter_channel=6`), the emitted settings string contains
      `E_SLIDER_DMX6=255` (the declared `shutter_default`), **not** `E_SLIDER_DMX6=0`.
      This is the inverted expectation of the P1P-T1 test; that test and its golden are
      updated in this change, and the update is called out in the commit message.
- [ ] With `rig_shutter_high` (`shutter_channel=17`), no `E_SLIDER_DMX17` token is emitted
      **unless** the rig's real channel count places 17 inside the window via
      `get_max_channel`; if it does, the token is `=255`, never `=0`.
- [ ] No `E_SLIDER_DMX{ch}=0` token is emitted for any channel the fixture does not map.
- [ ] `get_max_channel` has a production caller; `_calculate_max_channel`'s
      floor-16/round-to-16 rule is gone (or retained only as a documented, tested
      exception).
- [ ] `shutter_default` has a production reader (the review's "zero readers" statement is
      no longer true for it).
- [ ] `ChannelDefaults` / `is_channel_enabled` are either read by the policy or removed
      from the codebase, and the choice is stated in a code comment or the change's
      handoff. `grep` shows no remaining "declared but unread" state for these two.
- [ ] The validator (`mh_xsq_validation.py`) — which already *"cross-checks shutter/colour/
      gobo channels against the fixture map"* — reports no channel-map violation on the
      golden render.
- [ ] `make validate` check-only equivalents pass; golden suite regenerated with reviewed
      diffs.

**Golden-diff expectation (BEFORE/AFTER), all three rigs:**

```
BEFORE (rig_4head_reference, shutter_channel=6):
  ...,E_SLIDER_DMX5=0,E_SLIDER_DMX6=0,E_SLIDER_DMX7=0,...   # 16 sliders always
  every unwritten channel 1..16 emitted as 0, including shutter=6

AFTER (rig_4head_reference):
  E_SLIDER_DMX6=255                      # shutter open, from shutter_default
  unmapped channels: token ABSENT from the string entirely
  mapped-but-unwritten color/gobo: their configured defaults, not 0
  window width now derived from get_max_channel, so the count of E_SLIDER_DMX
  tokens per effect CHANGES — this is the most visible diff and is expected

BEFORE/AFTER (rig_shutter_high, shutter_channel=17):
  BEFORE: no E_SLIDER_DMX17 token (outside the floor-16 window)
  AFTER : token present as =255 IF get_max_channel puts 17 in range for that
          rig; still absent otherwise. Either outcome is acceptable, but it
          must be asserted explicitly rather than left implicit.

UNCHANGED in this diff: PAN/TILT/DIMMER values and value curves (owned by
P1P-T3/T5), effect start/end times (P1P-T4), E_VALUECURVE_DMX payloads.
Any movement in those tokens means this task overreached.
```

## Tests

TDD: invert the shutter-6 assertion first (it fails), then implement the policy.

| Test | Behavior pinned |
|---|---|
| `test_mapped_unwritten_shutter_emits_declared_default` | The headline: 255, not 0 |
| `test_unmapped_channel_is_omitted` | No zero-fill for channels the rig does not have |
| `test_window_derived_from_get_max_channel[rig]` | `get_max_channel` is the authority; floor-16 rule retired |
| `test_written_channels_unchanged` | PAN/TILT/DIMMER resolution is untouched by the policy |
| `test_color_gobo_defaults_from_fixture_map` | Mapped color/gobo emit configured values |
| `test_channel_defaults_wired_or_absent` | `ChannelDefaults`/`is_channel_enabled` are not left in the dead-config class |
| `test_validator_channel_crosscheck_clean` | The existing validator's shutter/color/gobo cross-check passes on the golden render |
| Golden suite (P1P-T1) | Reviewed BEFORE/AFTER diff as specified above |

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .

uv run pytest tests/unit/sequencer/moving_heads -v
uv run pytest tests/golden -v

# defect-specific checks the verifier runs
grep -rn "shutter_default" packages/twinklr/core/sequencer packages/twinklr/core/config   # expect: a real reader, not just the declaration
grep -rn "get_max_channel" packages/ | grep -v "config/adapter.py"                        # expect: a production caller
grep -rn "is_channel_enabled\|ChannelDefaults" packages/                                  # expect: wired, or gone
```

No LOCAL-ONLY steps. No paid API calls. (Whether a physical fixture honors the convention
is confirmed empirically in P1P-T12, LOCAL-ONLY.)

## Effort & risk

**Effort: S–M.** The emit-loop change is small; plumbing the fixture map to the exporter
may not be.

**Main risk: changing the emitted window width changes the shape of every settings string
in the file**, so an xLights compatibility problem introduced here would look like "the
file opens but effects behave oddly" — the hardest failure to detect (P5 §V4 item 5).
Mitigation: P1P-T12's LOCAL-ONLY xLights acceptance test explicitly covers "verify
shutter-open output on the >16-channel rig config"; until that runs, keep the change
reviewable by asserting exact token sets in the goldens rather than substring matches.

**Second risk: `get_max_channel` has never executed** (zero callers). Mitigation: unit-test
it directly against all three P1P-T2 rigs — including fine channels and absent optional
channels — before wiring it in.

**Third risk: deleting `ChannelDefaults`/`is_channel_enabled` conflicts with P0-T7**,
which explicitly must *not* touch channel/fixture defaults because they get wired here.
Mitigation: if the decision is "delete", confirm P0-T7 left them in place and say so in
the handoff so the two tasks do not both claim the deletion.
