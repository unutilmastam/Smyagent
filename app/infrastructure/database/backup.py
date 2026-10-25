"""Database backups for cPanel (CLAUDE.md §16.5): gzip'd mysqldump, kept outside the web root.

The password goes into a temporary option file (mode 600), never onto the command line
where `ps` could show it. cPanel database users lack the PROCESS privilege, hence
`--no-tablespaces`. The dump is streamed, so large databases stay off-memory.
"""

from __future__ import annotations

import gzip
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL, make_url

PREFIX = "db-"
DUMP_TIMEOUT_SECONDS = 600


class BackupError(RuntimeError):
    pass


def has_schema(url: str) -> bool:
    """True when the database already has tables (a deploy over existing data)."""
    engine = create_engine(url)
    try:
        return bool(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def mysql_option_file(url: URL) -> str:
    def quoted(value: str) -> str:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    lines = ["[client]", f"user={quoted(url.username or '')}"]
    if url.password:
        lines.append(f"password={quoted(str(url.password))}")
    lines.append(f"host={quoted(url.host or 'localhost')}")
    if url.port:
        lines.append(f"port={url.port}")
    return "\n".join(lines) + "\n"


def rotate(directory: Path, keep: int) -> list[Path]:
    files = sorted(directory.glob(f"{PREFIX}*.gz"), key=lambda p: p.name, reverse=True)
    removed = files[keep:]
    for path in removed:
        path.unlink()
    return removed


def _dump_mysql(url: URL, target: Path) -> None:
    dump = shutil.which("mysqldump")
    if dump is None:
        raise BackupError("mysqldump not found")
    with tempfile.NamedTemporaryFile("w", suffix=".cnf", delete=False) as options:
        options.write(mysql_option_file(url))
    os.chmod(options.name, 0o600)
    argv = [
        dump,
        f"--defaults-extra-file={options.name}",  # must be the first option
        "--single-transaction",
        "--no-tablespaces",
        "--default-character-set=utf8mb4",
        str(url.database),
    ]
    try:
        with gzip.open(target, "wb") as out, tempfile.TemporaryFile() as errors:
            with subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=errors) as proc:  # noqa: S603
                assert proc.stdout is not None
                shutil.copyfileobj(proc.stdout, out)
                code = proc.wait(timeout=DUMP_TIMEOUT_SECONDS)
            errors.seek(0)
            message = errors.read().decode(errors="replace").strip()[:300]
        if code != 0:
            target.unlink(missing_ok=True)
            raise BackupError(message or "mysqldump failed")
    finally:
        os.unlink(options.name)


def backup(
    url_text: str, directory: Path, *, keep: int = 14, now: datetime | None = None
) -> Path | None:
    """Write `db-<UTC time>.<ext>.gz`; None when there is nothing to back up yet."""
    url = make_url(url_text)
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    backend = url.get_backend_name()
    if backend == "sqlite":
        source = Path(url.database or "")
        if not url.database or not source.exists():
            return None
        target = directory / f"{PREFIX}{stamp}.sqlite.gz"
        with source.open("rb") as src, gzip.open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)
    elif backend == "mysql":
        if not has_schema(url_text):
            return None
        target = directory / f"{PREFIX}{stamp}.sql.gz"
        _dump_mysql(url, target)
    else:
        raise BackupError(f"backups are not implemented for {backend}")
    os.chmod(target, 0o600)
    rotate(directory, keep)
    return target
