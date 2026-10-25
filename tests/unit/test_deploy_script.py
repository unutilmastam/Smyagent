"""scripts/deploy.sh must parse and pass shellcheck (it runs on the owner's server)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "deploy.sh"


def test_bash_syntax() -> None:
    assert subprocess.run(["bash", "-n", str(SCRIPT)], check=False).returncode == 0


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck not installed")
def test_shellcheck_clean() -> None:
    result = subprocess.run(
        ["shellcheck", str(SCRIPT)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout


def test_script_is_safe_to_rerun() -> None:
    text = SCRIPT.read_text()
    assert "set -euo pipefail" in text
    assert 'main "$@"' in text.splitlines()[-1]  # whole body parsed before `git pull` runs
    assert "--ff-only" in text and "db-backup" in text and "alembic upgrade head" in text
    assert "set -x" not in text  # never echo commands (secrets)
