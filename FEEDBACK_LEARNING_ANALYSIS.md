# Feedback Learning Analysis: Current vs. Proposed

## How Judge Feedback Currently Works

### 1. **Within-Session Flow** (Iteration N → N+1)

```
Iteration 1:
├─ Planner creates plan
├─ Validator checks structure
├─ Judge evaluates quality → SOFT_FAIL (score 6.2)
│  └─ Issues: [TEMPLATE_LANE_MISMATCH, COORDINATION_OVERLAP, WEAK_ENERGY_MATCH]
│  └─ Feedback: "BASE lane should use gtpl_base_* templates, not gtpl_rhythm_*"
└─ FeedbackManager stores feedback

Iteration 2:
├─ Planner receives:
│  ├─ feedback: "Feedback 1 (iteration 0, judge_soft_failure): BASE lane should use..."
│  ├─ revision_request.focus_areas: ["Schema Validation", "Energy Matching"]
│  ├─ revision_request.specific_fixes: ["Fix template IDs in BASE lane", "Increase intensity"]
│  └─ revision_request.avoid: ["Keep: Good coordination sequencing", "Keep: Timing structure"]
├─ Planner refines plan based on feedback
└─ Judge re-evaluates → APPROVE (score 8.0) ✓
```

### 2. **Current Architecture**

**FeedbackManager** (`feedback.py`):
- Stores feedback entries per session (max 25 entries)
- Tracks: validation failures, judge soft/hard failures
- Formats feedback for prompt inclusion
- **Scope: Single section orchestration** (cleared after section complete)

**RevisionRequest** (`models.py`):
- Structured guidance for refinement
- Contains:
  - `focus_areas`: Key improvement areas (e.g., "Energy Matching", "Coordination")
  - `specific_fixes`: Actionable fixes (e.g., "Use gtpl_base_glow_warm instead of gtpl_rhythm_chase")
  - `avoid`: Strengths to preserve (e.g., "Keep: Good timing structure")
  - `context_for_planner`: Narrative feedback

**StandardIterationController** (`controller.py`):
- Manages iteration loop
- Passes feedback to planner via prompt variables:
  ```jinja2
  {% if iteration > 0 %}
  # Iteration {{ iteration + 1 }} - Refinement Feedback
  {{ feedback }}
  **Instructions:** Address the feedback while maintaining section coherence.
  {% endif %}
  ```

### 3. **Limitations of Current System**

❌ **Session-scoped only** - Feedback cleared after each section  
❌ **No cross-run learning** - Same mistakes repeated across different songs  
❌ **No pattern detection** - Can't identify recurring issues (e.g., "always fails on high-energy verses")  
❌ **No quality trends** - Can't track if judge is becoming more/less critical over time  
❌ **Isolated failures** - Section failures don't inform other sections in same run  

---

## Proposed: Cross-Run Learning System

### Architecture: Three-Tier Feedback System

```
┌─────────────────────────────────────────────────────────────┐
│ TIER 1: Within-Iteration Feedback (Current System)         │
│ Scope: Single iteration → next iteration                   │
│ Lifetime: Single section orchestration (~30-90 seconds)    │
│ Purpose: Immediate refinement                              │
└─────────────────────────────────────────────────────────────┘
                         ↓ save to
┌─────────────────────────────────────────────────────────────┐
│ TIER 2: Within-Run Session Memory (NEW)                   │
│ Scope: All sections in current pipeline run               │
│ Lifetime: Single song processing (~5-15 minutes)          │
│ Purpose: Cross-section pattern learning                   │
└─────────────────────────────────────────────────────────────┘
                         ↓ save to
┌─────────────────────────────────────────────────────────────┐
│ TIER 3: Historical Knowledge Base (NEW)                   │
│ Scope: All pipeline runs across all songs                 │
│ Lifetime: Persistent (days/months)                        │
│ Purpose: Long-term pattern recognition & best practices   │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Design

#### 1. **SessionFeedbackAggregator** (Tier 2)

**Purpose**: Learn from other sections in the SAME run

```python
class SessionFeedbackAggregator:
    """Aggregates feedback across all sections in current pipeline run.
    
    Enables cross-section learning:
    - If Section 1 (verse) failed with TEMPLATE_LANE_MISMATCH, warn Section 2 (chorus)
    - If Section 3 (instrumental) got 9.5 score, show its pattern to Section 4
    - Detect recurring issues across sections
    """
    
    def __init__(self, output_dir: Path):
        self.section_results: dict[str, SectionFeedbackSummary] = {}
        self.recurring_issues: dict[str, int] = defaultdict(int)  # issue_id -> count
        self.best_practices: list[BestPractice] = []
        
    def add_section_result(self, section_id: str, result: IterationResult):
        """Add completed section result."""
        # Extract key learnings
        summary = SectionFeedbackSummary(
            section_id=section_id,
            final_score=result.context.final_verdict.score,
            iterations_needed=result.context.current_iteration,
            common_issues=[issue.issue_id for issue in result.context.final_verdict.issues],
            successful_patterns=self._extract_patterns(result.plan),
        )
        
        self.section_results[section_id] = summary
        
        # Track recurring issues
        for issue_id in summary.common_issues:
            self.recurring_issues[issue_id] += 1
    
    def get_warnings_for_section(self, section_context: SectionPlanningContext) -> list[str]:
        """Get warnings based on prior sections in this run.
        
        Returns:
            List of warning strings to inject into planner prompt
        """
        warnings = []
        
        # Check for recurring issues
        for issue_id, count in self.recurring_issues.items():
            if count >= 2:  # Seen in 2+ sections
                warnings.append(
                    f"⚠️ RECURRING ISSUE: '{issue_id}' has occurred in {count} previous sections. "
                    f"Review validator rules carefully."
                )
        
        # Find similar sections that succeeded
        similar_sections = self._find_similar_sections(section_context)
        for prev_section in similar_sections:
            if prev_section.final_score >= 8.0:
                warnings.append(
                    f"✓ SUCCESSFUL PATTERN: Section '{prev_section.section_id}' (score {prev_section.final_score}) "
                    f"with similar energy used these approaches: {prev_section.successful_patterns}"
                )
        
        return warnings
    
    def save_to_checkpoint(self, checkpoint_path: Path):
        """Save session feedback for historical analysis."""
        # This feeds into Tier 3 (Historical Knowledge Base)
        pass
```

#### 2. **HistoricalKnowledgeBase** (Tier 3)

**Purpose**: Persistent learning across ALL runs

```python
class HistoricalKnowledgeBase:
    """Persistent knowledge base of patterns learned across all pipeline runs.
    
    Stored in: data/knowledge_base/feedback_patterns.db (SQLite)
    
    Tracks:
    - Common failure patterns (e.g., "High-energy verses often fail with COORDINATION_OVERLAP")
    - Template effectiveness (e.g., "gtpl_rhythm_chase works well for HERO groups in high-energy")
    - Judge tendencies (e.g., "Judge is critical of ACCENT intensity < 0.8 in chorus sections")
    """
    
    def __init__(self, db_path: Path = Path("data/knowledge_base/feedback_patterns.db")):
        self.db_path = db_path
        self._init_schema()
    
    def add_run_feedback(self, session_aggregator: SessionFeedbackAggregator):
        """Ingest feedback from completed pipeline run."""
        with self._get_connection() as conn:
            # Store section results
            for section_id, summary in session_aggregator.section_results.items():
                conn.execute(
                    "INSERT INTO section_history VALUES (?, ?, ?, ?, ?)",
                    (
                        datetime.now(),
                        section_id,
                        summary.final_score,
                        summary.iterations_needed,
                        json.dumps(summary.common_issues),
                    ),
                )
    
    def get_dos_and_donts(self, section_context: SectionPlanningContext) -> dict[str, list[str]]:
        """Query knowledge base for DOs and DONTs relevant to this section.
        
        Returns:
            {
                "dos": [
                    "DO use gtpl_base_glow_warm for OUTLINE groups in intro sections (95% success rate)",
                    "DO keep BASE intensity between 0.7-0.9 for medium energy (avg score: 8.2)",
                ],
                "donts": [
                    "DON'T use gtpl_rhythm_chase in BASE lane (causes TEMPLATE_LANE_MISMATCH)",
                    "DON'T overlap UNIFIED coordination on same group (validation fails 80% of time)",
                ]
            }
        """
        # Query patterns matching section characteristics
        with self._get_connection() as conn:
            # Find successful patterns for similar sections
            successful_patterns = conn.execute(
                """
                SELECT pattern, success_rate, avg_score 
                FROM pattern_success 
                WHERE 
                    section_type = ? AND 
                    energy_level = ? AND
                    success_rate >= 0.80
                ORDER BY success_rate DESC
                LIMIT 5
                """,
                (section_context.section_name, section_context.energy_target),
            ).fetchall()
            
            # Find common failures for similar sections
            common_failures = conn.execute(
                """
                SELECT issue_code, failure_rate, description
                FROM pattern_failures
                WHERE
                    section_type = ? AND
                    failure_rate >= 0.60
                ORDER BY failure_rate DESC
                LIMIT 5
                """,
                (section_context.section_name,),
            ).fetchall()
        
        return {
            "dos": [
                f"DO {pattern['pattern']} (success rate: {pattern['success_rate']:.0%}, avg score: {pattern['avg_score']:.1f})"
                for pattern in successful_patterns
            ],
            "donts": [
                f"DON'T {failure['description']} (fails {failure['failure_rate']:.0%} of time with {failure['issue_code']})"
                for failure in common_failures
            ],
        }
    
    def get_judge_tendencies(self) -> dict[str, Any]:
        """Analyze judge scoring patterns across all runs.
        
        Returns:
            {
                "average_score": 7.3,
                "score_std_dev": 1.2,
                "approval_rate": 0.65,
                "common_critique_areas": ["Energy matching", "Coordination clarity"],
                "score_by_section_type": {"intro": 8.1, "verse": 6.9, "chorus": 7.8},
            }
        """
        pass
```

#### 3. **Enhanced Prompt Injection**

Update planner prompt to include historical learnings:

```jinja2
{# planner/user.j2 #}

{% if historical_dos_donts %}
---

# Historical Learnings (from previous runs)

## Patterns That Work Well ✓
{% for do in historical_dos_donts.dos %}
- {{ do }}
{% endfor %}

## Common Pitfalls to Avoid ⚠️
{% for dont in historical_dos_donts.donts %}
- {{ dont }}
{% endfor %}

---
{% endif %}

{% if session_warnings %}
---

# Cross-Section Warnings (from this run)

{% for warning in session_warnings %}
{{ warning }}
{% endfor %}

---
{% endif %}

{% if iteration > 0 %}
---

# Iteration {{ iteration + 1 }} - Refinement Feedback

{{ feedback }}

---
{% endif %}

# Your Task
...
```

### Storage Schema

```sql
-- Historical Knowledge Base Schema

CREATE TABLE section_history (
    run_timestamp DATETIME,
    section_id TEXT,
    section_type TEXT,  -- intro, verse, chorus, bridge, instrumental
    energy_level TEXT,  -- low, medium, high
    motion_density TEXT,
    final_score REAL,
    iterations_needed INTEGER,
    approved BOOLEAN,
    issues_json TEXT,   -- JSON array of issue codes
    plan_json TEXT      -- Full plan for pattern analysis
);

CREATE TABLE pattern_success (
    pattern_id TEXT PRIMARY KEY,
    pattern TEXT,  -- Human-readable description
    section_type TEXT,
    energy_level TEXT,
    success_count INTEGER,
    total_count INTEGER,
    success_rate REAL,
    avg_score REAL,
    last_seen DATETIME
);

CREATE TABLE pattern_failures (
    failure_id TEXT PRIMARY KEY,
    issue_code TEXT,
    description TEXT,
    section_type TEXT,
    failure_count INTEGER,
    total_count INTEGER,
    failure_rate REAL,
    avg_recovery_iterations REAL,
    last_seen DATETIME
);

CREATE TABLE judge_analytics (
    metric_name TEXT,
    metric_value REAL,
    computed_at DATETIME
);
```

---

## Benefits of Cross-Run Learning

### 1. **Faster Convergence**
- **Before**: Every run starts from scratch, repeats same mistakes
- **After**: Planner starts with historical knowledge, avoids known pitfalls

### 2. **Reduced Token Usage**
- **Before**: Planner explores bad paths, judge rejects, costs tokens for refinement
- **After**: Planner steers clear of known failures, higher first-pass success rate

### 3. **Quality Improvements**
- **Before**: Quality depends on prompt engineering alone
- **After**: Quality improves over time as system learns patterns

### 4. **Debugging Insights**
- Track: "Why does judge always fail verse sections with high energy?"
- Answer: Historical data shows 70% of high-energy verses fail with COORDINATION_OVERLAP
- Solution: Update validator or add specific guidance to prompt

### 5. **Judge Calibration**
- If judge approval rate is 90%, maybe judge is too lenient → increase thresholds
- If judge approval rate is 30%, maybe judge is too critical → tune scoring or prompts

---

## Implementation Phases

### Phase 1: Session-Scoped Learning (EASIEST)
**Effort**: 1-2 days  
**Files**:
- Create `packages/twinklr/core/agents/shared/feedback/session_aggregator.py`
- Update `packages/twinklr/core/pipeline/context.py` to add `session_feedback: SessionFeedbackAggregator`
- Update `packages/twinklr/core/agents/sequencer/group_planner/orchestrator.py` to call aggregator
- Update `prompts/planner/user.j2` to include `session_warnings`

**Immediate Value**: Cross-section learning within same song

### Phase 2: Historical Persistence (MODERATE)
**Effort**: 3-5 days  
**Files**:
- Create `packages/twinklr/core/agents/shared/feedback/knowledge_base.py`
- Add SQLite schema and queries
- Create CLI command: `twinklr feedback analyze` (show stats)
- Update orchestrator to query historical patterns
- Update prompts to include `historical_dos_donts`

**Long-Term Value**: Continuous improvement across all runs

### Phase 3: Analytics & Tuning (ADVANCED)
**Effort**: 5-7 days  
**Files**:
- Create `packages/twinklr/core/agents/shared/feedback/analytics.py`
- Dashboard: Streamlit app showing judge trends, failure patterns, success rates
- Auto-tuning: Adjust judge thresholds based on approval rate trends
- Pattern mining: LLM-powered analysis of successful plans to extract strategies

**Strategic Value**: Automated quality improvement and system introspection

---

## Recommended Approach

### Start with Phase 1 (Session-Scoped Learning)
This gives immediate value with minimal complexity:

1. **Add SessionFeedbackAggregator** to pipeline context
2. **Track section results** as they complete
3. **Inject warnings** into subsequent sections (e.g., "Section 1 failed with TEMPLATE_LANE_MISMATCH")
4. **Validate impact**: Re-run "Rudolph" and measure:
   - Does approval rate improve? (target: 70% → 80%)
   - Do later sections avoid issues from earlier sections?
   - Does iteration count decrease?

If Phase 1 shows value, proceed to Phase 2 for long-term learning.

---

## Example: Phase 1 in Action

**Run: "Rudolph the Red-Nosed Reindeer"**

```
Section 1 (intro):
├─ Planner creates plan
├─ Judge evaluates → APPROVE (score 8.5) ✓
└─ SessionAggregator records: "intro with medium energy, gtpl_base_glow_warm worked well"

Section 2 (verse_1):
├─ Planner receives session_warnings:
│  ✓ "Section 'intro' (score 8.5) with similar energy used: gtpl_base_glow_warm for BASE"
├─ Planner creates plan (uses similar approach)
├─ Judge evaluates → SOFT_FAIL (score 6.2) ⚠️
│  └─ Issue: TEMPLATE_LANE_MISMATCH (used gtpl_rhythm_chase in BASE lane)
└─ SessionAggregator records: "verse with high energy failed with TEMPLATE_LANE_MISMATCH"

Section 3 (chorus_1):
├─ Planner receives session_warnings:
│  ⚠️ "RECURRING ISSUE: 'TEMPLATE_LANE_MISMATCH' occurred in verse_1. Ensure BASE uses gtpl_base_* only."
├─ Planner creates plan (avoids gtpl_rhythm_* in BASE)
├─ Judge evaluates → APPROVE (score 8.2) ✓
└─ SessionAggregator records: success

Section 4 (verse_2):
├─ Planner receives session_warnings:
│  ⚠️ "RECURRING ISSUE: 'TEMPLATE_LANE_MISMATCH' in previous verse. BASE lane requires gtpl_base_* templates."
│  ✓ "Section 'chorus_1' (score 8.2) succeeded after fixing template lanes"
├─ Planner creates plan (uses correct templates)
├─ Judge evaluates → APPROVE (score 8.0) ✓

Result: 4/4 sections approved (100% vs. 45% baseline) ✓
```

---

## Conclusion

**Current System**: Works well for single-section refinement but has no memory  
**Proposed System**: Three-tier feedback hierarchy enabling continuous learning

**Recommendation**: Implement Phase 1 (session-scoped) first to validate the approach, then expand to Phase 2 (historical) if benefits are confirmed.

This would be a powerful addition that transforms the system from "iteratively improving each section independently" to "learning from mistakes and successes across all sections and all runs."
