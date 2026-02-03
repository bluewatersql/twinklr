# Agent Learning System

## Overview

The Agent Learning System provides persistent issue tracking and cross-job learning for all judge agents. It automatically captures issues identified during evaluation, analyzes patterns across multiple jobs, and injects relevant learning context back into agent prompts to improve future evaluations.

**Key Features**:
- 📊 **Per-Agent Tracking**: Issues are attributed to specific judges (macro_planner_judge, section_judge, etc.)
- 💾 **Persistent Storage**: JSON-lines storage for efficient append and low-volume use cases
- 🔄 **Cross-Job Learning**: Agents learn from patterns across multiple job runs
- 🎯 **Generic Examples**: Issues can include abstract examples to avoid biasing future judgments
- 🔌 **Transparent by Default**: Enabled automatically, opt-out via configuration
- 🧠 **Automatic Injection**: Learning context injected into developer prompts, invisible to user prompts

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│ StandardIterationController                             │
│  - Creates IssueRepository (if enabled)                 │
│  - Passes to FeedbackManager                            │
│  - Injects learning context into developer prompts      │
└───────────────┬─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│ FeedbackManager                                         │
│  - Tracks issues per iteration                          │
│  - Automatically records to IssueRepository             │
│  - Tracks resolution (issue_id no longer present)       │
└───────────────┬─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│ IssueRepository                                         │
│  - Persistent JSON-lines storage                        │
│  - Per-agent files: {agent_name}_issues.jsonl          │
│  - Analytics: top issues, resolution rates, etc.        │
│  - Format learning context for developer prompts        │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Issue Generation**: Judge agent identifies issues in `JudgeVerdict`
2. **Recording**: `FeedbackManager` automatically records to `IssueRepository`
3. **Resolution Tracking**: Issues present in iteration N but not N+1 marked as resolved
4. **Analytics**: Repository aggregates issues by category, counts occurrences
5. **Context Injection**: Learning context injected into next job's developer prompts
6. **Transparent Learning**: Agents reference patterns without seeing specifics

## Configuration

### Default Behavior (Enabled)

By default, issue tracking is **enabled** with sensible defaults:

```python
from twinklr.core.agents.shared.judge.controller import (
    IterationConfig,
    StandardIterationController,
)

config = IterationConfig(
    max_iterations=3,
    # Issue tracking enabled by default
    enable_issue_tracking=True,  # ← Default
    issue_tracking_storage_dir="data/agent_analytics",  # ← Default
    include_historical_learning=True,  # ← Default
    top_n_historical_issues=5,  # ← Default
)

controller = StandardIterationController(
    config=config,
    job_id="my_job_123",  # Optional, auto-generated if omitted
)
```

### Opt-Out (Disable Tracking)

To disable issue tracking:

```python
config = IterationConfig(
    max_iterations=3,
    enable_issue_tracking=False,  # ← Disable tracking
)
```

### Advanced Configuration

```python
config = IterationConfig(
    max_iterations=3,
    
    # Issue tracking
    enable_issue_tracking=True,
    issue_tracking_storage_dir="/path/to/analytics",
    
    # Learning context injection
    include_historical_learning=True,  # Include in developer prompts
    top_n_historical_issues=10,  # Show top 10 (default: 5)
    
    # Feedback management
    max_feedback_entries=25,  # Keep last 25 entries
)
```

### JSON Config (Job Config)

```json
{
  "agent": {
    "max_iterations": 3,
    "issue_tracking": {
      "enabled": true,
      "storage_dir": "data/agent_analytics",
      "include_historical_learning": true,
      "top_n_historical_issues": 5
    }
  }
}
```

## Issue Model Enhancement

### Generic Examples Field

The `Issue` model includes an optional `generic_example` field for bias-free learning:

```python
from twinklr.core.agents.issues import Issue, IssueCategory, IssueSeverity

issue = Issue(
    issue_id="VARIETY_LOW_CHORUS",
    category=IssueCategory.VARIETY,
    severity=IssueSeverity.WARN,
    message="Chorus uses same template 3 times without variation",
    fix_hint="Use different geometry types or presets for variety",
    
    # Generic example (abstract pattern, no specifics)
    generic_example="Repeated template usage without variation in high-energy sections",
)
```

**Guidelines for Generic Examples**:
- ✅ **Good**: "Repeated template usage without variation in high-energy sections"
- ✅ **Good**: "Missing spatial contrast between verse and chorus"
- ✅ **Good**: "Low energy sections using high-intensity templates"
- ❌ **Bad**: "Section chorus_1 uses sweep_fan 3 times" (too specific)
- ❌ **Bad**: "Fixture group mega_tree overlaps in BASE lane" (too specific)

The goal is to capture the **pattern** without anchoring on specific plan details.

## Developer Prompt Integration

Learning context is automatically injected into `developer.j2` templates:

```jinja
## Technical Contract

### Response Schema

{{ response_schema }}

{% if learning_context %}
### Historical Learning Context

{{ learning_context }}

Use this context to be more vigilant about recurring patterns, but evaluate each plan on its own merits.

---
{% endif %}

### Evaluation Process
...
```

**Sample Output**:
```
### Historical Learning Context

# Historical Learning Context

Based on 47 recent issues across multiple jobs, common issues for macro_planner_judge:

**VARIETY** (occurred 12 times):
  - Example: Repeated template usage without variation in high-energy sections
  - Example: Insufficient contrast between adjacent sections

**MUSICALITY** (occurred 9 times):
  - Example: Energy mismatch between plan and audio profile

**LAYERING** (occurred 8 times):
  - Example: Unbalanced layer intensity distribution

**TIMING** (occurred 7 times):
  - Example: Section transitions not aligned with beat boundaries

**STYLE** (occurred 6 times):
  - Example: Inconsistent choreography style across song sections

Overall issue resolution rate: 68.1%

Use this context to be more vigilant about these recurring patterns, but evaluate each plan on its own merits.

---
```

## Storage Format

### File Organization

```
data/agent_analytics/
├── macro_planner_judge_issues.jsonl
├── section_judge_issues.jsonl
├── holistic_judge_issues.jsonl
└── ...
```

### JSON-Lines Format

Each line is a complete `IssueRecord`:

```json
{"issue":{"issue_id":"VARIETY_LOW_CHORUS","category":"VARIETY","severity":"WARN","estimated_effort":"LOW","scope":"SECTION","location":{"section_id":"chorus_1","bar_start":25,"bar_end":33},"message":"Chorus uses same template 3 times without variation","fix_hint":"Use different geometry types or presets for variety","acceptance_test":"Chorus sections use at least 2 different templates or presets","suggested_action":"PATCH","generic_example":"Repeated template usage without variation in high-energy sections"},"agent_name":"macro_planner_judge","job_id":"job_a3f4b2c1","iteration":1,"verdict_score":6.5,"timestamp":1706889600.0,"resolved":false}
```

**Benefits of JSON-Lines**:
- Efficient append (no need to parse entire file)
- Streaming reads (tail recent records)
- Human-readable with `jq` or similar tools
- Low overhead for low-volume use cases

## API Reference

### IssueRepository

```python
from pathlib import Path
from twinklr.core.agents.analytics import IssueRepository

# Initialize
repo = IssueRepository(
    storage_dir=Path("data/agent_analytics"),
    enabled=True,  # Set False to opt-out
)

# Record issues (automatic via FeedbackManager)
repo.record_issues(
    issues=[issue1, issue2],
    agent_name="macro_planner_judge",
    job_id="job_123",
    iteration=1,
    verdict_score=6.5,
    timestamp=time.time(),
    resolved_issue_ids={"OLD_ISSUE_1"},
)

# Get top issues
top_issues = repo.get_top_issues(
    agent_name="macro_planner_judge",
    top_n=10,
    min_occurrences=2,
    max_records=1000,  # Scan most recent 1000 records
)
# Returns: [(category, count, [generic_examples]), ...]

# Get recurring issues (by issue_id)
recurring = repo.get_recurring_issues(
    agent_name="macro_planner_judge",
    min_occurrences=3,
)
# Returns: [(issue_id, count, example_issue), ...]

# Get resolution rate
resolution_rate = repo.get_resolution_rate(
    agent_name="macro_planner_judge",
    category=IssueCategory.VARIETY,  # Optional filter
)
# Returns: 0.0-1.0

# Format learning context for developer prompt
learning_context = repo.format_learning_context(
    agent_name="macro_planner_judge",
    top_n=5,
    include_resolution_rate=True,
)
# Returns: Markdown-formatted string

# Get stats
stats = repo.get_stats(agent_name="macro_planner_judge")
# Returns: {
#   "total_issues": 150,
#   "unique_categories": 8,
#   "unique_severities": 3,
#   "resolution_rate": 0.681,
#   "most_common_category": "VARIETY"
# }
```

### FeedbackManager Integration

```python
from twinklr.core.agents.shared.judge.feedback import FeedbackManager

# Create with repository integration
feedback = FeedbackManager(
    max_entries=25,
    agent_name="macro_planner_judge",
    job_id="job_123",
    issue_repository=repo,  # Optional
)

# Add verdict (automatically records to repository if configured)
feedback.add_judge_verdict(verdict, iteration=1)

# Format with learning context
feedback_text = feedback.format_with_learning_context(
    include_historical=True,
    top_n_historical=5,
)
```

## Usage Examples

### Basic Usage (Default Enabled)

```python
from twinklr.core.agents.shared.judge.controller import (
    IterationConfig,
    StandardIterationController,
)

# Default config (tracking enabled)
config = IterationConfig(max_iterations=3)

# Controller automatically creates repository
controller = StandardIterationController(
    config=config,
    job_id="xmas_song_v1",
)

# Run iteration loop
result = await controller.run(
    planner_spec=planner_spec,
    judge_spec=judge_spec,
    initial_variables={"audio_profile": profile, ...},
    validator=validate_plan,
    provider=openai_provider,
    llm_logger=llm_logger,
)

# Issues automatically recorded to:
# data/agent_analytics/{judge_name}_issues.jsonl
```

### Disable Tracking

```python
config = IterationConfig(
    max_iterations=3,
    enable_issue_tracking=False,  # Opt-out
)

controller = StandardIterationController(config=config)
# No repository created, no issues recorded
```

### Custom Storage Path

```python
config = IterationConfig(
    max_iterations=3,
    issue_tracking_storage_dir="/mnt/analytics/twinklr",
)
```

### Query Analytics

```python
from twinklr.core.agents.analytics import IssueRepository

repo = IssueRepository(storage_dir="data/agent_analytics")

# Top issues for specific judge
top_issues = repo.get_top_issues("macro_planner_judge", top_n=10)
for category, count, examples in top_issues:
    print(f"{category.value}: {count} occurrences")
    for example in examples:
        print(f"  - {example}")

# Resolution rate
rate = repo.get_resolution_rate("macro_planner_judge")
print(f"Resolution rate: {rate:.1%}")

# Recurring issues
recurring = repo.get_recurring_issues("macro_planner_judge", min_occurrences=5)
for issue_id, count, issue in recurring:
    print(f"{issue_id}: {count} times - {issue.message}")
```

## Best Practices

### 1. Use Generic Examples

When creating issues, always provide a `generic_example` that captures the pattern:

```python
# ✅ Good
generic_example="Missing spatial contrast between verse and chorus"

# ❌ Bad (too specific)
generic_example="Fixture group mega_tree not used in verse_1"
```

### 2. Stable Issue IDs

Use stable, descriptive issue IDs that can be tracked across iterations:

```python
# ✅ Good
issue_id="VARIETY_LOW_CHORUS"
issue_id="TIMING_OVERLAP_BASE_LANE"

# ❌ Bad (not stable)
issue_id=f"issue_{random.randint(1000, 9999)}"
```

### 3. Monitor Resolution Rates

Periodically check resolution rates to identify persistent issues:

```python
repo = IssueRepository(storage_dir="data/agent_analytics")
rate = repo.get_resolution_rate("macro_planner_judge")

if rate < 0.5:
    # More than half of issues not resolved - investigate
    recurring = repo.get_recurring_issues("macro_planner_judge", min_occurrences=5)
    # Analyze recurring issues for systemic problems
```

### 4. Audit Learning Context

Before production use, audit the learning context being injected:

```python
learning_context = repo.format_learning_context("macro_planner_judge")
print(learning_context)
# Verify no overly specific details leak through
```

## Migration Guide

### Existing Code

If you have existing iteration controllers, they will **automatically** enable issue tracking with defaults. To preserve old behavior (no tracking):

```python
config = IterationConfig(
    max_iterations=3,
    enable_issue_tracking=False,  # Preserve old behavior
)
```

### Custom Controllers

If you have custom controllers not using `StandardIterationController`, integrate as follows:

```python
from twinklr.core.agents.analytics import IssueRepository
from twinklr.core.agents.shared.judge.feedback import FeedbackManager

# 1. Create repository
repo = IssueRepository(
    storage_dir="data/agent_analytics",
    enabled=True,
)

# 2. Create feedback manager with repository
feedback = FeedbackManager(
    max_entries=25,
    agent_name="my_judge",
    job_id="job_123",
    issue_repository=repo,
)

# 3. Add verdicts (automatic recording)
feedback.add_judge_verdict(verdict, iteration=1)

# 4. Inject learning context into developer variables
learning_context = repo.format_learning_context("my_judge", top_n=5)
developer_vars = {"learning_context": learning_context, ...}
```

## Troubleshooting

### Issue: Learning context not appearing in prompts

**Check**:
1. `config.include_historical_learning == True`
2. Developer template has `{% if learning_context %}` block
3. Repository has sufficient data (min_occurrences threshold)
4. Agent name matches between controller and repository

### Issue: Duplicate issues being recorded

**Cause**: Issue IDs are not stable across iterations.

**Fix**: Use consistent, descriptive issue IDs:
```python
# ✅ Stable
issue_id="TIMING_OVERLAP_BASE_LANE"

# ❌ Unstable
issue_id=f"timing_issue_{timestamp}"
```

### Issue: Storage directory not created

**Check**: Permissions and parent directory existence. Repository auto-creates directory if `enabled=True`.

### Issue: Resolution rate always 0%

**Cause**: Issue IDs changing between iterations, so resolution tracking fails.

**Fix**: Ensure issue IDs are stable and deterministic based on issue type/location.

## Performance Considerations

### File Size Management

JSON-lines files grow linearly with issue count. For high-volume scenarios:

```python
# Limit scan to recent records
top_issues = repo.get_top_issues(
    agent_name="macro_planner_judge",
    max_records=1000,  # Only scan most recent 1000
)
```

### Query Performance

- `get_top_issues()`: O(N) where N = max_records (default 1000)
- `get_recurring_issues()`: O(N) where N = max_records (default 500)
- `get_resolution_rate()`: O(N) where N = max_records (default 500)

For very large files (>10,000 records), consider periodic archival:
```bash
# Archive old records (keep recent 5000)
tail -n 5000 macro_planner_judge_issues.jsonl > macro_planner_judge_issues.jsonl.tmp
mv macro_planner_judge_issues.jsonl.tmp macro_planner_judge_issues.jsonl
```

## Future Enhancements

Potential future improvements:

1. **SQLite Backend**: For complex queries and larger volumes
2. **Time-Based Decay**: Weight recent issues higher than old ones
3. **Cross-Agent Analysis**: Identify issues that span multiple agents
4. **Automatic Prompt Tuning**: Adjust prompts based on persistent issues
5. **Issue Clustering**: Group similar issues for better pattern detection
6. **A/B Testing**: Compare resolution rates before/after prompt changes

## Summary

The Agent Learning System provides:
- ✅ Transparent, automatic issue tracking (opt-out to disable)
- ✅ Per-agent attribution for targeted learning
- ✅ Cross-job learning via persistent storage
- ✅ Generic examples to avoid bias
- ✅ Automatic injection into developer prompts
- ✅ Minimal configuration required
- ✅ Low overhead for low-volume use cases

Enable richer agent learning with zero code changes - just run your existing controllers!
