"""Restore drill (M11): a backup restored into a scratch database and compared."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.infrastructure.database import Database
from app.infrastructure.database.backup import backup, restore_drill, verify
from app.infrastructure.repositories.companies import CompanyRepository, NewCompany


def _seed(db: Database, name: str = "Lazzat") -> None:
    with db.transaction() as s:
        CompanyRepository(s).add(NewCompany(name=name, country="UZ"))


def test_drill_restores_and_compares(db: Database, database_url: str, tmp_path: Path) -> None:
    backend = make_url(database_url).get_backend_name()
    if backend == "mysql" and (shutil.which("mysqldump") is None or shutil.which("mysql") is None):
        pytest.skip("mysql client tools not installed")
    _seed(db)
    path = backup(database_url, tmp_path)
    assert path is not None and verify(path).ok
    scratch = f"smy_drill_{uuid.uuid4().hex[:8]}"
    if backend == "mysql":
        with create_engine(database_url).begin() as conn:
            conn.execute(text(f"CREATE DATABASE {scratch} CHARACTER SET utf8mb4"))
    try:
        result = restore_drill(database_url, path, scratch)
        assert result.ok, result.problem
        assert result.rows["companies"] == 1 and result.differences == {}
        # Data added after the backup shows as a difference, not a failure.
        _seed(db, "Denov Mebel")
        later = restore_drill(database_url, path, scratch)
        assert later.ok and later.differences["companies"] == (1, 2)
        if backend == "mysql":  # the scratch copy is emptied again
            target = make_url(database_url).set(database=scratch)
            assert inspect(create_engine(target)).get_table_names() == []
            refused = restore_drill(database_url, path, make_url(database_url).database or "")
            assert not refused.ok and "different" in (refused.problem or "")
    finally:
        if backend == "mysql":
            with create_engine(database_url).begin() as conn:
                conn.execute(text(f"DROP DATABASE IF EXISTS {scratch}"))


def test_drill_refuses_invalid_backup(database_url: str, tmp_path: Path) -> None:
    bad = tmp_path / "db-x.sql.gz"
    bad.write_bytes(b"not gzip")
    result = restore_drill(database_url, bad, "smy_whatever")
    assert not result.ok and "not valid" in (result.problem or "")
