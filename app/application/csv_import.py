"""CSV import of companies (M4). Every row goes through the same intake as manual entry.

Accepted: UTF-8 (with or without BOM) or Windows-1251 (Excel in RU locale);
delimiter `,`, `;` or tab (auto-detected); headers in English, Uzbek or Russian.
Multiple values in one cell (e.g. two phones) are separated by `|`.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.application.discovery import DiscoveryService, IntakeResult, IntakeStatus
from app.domain.actors import Actor
from app.domain.errors import DomainError
from app.infrastructure.repositories.companies import NewCompany
from app.infrastructure.repositories.workflow import AuditLogRepository

MAX_BYTES = 1024 * 1024
MAX_ROWS = 2000

# canonical field -> accepted header spellings (compared lowercased, stripped)
HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("name", "company", "nomi", "kompaniya", "название", "компания"),
    "country": ("country", "davlat", "mamlakat", "страна"),
    "city": ("city", "shahar", "город"),
    "industry": ("industry", "soha", "отрасль", "сфера"),
    "domain": ("domain", "website", "site", "domen", "sayt", "сайт", "домен"),
    "phone": ("phone", "telefon", "телефон"),
    "email": ("email", "e-mail", "pochta", "почта"),
    "telegram": ("telegram", "телеграм"),
    "source_url": ("source_url", "source", "manba", "источник"),
    "notes": ("notes", "note", "izoh", "примечание", "заметки"),
}
REQUIRED = ("name", "country")


class CsvFormatError(DomainError):
    pass


@dataclass(frozen=True)
class RowResult:
    row: int  # 1-based line number in the file (header = 1)
    name: str
    result: IntakeResult


@dataclass
class ImportReport:
    filename: str
    dry_run: bool
    rows: list[RowResult] = field(default_factory=list)

    def count(self, status: IntakeStatus) -> int:
        return sum(1 for r in self.rows if r.result.status is status)

    @property
    def created(self) -> int:
        return self.count(IntakeStatus.CREATED)

    @property
    def duplicates(self) -> int:
        return self.count(IntakeStatus.DUPLICATE)

    @property
    def invalid(self) -> int:
        return self.count(IntakeStatus.INVALID)


def decode(data: bytes) -> str:
    if len(data) > MAX_BYTES:
        raise CsvFormatError(f"file is larger than {MAX_BYTES // 1024} KB")
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CsvFormatError("file must be UTF-8 or Windows-1251 text")


def _map_headers(headers: list[str]) -> dict[int, str]:
    lookup = {alias: canon for canon, aliases in HEADER_ALIASES.items() for alias in aliases}
    mapping: dict[int, str] = {}
    for index, header in enumerate(headers):
        canon = lookup.get(header.strip().lower())
        if canon and canon not in mapping.values():
            mapping[index] = canon
    missing = [f for f in REQUIRED if f not in mapping.values()]
    if missing:
        raise CsvFormatError("missing required column(s): " + ", ".join(missing))
    return mapping


def _split(value: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in value.split("|") if v.strip())


def parse_rows(text: str) -> list[tuple[int, dict[str, str]]]:
    sample = text[:4096]
    try:
        dialect: type[csv.Dialect] | csv.Dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise CsvFormatError("file is empty") from exc
    mapping = _map_headers(headers)
    rows: list[tuple[int, dict[str, str]]] = []
    for line_no, values in enumerate(reader, start=2):
        if not any(v.strip() for v in values):
            continue
        if len(rows) >= MAX_ROWS:
            raise CsvFormatError(f"more than {MAX_ROWS} rows; split the file")
        rows.append(
            (line_no, {mapping[i]: v.strip() for i, v in enumerate(values) if i in mapping})
        )
    return rows


def import_csv(
    session: Session, data: bytes, *, filename: str, actor: Actor, dry_run: bool
) -> ImportReport:
    safe_name = (filename or "upload.csv").replace("/", "_").replace("\\", "_")[:100]
    rows = parse_rows(decode(data))
    service = DiscoveryService(session)
    report = ImportReport(filename=safe_name, dry_run=dry_run)
    # A dry run performs the real intake inside a savepoint and rolls it back, so the
    # preview also catches duplicates between rows of the same file.
    savepoint = session.begin_nested()
    for line_no, row in rows:
        company = NewCompany(
            name=row.get("name", ""),
            country=row.get("country", ""),
            city=row.get("city") or None,
            industry=row.get("industry") or None,
            domains=_split(row.get("domain", "")),
            phones=_split(row.get("phone", "")),
            emails=_split(row.get("email", "")),
            telegrams=_split(row.get("telegram", "")),
            notes=row.get("notes") or None,
            source_type="csv",
            source_url=row.get("source_url") or None,
            external_id=f"{safe_name}#{line_no}"[:191],
        )
        report.rows.append(RowResult(line_no, company.name, service.ingest(company, actor)))
    if dry_run:
        savepoint.rollback()
    else:
        savepoint.commit()
    AuditLogRepository(session).add(
        actor=actor,
        action="discovery.csv_import",
        details={
            "file": safe_name,
            "dry_run": dry_run,
            "rows": len(report.rows),
            "created": report.created,
            "duplicates": report.duplicates,
            "invalid": report.invalid,
        },
    )
    return report
