"""Database backups for cPanel (CLAUDE.md §16.5): gzip'd mysqldump, kept outside the web root.

The password goes into a temporary option file (mode 600), never onto the command line
where `ps` could show it. cPanel database users lack the PROCESS privilege, hence
`--no-tablespaces`. The dump is streamed, so large databases stay off-memory.
"""

from __future__ import annotations

import gzip
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, func, inspect, select, table, text
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


# -- verification and restore drill (M11) -----------------------------------------

_CREATE = re.compile(rb"^CREATE TABLE `([^`]+)`")
_INSERT = re.compile(rb"^INSERT INTO `([^`]+)`")
_DB_NAME = re.compile(r"^[A-Za-z0-9_]{1,64}$")


@dataclass
class VerifyResult:
    path: Path
    ok: bool
    tables: list[str] = field(default_factory=list)
    insert_statements: int = 0
    size_bytes: int = 0
    problem: str | None = None


@dataclass
class DrillResult:
    ok: bool
    tables: int = 0
    rows: dict[str, int] = field(default_factory=dict)
    # table -> (rows in the backup copy, rows in the live database now)
    differences: dict[str, tuple[int, int]] = field(default_factory=dict)
    problem: str | None = None


def latest_backup(directory: Path) -> Path | None:
    files = sorted(directory.glob(f"{PREFIX}*.gz"), key=lambda p: p.name, reverse=True)
    return files[0] if files else None


def verify(path: Path) -> VerifyResult:
    """Read the whole archive: gzip intact, dump complete, tables present."""
    result = VerifyResult(path=path, ok=False, size_bytes=path.stat().st_size)
    try:
        if path.name.endswith(".sqlite.gz"):
            return _verify_sqlite(path, result)
        header = b""
        last = b""
        with gzip.open(path, "rb") as dump:
            for number, line in enumerate(dump):
                if number < 3:
                    header += line
                if _CREATE.match(line):
                    result.tables.append(_CREATE.match(line).group(1).decode())  # type: ignore[union-attr]
                elif _INSERT.match(line):
                    result.insert_statements += 1
                if line.strip():
                    last = line
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        result.problem = f"archive damaged: {type(exc).__name__}"
        return result
    if b"dump" not in header.lower():
        result.problem = "not a mysqldump file"
    elif not last.startswith(b"-- Dump completed"):
        result.problem = "dump is incomplete (no 'Dump completed' line)"
    elif "alembic_version" not in result.tables:
        result.problem = "alembic_version table missing"
    else:
        result.ok = True
    return result


def _verify_sqlite(path: Path, result: VerifyResult) -> VerifyResult:
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "check.db"
        with gzip.open(path, "rb") as src, copy.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        con = sqlite3.connect(copy)
        try:
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
            result.tables = [
                r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
            ]
        finally:
            con.close()
    if integrity != "ok":
        result.problem = f"integrity_check: {integrity}"
    elif "alembic_version" not in result.tables:
        result.problem = "alembic_version table missing"
    else:
        result.ok = True
    return result


def _counts(url: URL | str) -> dict[str, int]:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return {
                name: int(conn.execute(select(func.count()).select_from(table(name))).scalar() or 0)
                for name in inspect(conn).get_table_names()
            }
    finally:
        engine.dispose()


def restore_drill(
    url_text: str, path: Path, target_database: str, *, keep: bool = False
) -> DrillResult:
    """Restore `path` into an EMPTY scratch database and compare it with the live one.

    Never touches the live database. The scratch copy is emptied again afterwards
    (it holds personal data) unless `keep`.
    """
    live = make_url(url_text)
    checked = verify(path)
    if not checked.ok:
        return DrillResult(ok=False, problem=f"backup not valid: {checked.problem}")
    if live.get_backend_name() == "sqlite":
        return _drill_sqlite(live, path)
    if live.get_backend_name() != "mysql":
        return DrillResult(ok=False, problem=f"not implemented for {live.get_backend_name()}")
    if not _DB_NAME.match(target_database) or target_database == live.database:
        return DrillResult(ok=False, problem="target must be a different, existing database")
    target = live.set(database=target_database)
    try:
        if _counts(target):
            return DrillResult(ok=False, problem="target database is not empty")
    except Exception as exc:
        return DrillResult(ok=False, problem=f"cannot open target database: {type(exc).__name__}")
    client = shutil.which("mysql")
    if client is None:
        return DrillResult(ok=False, problem="mysql client not found")
    with tempfile.NamedTemporaryFile("w", suffix=".cnf", delete=False) as options:
        options.write(mysql_option_file(target))
    os.chmod(options.name, 0o600)
    try:
        argv = [
            client,
            f"--defaults-extra-file={options.name}",
            "--default-character-set=utf8mb4",
            target_database,
        ]
        with gzip.open(path, "rb") as dump, tempfile.TemporaryFile() as errors:
            with subprocess.Popen(argv, stdin=subprocess.PIPE, stderr=errors) as proc:  # noqa: S603
                assert proc.stdin is not None
                try:
                    shutil.copyfileobj(dump, proc.stdin)
                finally:
                    proc.stdin.close()
                code = proc.wait(timeout=DUMP_TIMEOUT_SECONDS)
            errors.seek(0)
            message = errors.read().decode(errors="replace").strip()[:300]
        if code != 0:
            return DrillResult(ok=False, problem=message or "mysql restore failed")
        restored = _counts(target)
        result = _compare(restored, _counts(live))
        if not keep:
            _empty(target, list(restored))
        return result
    finally:
        os.unlink(options.name)


def _drill_sqlite(live: URL, path: Path) -> DrillResult:
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "restored.db"
        with gzip.open(path, "rb") as src, copy.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        return _compare(_counts(f"sqlite:///{copy}"), _counts(live))


def _compare(restored: dict[str, int], live: dict[str, int]) -> DrillResult:
    differences = {
        name: (rows, live.get(name, -1))
        for name, rows in restored.items()
        if live.get(name) != rows
    }
    missing = sorted(set(live) - set(restored))
    problem = f"tables missing in backup: {', '.join(missing)}" if missing else None
    return DrillResult(
        ok=not missing and "alembic_version" in restored,
        tables=len(restored),
        rows=restored,
        differences=differences,
        problem=problem,
    )


def _empty(target: URL, tables: list[str]) -> None:
    engine = create_engine(target)
    try:
        with engine.begin() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            quote = conn.dialect.identifier_preparer.quote
            for name in tables:
                conn.execute(text("DROP TABLE IF EXISTS " + quote(name)))
            conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    finally:
        engine.dispose()
