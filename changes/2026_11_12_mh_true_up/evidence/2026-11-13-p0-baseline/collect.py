"""Collect the Phase 0 baseline evidence: diagnostics and fingerprints."""
from collections import Counter
from twinklr.core.config.models import JobConfig
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline
from twinklr.core.agents.sequencer.moving_heads.deterministic_selector import SelectorSection
from twinklr.core.agents.sequencer.moving_heads.reference_policy import build_reference_plan
from twinklr.core.sequencer.moving_heads.templates.library import REGISTRY
from tests.golden.harness import RIGS, build_fixture_group, build_plan, build_beat_grid
from tests.support.mh_true_up import CASE_IDS, synthetic_case

def summarize(p):
    c = Counter(d.control.value for d in p.diagnostics)
    return ", ".join(f"{k}={v}" for k, v in sorted(c.items())) or "none"

print("## golden rigs")
for rig_id, rig in RIGS.items():
    p = RenderingPipeline(choreography_plan=build_plan(), beat_grid=build_beat_grid(),
                          fixture_group=build_fixture_group(rig), job_config=JobConfig())
    print(f"| `{rig_id}` | {summarize(p)} | `{p.fingerprint()}` |")

print("## synthetic cases")
for cid in CASE_IDS:
    case = synthetic_case(cid)
    if not case.legacy_runnable:
        print(f"| `{cid}` | input only | - | - | - |"); continue
    for group, outcome in zip(case.fixture_groups, case.legacy_outcomes, strict=True):
        p = RenderingPipeline(choreography_plan=case.plan, beat_grid=case.beat_grid,
                              fixture_group=group, job_config=JobConfig())
        print(f"| `{cid}` | {len(group.fixtures)} | {outcome} | {summarize(p)} | `{p.fingerprint()}` |")

print("## reference arm")
specs = [("intro", 20), ("verse", 45), ("build", 60), ("chorus", 80), ("verse", 45), ("chorus", 85), ("outro", 30)]
sections = [SelectorSection(section_id=f"{r}_{i}", role=r, start_bar=(i-1)*4+1, end_bar=i*4, energy=e)
            for i, (r, e) in enumerate(specs, start=1)]
res = build_reference_plan(sections, seed=41, admitted_template_ids=frozenset(i.template_id for i in REGISTRY.list_all()))
for s, d, t in zip(sections, res.decisions, res.baseline.traces, strict=True):
    print(f"| `{d.section_id}` | {s.role} | {s.energy} | `{t.selected_template_id}` | `{d.preferred_template_id}` | `{d.selected_template_id}` | {d.reason} |")
