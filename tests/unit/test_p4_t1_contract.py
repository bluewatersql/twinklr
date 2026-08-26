"""Repository contract for the coordinated P4-T1 platform bump."""

from pathlib import Path
import tomllib

import yaml

ROOT = Path(__file__).parents[2]


def _toml(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def test_workspace_packages_and_tooling_require_python_313() -> None:
    root = _toml(ROOT / "pyproject.toml")
    core = _toml(ROOT / "packages/twinklr/core/pyproject.toml")
    cli = _toml(ROOT / "packages/twinklr/cli/pyproject.toml")
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))

    assert root["project"]["requires-python"] == ">=3.13,<3.14"  # type: ignore[index]
    assert core["project"]["requires-python"] == ">=3.13,<3.14"  # type: ignore[index]
    assert cli["project"]["requires-python"] == ">=3.13,<3.14"  # type: ignore[index]
    assert root["tool"]["ruff"]["target-version"] == "py313"  # type: ignore[index]
    assert root["tool"]["mypy"]["python_version"] == "3.13"  # type: ignore[index]
    assert ci["jobs"]["quality-gates"]["steps"][1]["with"]["python-version"] == "3.13"


def test_uv_lock_targets_supported_deployment_platforms() -> None:
    root = _toml(ROOT / "pyproject.toml")
    lock = _toml(ROOT / "uv.lock")

    assert root["tool"]["uv"]["required-environments"] == [  # type: ignore[index]
        "sys_platform == 'darwin' and platform_machine == 'arm64'",
        "sys_platform == 'linux' and platform_machine == 'x86_64'",
    ]
    assert lock["requires-python"] == "==3.13.*"
    assert lock["required-markers"] == [
        "platform_machine == 'arm64' and sys_platform == 'darwin'",
        "platform_machine == 'x86_64' and sys_platform == 'linux'",
    ]


def test_lock_contains_the_resolved_ml_chain_without_removed_packages() -> None:
    lock = _toml(ROOT / "uv.lock")
    versions = {package["name"]: package["version"] for package in lock["package"]}  # type: ignore[index]
    expected = {
        "torch": "2.8.0",
        "torchaudio": "2.8.0",
        "torchvision": "0.23.0",
        "whisperx": "3.8.6",
        "pyannote-audio": "4.0.7",
        "torchcodec": "0.7.0",
        "ctranslate2": "4.8.1",
        "faster-whisper": "1.2.1",
        "transformers": "4.57.6",
        "triton": "3.4.0",
    }
    assert {name: versions[name] for name in expected} == expected
    assert "sqlite-vec" not in versions
    assert "bezier" not in versions


def test_ml_extra_has_exact_coordinated_direct_dependencies() -> None:
    root = _toml(ROOT / "pyproject.toml")
    core = _toml(ROOT / "packages/twinklr/core/pyproject.toml")
    root_extras = root["project"]["optional-dependencies"]  # type: ignore[index]
    extras = core["project"]["optional-dependencies"]  # type: ignore[index]

    assert root_extras["normalization"] == ["twinklr-core[normalization]>=0.1.0"]
    assert "fe" not in extras
    assert set(extras["ml"]) == {
        "whisperx==3.8.6",
        "torch==2.8.0",
        "torchaudio==2.8.0",
        "pyannote-audio>=4,<5",
    }
    assert all(
        not dependency.startswith("bezier") for dependency in core["project"]["dependencies"]
    )  # type: ignore[index]


def test_orphaned_diarization_surface_is_absent() -> None:
    config_source = (ROOT / "packages/twinklr/core/config/models.py").read_text(encoding="utf-8")
    lyrics_dir = ROOT / "packages/twinklr/core/audio/lyrics"

    assert "enable_diarization" not in config_source
    assert not (lyrics_dir / "diarization.py").exists()
    assert not (lyrics_dir / "diarization_models.py").exists()
