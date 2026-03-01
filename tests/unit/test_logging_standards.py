"""Tests for logging standardization — CQ-11."""

import ast
from pathlib import Path

CORE_ROOT = Path("packages/twinklr/core")

# Files where print() is intentional (logger flush to stdout — correct behavior).
# These are the structured logger implementations that write to stdout when no
# output file is configured. print() IS the correct tool here, not the logging
# module, because these classes ARE the logging layer.
_ALLOWED_PRINT_FILES = {
    "logging/json_logger.py",
    "logging/yaml_logger.py",
}

# CLI entry-points and scripts are also permitted to use print().
_ALLOWED_PREFIXES = ("cli/", "scripts/")


class TestNoPrintInCore:
    def test_no_print_calls(self):
        """Core packages should use logging, not print().

        Exceptions:
        - cli/ and scripts/ directories (intentional user-facing output)
        - logging/json_logger.py and logging/yaml_logger.py (flush to stdout —
          these ARE the structured logger implementations)
        """
        violations: list[str] = []
        for py_file in sorted(CORE_ROOT.rglob("*.py")):
            rel = str(py_file.relative_to(CORE_ROOT))
            # Skip __pycache__
            if "__pycache__" in rel:
                continue
            # Skip CLI and scripts (allowed to use print)
            if any(rel.startswith(prefix) for prefix in _ALLOWED_PREFIXES):
                continue
            # Skip allowed files (structured logger flush methods)
            if rel in _ALLOWED_PRINT_FILES:
                continue
            try:
                tree = ast.parse(py_file.read_text())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "print"
                ):
                    violations.append(f"{py_file}:{node.lineno}")

        assert not violations, f"print() found in core (use logging instead): {violations}"


class TestLoggingPattern:
    def test_modules_use_getlogger(self):
        """Modules that use logging should use getLogger(__name__) or get_logger(__name__)."""
        for mod_path in [
            "feature_engineering/pipeline.py",
            "feature_store/backends/sqlite.py",
            "audio/metadata/pipeline.py",
            "audio/metadata/fingerprint.py",
            "audio/cache_adapter.py",
            "pipeline/executor.py",
        ]:
            full = CORE_ROOT / mod_path
            if not full.exists():
                continue
            content = full.read_text()
            if "logger" in content.lower() or "logging" in content:
                assert "getLogger(__name__)" in content or "get_logger(__name__)" in content, (
                    f"{mod_path}: uses logging but missing getLogger(__name__) "
                    f"or get_logger(__name__)"
                )

    def test_no_bare_import_logging_without_logger(self):
        """Files that import logging should define a module-level logger."""
        for py_file in sorted(CORE_ROOT.rglob("*.py")):
            rel = str(py_file.relative_to(CORE_ROOT))
            if "__pycache__" in rel:
                continue
            content = py_file.read_text()
            # Only check files that import the stdlib logging module
            if "import logging\n" not in content and "import logging\r" not in content:
                continue
            # They must define a logger
            has_logger = (
                "getLogger(__name__)" in content
                or "get_logger(__name__)" in content
                or "getLogger(" in content
            )
            assert has_logger, (
                f"{rel}: imports logging but does not define a logger via getLogger()"
            )
