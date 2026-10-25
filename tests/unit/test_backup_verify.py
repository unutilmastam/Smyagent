"""Backup verification (M11): complete, truncated and damaged archives."""

from __future__ import annotations

import gzip
from pathlib import Path

from app.infrastructure.database.backup import latest_backup, verify

GOOD = b"""-- MySQL dump 10.13  Distrib 8.0.36
--
-- Host: localhost    Database: itcode_smyagent
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) NOT NULL
);
INSERT INTO `alembic_version` VALUES ('0014');
CREATE TABLE `companies` (
  `id` char(36) NOT NULL
);
INSERT INTO `companies` VALUES ('a');
-- Dump completed on 2026-10-25  3:17:01
"""


def _write(path: Path, data: bytes) -> Path:
    with gzip.open(path, "wb") as out:
        out.write(data)
    return path


def test_complete_dump_is_ok(tmp_path: Path) -> None:
    result = verify(_write(tmp_path / "db-20261025-031700.sql.gz", GOOD))
    assert result.ok and result.tables == ["alembic_version", "companies"]
    assert result.insert_statements == 2


def test_truncated_dump_is_rejected(tmp_path: Path) -> None:
    cut = GOOD.rsplit(b"-- Dump completed", 1)[0]
    result = verify(_write(tmp_path / "db-1.sql.gz", cut))
    assert not result.ok and "incomplete" in (result.problem or "")


def test_damaged_archive_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path / "db-2.sql.gz", GOOD * 50)
    data = path.read_bytes()
    path.write_bytes(data[: len(data) // 2])
    result = verify(path)
    assert not result.ok and "damaged" in (result.problem or "")


def test_not_a_dump_and_missing_alembic(tmp_path: Path) -> None:
    assert not verify(_write(tmp_path / "db-3.sql.gz", b"hello\n-- Dump completed\n")).ok
    no_alembic = GOOD.replace(b"`alembic_version`", b"`other`")
    assert "alembic_version" in (verify(_write(tmp_path / "db-4.sql.gz", no_alembic)).problem or "")


def test_latest_backup_picks_newest_name(tmp_path: Path) -> None:
    assert latest_backup(tmp_path) is None
    _write(tmp_path / "db-20261024-031700.sql.gz", GOOD)
    newest = _write(tmp_path / "db-20261025-031700.sql.gz", GOOD)
    assert latest_backup(tmp_path) == newest
