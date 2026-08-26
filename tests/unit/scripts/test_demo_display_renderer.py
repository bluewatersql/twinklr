from pathlib import Path
import subprocess
import sys


def test_demo_display_renderer_help_imports_current_models() -> None:
    repo_root = Path(__file__).resolve().parents[3]

    completed = subprocess.run(
        [sys.executable, "scripts/demo_display_renderer.py", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "usage:" in completed.stdout.lower()
