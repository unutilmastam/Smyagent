"""Database backups for cPanel: sqlite copy, mysqldump via an option file, rotation."""

from __future__ import annotations

import gzip
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from app.infrastructure.database import backup as backup_module
from app.infrastructure.database.backup import BackupError, backup, mysql_option_file

T0 = datetime(2026, 11, 1, 3, 17, tzinfo=timezone.utc)


def test_sqlite_backup_and_rotation(tmp_path: Path) -> None:
    db = tmp_path / "app.db"
    db.write_bytes(b"SQLite format 3\x00 data")
    out = tmp_path / "backups"
    paths = [backup(f"sqlite:///{db}", out, keep=3, now=T0 + timedelta(days=i)) for i in range(5)]
    assert all(p is not None for p in paths)
    remaining = sorted(p.name for p in out.iterdir())
    assert len(remaining) == 3 and remaining[-1] == "db-20261105-031700.sqlite.gz"
    assert gzip.decompress((out / remaining[-1]).read_bytes()) == db.read_bytes()
    assert stat.S_IMODE((out / remaining[-1]).stat().st_mode) == 0o600
    assert stat.S_IMODE(out.stat().st_mode) == 0o700


def test_nothing_to_back_up(tmp_path: Path) -> None:
    assert backup(f"sqlite:///{tmp_path / 'missing.db'}", tmp_path / "b") is None


def test_option_file_quotes_the_password() -> None:
    url = make_url("mysql+pymysql://cpu_smy:P%40ss%22q%5C@localhost:3306/db")
    text = mysql_option_file(url)
    assert 'password="P@ss\\"q\\\\"' in text and 'user="cpu_smy"' in text and "port=3306" in text


def _fake_mysqldump(tmp_path: Path, script: str) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tool = bin_dir / "mysqldump"
    tool.write_text("#!/usr/bin/env bash\n" + script)
    tool.chmod(0o755)
    return bin_dir


def test_mysql_dump_uses_option_file_never_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = _fake_mysqldump(
        tmp_path,
        'case "$1" in --defaults-extra-file=*) f="${1#*=}";; *) exit 9;; esac\n'
        '[ "$(stat -c %a "$f")" = 600 ] || exit 8\n'
        'grep -q "password=\\"s3cret\\"" "$f" || exit 7\n'
        'case "$*" in *s3cret*) exit 6;; esac\n'
        'echo "-- dump of ${@: -1}"\n',
    )
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(backup_module, "has_schema", lambda url: True)
    path = backup("mysql+pymysql://u:s3cret@localhost/cpu_db", tmp_path / "b", now=T0)
    assert path is not None and path.name == "db-20261101-031700.sql.gz"
    assert gzip.decompress(path.read_bytes()).decode().strip() == "-- dump of cpu_db"


def test_mysql_dump_failure_leaves_no_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = _fake_mysqldump(tmp_path, 'echo "Access denied" >&2; exit 2\n')
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(backup_module, "has_schema", lambda url: True)
    with pytest.raises(BackupError, match="Access denied"):
        backup("mysql+pymysql://u:p@localhost/db", tmp_path / "b", now=T0)
    assert list((tmp_path / "b").iterdir()) == []


def test_mysql_without_tables_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backup_module, "has_schema", lambda url: False)
    assert backup("mysql+pymysql://u:p@localhost/db", tmp_path / "b") is None
