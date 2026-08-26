"""Manifest guards for the platform-specific Demucs optional extra."""

from pathlib import Path
import tomllib

from packaging.requirements import Requirement


def test_stems_extra_selects_demucs_on_arm64_and_excludes_intel_macos() -> None:
    """The two-marker contract keeps Intel macOS installable with an explicit fallback."""
    requirements = [
        Requirement(value)
        for value in tomllib.loads(Path("packages/twinklr/core/pyproject.toml").read_text())[
            "project"
        ]["optional-dependencies"]["stems"]
    ]
    arm = {
        "sys_platform": "darwin",
        "platform_machine": "arm64",
        "python_full_version": "3.13.15",
    }
    intel = {
        "sys_platform": "darwin",
        "platform_machine": "x86_64",
        "python_full_version": "3.13.15",
    }

    assert sum(requirement.marker.evaluate(arm) for requirement in requirements) == 1
    assert sum(requirement.marker.evaluate(intel) for requirement in requirements) == 0
    assert all(requirement.name == "demucs" for requirement in requirements)
    assert all(str(requirement.specifier) == "==4.1.0" for requirement in requirements)
