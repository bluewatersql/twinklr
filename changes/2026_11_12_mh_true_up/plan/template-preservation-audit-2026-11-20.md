---
type: plan
status: complete
area: engineering
updated: 2026-11-20
---

# Template preservation audit

Owner asks to validate that no templates were lost because the counts seem off.
Root owns `codex/audit-template-preservation`; reviewer reads only. Compare historical
registered built-ins and JSON copies immediately before `0ec65d47`, the seven-family
catalog at `e0376f66`, current production catalog and both sample manifests. Distinguish
IDs, full arrangements, path capabilities, presets and video entries. Do not accept a
mapping to a primitive as proof of template parity. Inventory every historical ID and
verify current loading/preset availability with offline checks. Record proven retention,
known omissions and unproven equivalence; correct overbroad current coverage claims.
No renderer changes, provider calls, owner-show mutations or new video generation.
CI stays paused. Prior commit/merge/sync authorization persists.

Acceptance: reproducible counts and per-template inventory, direct source examples of
any arrangement gaps, independent review, evidence/handoff and concise owner report.
Use focused catalog/restoration checks; full application gate is skipped if only audit
and documentation change. No human taste or physical acceptance claims.

Audit complete: recent seven-family catalog is byte-identical; all 25 current
families load; both sample counts reconciled; 40 focused tests passed. Independent
source review confirms historical arrangement gaps. Evidence and current context
now distinguish mapping from preservation. No source edits; full gate skipped.
See [findings](../evidence/2026-11-20-template-preservation/README.md).
