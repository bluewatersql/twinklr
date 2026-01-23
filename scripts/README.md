# BlinkB0t Scripts

Utility scripts for development, testing, and analysis.

## Test Coverage Analysis

### `show_coverage_by_component.py`

Shows test coverage breakdown by major system component.

**Requirements**: Run tests with coverage first to generate `coverage.json`:

```bash
make test-cov  # or: uv run pytest --cov --cov-report=json
```

**Usage**:

```bash
# Show summary by component
make coverage
# or: uv run python scripts/show_coverage_by_component.py

# Show detailed breakdown with file-level stats
make coverage-detailed
# or: uv run python scripts/show_coverage_by_component.py --detailed

# Custom threshold (default: 65%)
uv run python scripts/show_coverage_by_component.py --threshold 80

# Custom coverage file location
uv run python scripts/show_coverage_by_component.py --coverage-file path/to/coverage.json
```

**Output**:

- Component-level coverage summary
- Overall project coverage
- List of components below threshold
- Worst-performing files per component

**Legend**:
- ✓ = >= 80% (Good coverage)
- ⚠ = 65-79% (Acceptable coverage)
- ✗ = < 65% (Needs improvement)

**Example**:

```
================================================================================
TEST COVERAGE BY COMPONENT
================================================================================

✓ config:  89.3% (532/596 lines, 8 files)
⚠ agents:  72.0% (1183/1642 lines, 13 files)
✗ audio:  25.5% (307/1202 lines, 22 files)
✗ api:  28.2% (77/273 lines, 2 files)

================================================================================
⚠ OVERALL:  72.7% (8620/11858 lines)
================================================================================
```

## Demo & Validation

### `demo.py`

Demo script for running the full pipeline.

```bash
uv run python scripts/demo.py
```

### `validation/`

Validation utilities for plans and XSQ files:

- `plan.py` - Validate agent-generated choreography plans
- `xsq.py` - Validate and inspect xLights XSQ files

```bash
uv run python scripts/validation/plan.py path/to/plan.json
uv run python scripts/validation/xsq.py path/to/sequence.xsq
```

## Development Tips

**Run coverage analysis after each test run**:

```bash
make test-cov && make coverage
```

**Focus on low-coverage components**:

```bash
make coverage-detailed | grep "✗"
```

**Track coverage over time**:

```bash
# Save baseline
make coverage > coverage_baseline.txt

# After changes, compare
make coverage > coverage_current.txt
diff coverage_baseline.txt coverage_current.txt
```
