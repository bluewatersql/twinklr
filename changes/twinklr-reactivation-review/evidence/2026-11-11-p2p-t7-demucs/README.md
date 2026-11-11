---
type: change
status: active
area: engineering
created: 2026-11-11
updated: 2026-11-11
---

# P2P-T7 real Demucs separation on Apple Silicon — 2026-11-11

Run per [runbook 05 §5](../../runbooks/05-phase-2p-and-3-live-evidence.md). Authority:
[P2P-T7 spec](../../build/specs/phase-2p-creative-quality/P2P-T7-stems-stage.md). No paid API.

| Field | Value |
|---|---|
| Window (UTC) | 2026-11-11T21:32:19Z – 21:32:39Z |
| Host | Apple Silicon (`uname -m` = `arm64`), `torch.backends.mps.is_available()` = `True` |
| Versions | demucs 4.1.0, torch 2.8.0 (installed with `uv sync --locked … --extra stems --all-packages`, no lock change) |
| Git SHA | `722c58d7632b607c1b02f825449c7f51554481a0` |
| Input | `data/music/Hey Come Look At My House.mp3`, 140.9 s, owner-local and not committed |
| Test | `test_real_separation_smoke`, run with `-m local_only -o log_cli_level=WARNING` |
| Result | **PASS.** `drums`, `bass`, `vocals` and `other` stems were all produced. |
| Wall time | **19.19 s** (the `--durations=1` call time). The spec expectation was about 1–2 min on MPS and the test limit is 1,200 s. |
| Device | Demucs chose its own device: CUDA, then MPS, then CPU. **The MPS→CPU fallback warning (`retrying once on CPU`) did not appear**, so separation ran on its first-choice device (MPS on this host) without falling back. |

Log: [pytest.log](pytest.log).

The forced-failure path for the MPS→CPU fallback has no live command in the spec. It is
covered only by stubbed unit tests, as runbook 05 §5 step 4 notes.
