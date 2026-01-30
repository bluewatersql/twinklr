# Twinklr Documentation Index

## Getting Started

- [README](../README.md) - Project overview and quick start
- [CLAUDE.md](../CLAUDE.md) - Development guide for AI assistants

## Template Authoring

### New in v1.0: Categorical Parameters System ⭐

- **[Template Authoring Guide: Categorical Parameters](TEMPLATE_AUTHORING_CATEGORICAL_PARAMS.md)** - Complete guide to using intensity levels and parameter overrides
- **[Quick Reference Card](CATEGORICAL_PARAMS_QUICK_REFERENCE.md)** - One-page reference for common patterns

The categorical parameter system provides:
- Automatic curve-specific optimization for movement intensity
- 5 intensity levels (SLOW, SMOOTH, FAST, DRAMATIC, INTENSE)
- Optional fine-tuning with parameter overrides
- 100% backward compatible with existing templates

**Start here**: [Quick Reference Card](CATEGORICAL_PARAMS_QUICK_REFERENCE.md) for a 5-minute introduction.

### Legacy Documentation

- [Checkpoints](checkpoints.md) - Agent checkpoint system

## Configuration

- [Configuration Overview](configs/README.md) - Configuration system documentation
- [Quick Reference](configs/QUICK_REFERENCE.md) - Common configuration patterns
- [App Config Example](configs/app_config.example.json) - Application settings
- [Job Config Example](configs/job_config.example.json) - Job execution settings
- [Fixture Config Example](configs/fixture_config.example.json) - Fixture definitions

## Development

### Architecture Documents

Located in `changes/vnext/`:

#### Agent System Rewrite
- [Agent Rewrite Overview](../changes/agent_rewrite/README.md) - Multi-agent system redesign
- [Implementation Checklist](../changes/agent_rewrite/IMPLEMENTATION_CHECKLIST.md) - Development progress

#### Curve Optimization System
- [Curve Movement Parameters](../changes/vnext/optimization/curve_movement_params/) - Categorical parameter design and implementation
  - [Design Document](../changes/vnext/optimization/curve_movement_params/DESIGN_AND_REMEDIATION.md)
  - [Implementation Checklist](../changes/vnext/optimization/curve_movement_params/IMPLEMENTATION_CHECKLIST.md)
  - [Phase 6 Progress](../changes/vnext/optimization/curve_movement_params/PHASE6_PROGRESS.md)
- [Curve Optimization Report](../changes/vnext/optimization/curve_optimization_phase5_fixed.md) - Parameter optimization results
- [Template Audit Report](../changes/vnext/optimization/TEMPLATE_AUDIT.md) - Built-in template analysis

### Testing

```bash
# Run all tests
make test

# Run specific test suites
uv run pytest tests/unit/           # Unit tests
uv run pytest tests/integration/    # Integration tests

# Run tests with coverage
make test-cov
```

### Quality Checks

```bash
# Run all quality checks
make validate

# Individual checks
make lint        # Ruff linting
make format      # Ruff formatting
make type-check  # MyPy type checking
```

## API Reference

### Core Modules

- **Audio Analysis**: `twinklr.core.audio.*`
  - Rhythm analysis (beats, tempo)
  - Energy profiling (multi-scale)
  - Structure detection (sections)
  - Harmonic analysis (chords, key)

- **Sequencing**: `twinklr.core.sequencer.*`
  - Template system
  - Movement library
  - Geometry handlers
  - Dimmer patterns

- **Agents**: `twinklr.core.agents.*`
  - Multi-agent orchestration
  - Plan generation
  - Quality evaluation
  - Iterative refinement

- **Curves**: `twinklr.core.curves.*`
  - Curve generators
  - Parameter adapters
  - Categorical parameters

## Project Structure

```
twinklr/
├── packages/twinklr/core/          # Core engine
│   ├── agents/                      # Multi-agent system
│   ├── audio/                       # Audio analysis
│   ├── curves/                      # Curve generation
│   ├── sequencer/                   # Sequencing engine
│   │   └── moving_heads/
│   │       ├── libraries/           # Movement, geometry, dimmer libraries
│   │       ├── templates/           # Template definitions
│   │       └── handlers/            # Effect handlers
│   └── formats/xlights/             # xLights file I/O
│
├── tests/                           # Test suite
│   ├── unit/                        # Unit tests
│   ├── integration/                 # Integration tests
│   └── fixtures/                    # Test fixtures
│
├── doc/                             # Documentation (you are here)
├── changes/                         # Architecture docs & ADRs
└── scripts/                         # Utility scripts
```

## Contributing

### Development Workflow

1. **Setup**: `make install`
2. **Make Changes**: Follow TDD (test-driven development)
3. **Validate**: `make validate` (linting, types, tests)
4. **Test**: `make test-cov` (with coverage report)
5. **Commit**: Write clear commit messages

### Code Standards

- **Python 3.12+** with type hints
- **Ruff** for linting/formatting (100 char line length)
- **MyPy** for type checking (strict mode)
- **TDD**: Write tests before implementation
- **Pydantic V2** for data validation
- **Test coverage**: Maintain 65%+ (strive for 80%)

## Changelog

### v1.0 (Current)

**New Features**:
- ✨ Categorical parameter system with curve-specific optimization
- ✨ 5 intensity levels (SLOW, SMOOTH, FAST, DRAMATIC, INTENSE)
- ✨ Optional parameter overrides for fine-tuning
- ✨ Comprehensive template authoring documentation

**Improvements**:
- 🎯 18 built-in templates validated with optimized parameters
- 🎯 Zero templates require overrides (excellent defaults)
- 🎯 100% backward compatible with existing templates

**Technical**:
- 📦 1321 tests passing
- 📦 64% code coverage
- 📦 0 linting errors
- 📦 0 type checking errors

## Support & Resources

- **Issues**: Report bugs and request features via GitHub Issues
- **Discussions**: Ask questions and share templates in GitHub Discussions
- **Documentation**: This directory (`doc/`)
- **Examples**: See `tests/fixtures/` and `packages/twinklr/core/sequencer/moving_heads/templates/builtins/`

## Quick Links

### Most Used Docs

1. [Categorical Parameters Quick Reference](CATEGORICAL_PARAMS_QUICK_REFERENCE.md) ⭐
2. [Template Authoring Guide](TEMPLATE_AUTHORING_CATEGORICAL_PARAMS.md)
3. [Configuration Quick Reference](configs/QUICK_REFERENCE.md)
4. [README](../README.md)

### For Template Authors

1. Start: [Quick Reference Card](CATEGORICAL_PARAMS_QUICK_REFERENCE.md)
2. Learn: [Template Authoring Guide](TEMPLATE_AUTHORING_CATEGORICAL_PARAMS.md)
3. Reference: [Template Audit Report](../changes/vnext/optimization/TEMPLATE_AUDIT.md)
4. Examples: [Built-in Templates](../packages/twinklr/core/sequencer/moving_heads/templates/builtins/)

### For Developers

1. Setup: [CLAUDE.md](../CLAUDE.md)
2. Architecture: [Agent Rewrite Docs](../changes/agent_rewrite/)
3. Testing: `make test`, `make test-cov`
4. Quality: `make validate`

---

**Last Updated**: 2026-01-26  
**Version**: 1.0  
**Status**: Production Ready
