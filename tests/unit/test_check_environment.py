"""The hosting check script must run to completion with the stdlib only."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_environment.py"


def test_runs_offline_and_reports_all_sections() -> None:
    result = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--offline"],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for heading in ("1. System", "2. Python", "4. MySQL", "6. Cron", "8. Virtualenv", "Done"):
        assert heading in result.stdout
    assert "Checks with internal errors: 0" in result.stdout
    assert str(Path.home()) not in result.stdout or str(Path.home()) in ("/", "/root")
