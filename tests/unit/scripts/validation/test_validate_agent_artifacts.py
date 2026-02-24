from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_module():
    repo_root = Path(__file__).resolve().parents[4]
    module_path = repo_root / "scripts" / "validation" / "validate_agent_artifacts.py"
    spec = importlib.util.spec_from_file_location("validate_agent_artifacts", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_selected_checks_defaults_to_all_when_none_requested() -> None:
    module = _load_module()

    checks = module.selected_checks(run_schemas=False, run_prompts=False, run_all=False)

    assert checks == ("schemas", "prompts")


def test_selected_checks_honors_specific_flags() -> None:
    module = _load_module()

    checks = module.selected_checks(run_schemas=True, run_prompts=False, run_all=False)

    assert checks == ("schemas",)
