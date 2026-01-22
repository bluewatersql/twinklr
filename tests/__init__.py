"""Test suite for blinkb0t.

This test suite follows a hybrid approach:
- Quick harvest of stable, architecture-independent tests (utils, timing)
- Fresh tests for new architecture (sequencer, templates, handlers)
- Old tests used as requirements documentation and reference

Test Structure:
- unit/: Unit tests for individual components
  - utils/: Utility function tests (harvested from .dev/tests)
  - timing/: BeatGrid and timing tests (adapted from .dev/tests)
  - sequencer/: New tests for core.sequencer
  - curves/: Curve generation and library tests
- integration/: Integration tests for component interactions
- fixtures/: Test data and fixture factories
- conftest.py: Shared fixtures and test configuration

See TEST_MIGRATION_ANALYSIS.md for migration strategy.
"""
