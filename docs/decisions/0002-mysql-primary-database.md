# ADR-0002: MySQL/MariaDB as primary database

**Context.** cPanel shared hosting provides MySQL/MariaDB, not PostgreSQL.

**Decision.** Target MySQL/MariaDB (`utf8mb4`) in production via SQLAlchemy 2.x + Alembic, driver PyMySQL (pure Python, installs without a compiler). UUIDs stored as `CHAR(36)` through a portable type. No Postgres-only features. SQLite for fast tests; MariaDB service in CI for migration and repository tests.

**Consequences.** No `SKIP LOCKED` dependency; job locking uses a portable lock-row + optimistic update pattern. Migration to PostgreSQL later is a configuration change plus a data move.
