"""Read and save agent settings; every save is versioned and audit-logged."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.actors import Actor
from app.domain.agent_settings import SETTINGS_MODELS, defaults, load
from app.domain.agents import AgentModule
from app.domain.errors import DomainError
from app.infrastructure.database.models import AgentSetting, AgentSettingVersion
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.workflow import AuditLogRepository


class AgentSettingsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, module: AgentModule) -> Any:
        row = self.session.get(AgentSetting, module.value)
        return load(module, row.values if row else None)

    def current_version(self, module: AgentModule) -> int:
        row = self.session.get(AgentSetting, module.value)
        return row.version if row else 0

    def save(
        self, module: AgentModule, settings: BaseModel, actor: Actor, *, note: str | None = None
    ) -> int:
        if not isinstance(settings, SETTINGS_MODELS[module]):
            raise DomainError("settings do not match the agent")
        values = settings.model_dump(mode="json")
        row = self.session.get(AgentSetting, module.value, with_for_update=True)
        if row is None:
            row = AgentSetting(module=module.value, version=0, updated_by=str(actor))
            self.session.add(row)
        row.values = values
        row.version += 1
        row.updated_at = utcnow()
        row.updated_by = str(actor)
        self.session.add(
            AgentSettingVersion(
                module=module.value,
                version=row.version,
                values=values,
                changed_by=str(actor),
                note=note,
            )
        )
        AuditLogRepository(self.session).add(
            actor=actor,
            action="settings.agent",
            entity_type="agent",
            details={"module": module.value, "version": row.version, "note": note},
        )
        self.session.flush()
        return row.version

    def history(self, module: AgentModule, limit: int = 20) -> list[AgentSettingVersion]:
        return list(
            self.session.scalars(
                select(AgentSettingVersion)
                .where(AgentSettingVersion.module == module.value)
                .order_by(AgentSettingVersion.version.desc())
                .limit(limit)
            )
        )

    def restore(self, module: AgentModule, version_id: uuid.UUID, actor: Actor) -> int:
        """Re-save an earlier version as the newest one (history is never rewritten)."""
        old = self.session.get(AgentSettingVersion, version_id)
        if old is None or old.module != module.value:
            raise DomainError("settings version not found")
        return self.save(module, load(module, old.values), actor, note=f"restored v{old.version}")

    def reset(self, module: AgentModule, actor: Actor) -> int:
        return self.save(module, defaults(module), actor, note="defaults")
