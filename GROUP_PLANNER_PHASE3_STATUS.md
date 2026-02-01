# GroupPlanner Phase 3 - E2E Testing & Validation

**Date:** 2026-01-31  
**Status:** READY FOR E2E TESTING  
**Prerequisites:** Phases 1 & 2 Complete ✅

---

## Summary

Phase 3 validates the complete GroupPlanner agent flow end-to-end with real LLM calls. This phase demonstrates that the template framework (Phase 1) and agent integration (Phase 2) work together correctly to generate valid GroupPlans.

---

## Components Validated ✅

### 1. Template Registry (Phase 1)
- ✅ 12 templates auto-register on import
- ✅ `list_templates()` returns TemplateInfo objects
- ✅ Template search by ID, alias, tags works

### 2. TemplateRef Conversion (Phase 2)
- ✅ `template_ref_from_info()` converts TemplateInfo → TemplateRef
- ✅ TemplateRef includes: `template_id`, `name`, `description`, `template_type`, `tags`
- ✅ TemplateRef serializes correctly for Pydantic contexts

### 3. GroupPlanningContext (Phase 2)
- ✅ Accepts `List[TemplateRef]` (not `list[str]`)
- ✅ Context validation passes with real fixtures
- ✅ All required fields present

### 4. Prompt Rendering (Phase 2)
- ✅ System prompt renders successfully
- ✅ User prompt renders with template metadata
- ✅ Template names/types/tags appear in prompts (Phase 2 integration confirmed)

### 5. Demo Script Integration (Phase 2)
- ✅ `scripts/demo_sequencer_pipeline.py` updated to use TemplateRef
- ✅ Orchestrator loads templates from registry automatically
- ✅ Syntax validation passes

---

## E2E Test Instructions

### Prerequisites

1. **OpenAI API Key**:
   ```bash
   export OPENAI_API_KEY='your-key-here'
   ```

2. **Audio File**:
   - Default: `data/music/Need A Favor.mp3`
   - Or provide your own: `uv run python scripts/demo_sequencer_pipeline.py path/to/audio.mp3`

### Run Full Pipeline

```bash
# Full pipeline: Audio → AudioProfile → Lyrics → MacroPlanner → GroupPlanner
uv run python scripts/demo_sequencer_pipeline.py

# Or with custom audio
uv run python scripts/demo_sequencer_pipeline.py data/music/MyChristmasSong.mp3

# Skip cache (force reanalysis)
uv run python scripts/demo_sequencer_pipeline.py --no-cache

# Custom output directory
uv run python scripts/demo_sequencer_pipeline.py --output-dir my_test_run
```

### Expected Outputs

The script saves artifacts to `artifacts/demo_sequencer_pipeline_{TIMESTAMP}/`:

**Audio Analysis:**
- `song_bundle.json` - Raw audio features
- `audio_profile.json` - AudioProfile agent output
- `lyric_context.json` - Lyrics agent output (if lyrics found)

**Strategic Planning:**
- `macro_plan.json` - MacroPlanner output
- `macro_plan_audit.json` - Iteration metadata (score, iterations, verdicts)

**GroupPlanner:**
- `group_plan_set.json` - **GroupPlan for all display groups** ✨
- Individual group plans with:
  - Section-by-section choreography
  - Template selections (from Phase 1 templates!)
  - Layer assignments
  - Asset requests (if any)

---

## Validation Checklist

After running the E2E test, validate:

### ✅ GroupPlan Structure
- [ ] `group_plan_set.json` exists
- [ ] Contains `group_plans` array
- [ ] Each GroupPlan has:
  - `group_id`
  - `section_plans` (one per audio section)
  - `asset_requests` (if applicable)
  - `compilation_hints`

### ✅ Template Selection
- [ ] `template_id` values match Phase 1 template IDs
  - Expected: `gtpl_scene_cozy_village_bg`, `gtpl_tree_polar_radial_burst`, etc.
  - NOT: Random/hallucinated template names
- [ ] Templates make sense for section energy/mood

### ✅ Phase 2 Integration
- [ ] Template metadata (names, types, tags) influenced agent selection
- [ ] Check LLM logs (if enabled) to see template descriptions in prompts

### ✅ Iteration Loop
- [ ] `macro_plan_audit.json` shows iterations
- [ ] Judge scores present (0-10 scale)
- [ ] Iteration stopped at approval threshold or max iterations

### ✅ Checkpoints (if configured)
- [ ] `checkpoints/plans/` directory created
- [ ] `{project_name}_raw.json` - Last planner output
- [ ] `{project_name}_evaluation.json` - Last judge evaluation
- [ ] `{project_name}_final.json` - Final approved plan

---

## Known Limitations (v1)

1. **No Asset Generation**: AssetGenerator not yet implemented
   - Asset requests are created but not fulfilled
   - Assets resolved to fallback/builtin

2. **No Rendering**: SequenceAssembler not yet implemented
   - GroupPlan is end-of-pipeline for Phase 1
   - Cannot generate .xsq files yet

3. **Sequential Execution**: Groups planned one at a time
   - Parallel execution (Phase 2 improvement) not yet implemented

---

## Success Criteria

**Phase 3 passes if:**

1. ✅ Demo script runs without errors
2. ✅ `group_plan_set.json` is generated
3. ✅ GroupPlans reference valid templates from Phase 1 registry
4. ✅ Template metadata appears in prompts (Phase 2 integration)
5. ✅ Judge-based refinement loop executes
6. ✅ Output validates against Pydantic schemas

---

## Troubleshooting

### Issue: Template IDs not recognized

**Symptom**: Heuristic validator errors about unknown template IDs

**Fix**: Ensure bootstrap templates are imported:
```python
from twinklr.core.sequencer.templates.group_templates import bootstrap_traditional
```

This triggers `@register_template` decorators.

### Issue: Prompt rendering fails

**Symptom**: Jinja2 errors about undefined variables

**Fix**: Check that `available_templates` is `List[TemplateRef]`, not `list[str]`.

### Issue: LLM hallucinates template names

**Symptom**: GroupPlan contains template IDs like "christmas_sparkle" that don't exist

**Possible causes:**
1. Templates not showing in prompt (check Phase 2 integration)
2. LLM ignoring context (check prompt clarity)
3. Judge not catching invalid templates (check heuristic validator)

---

## Next Steps (After Phase 3)

Once E2E testing validates the agent works:

1. **Asset Pipeline** (Phase 2A in roadmap)
   - AssetGenerator implementation
   - AssetIndexer implementation

2. **Sequence Assembly** (Phase 2B in roadmap)
   - SequenceAssembler/IRComposer
   - Convert GroupPlanSet → SequenceIR

3. **Rendering** (Phase 2C in roadmap)
   - Renderer framework
   - DefaultHandler
   - XSQ export

---

**Status:** Phase 3 ready for manual E2E validation with real OpenAI API key.

**Dependencies:**
- Phase 1: Template Framework ✅ Complete
- Phase 2: Agent Integration ✅ Complete
- OpenAI API Key: Required for E2E
- Audio file: `data/music/Need A Favor.mp3` or custom

**Output:** Validated GroupPlans using Phase 1 templates via Phase 2 integration.
