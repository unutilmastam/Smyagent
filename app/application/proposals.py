"""Offer drafting, Quality Gate and explicit owner approval (CLAUDE.md §8.1, §8.2, M7).

Flow: QUALIFIED lead → draft v1 (PROPOSAL_DRAFTED) → Quality Gate →
AWAITING_APPROVAL + approval request (or NEEDS_EDIT when the gate rejects) →
owner approves (APPROVED) or rejects (lead DISQUALIFIED). Edits create a new
version and are re-checked; nothing is sent from here (sending is M9).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.application.controls import Button
from app.application.workflow import NotFoundError, WorkflowService
from app.domain.actors import Actor
from app.domain.agents import AgentModule
from app.domain.audit import Kind
from app.domain.errors import DomainError
from app.domain.leads import LeadStage
from app.domain.persona import language_for_country
from app.domain.proposals import (
    ApprovalStatus,
    Observation,
    OfferInput,
    ProposalStatus,
    build_offer,
)
from app.domain.quality_gate import GateResult, Verdict, review
from app.domain.scoring import Service
from app.infrastructure.database.models import (
    ApprovalRequest,
    Company,
    Lead,
    Opportunity,
    Proposal,
    ProposalVersion,
    ResearchFinding,
    ResearchRun,
)
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.agent_settings import AgentSettingsRepository
from app.infrastructure.repositories.workflow import AuditLogRepository

PROPOSAL_ACTOR = Actor.agent(AgentModule.PROPOSAL_REQUIREMENTS.value)
GATE_ACTOR = Actor.agent(AgentModule.QUALITY_GATE.value)
MAX_TITLE = 200
MAX_BODY = 8000
PREVIEW_CHARS = 1500

# Telegram callback data: "pa:<uuid>" approve, "pr:<uuid>" reject (≤ 64 bytes).
CALLBACK_APPROVE = "pa"
CALLBACK_REJECT = "pr"


class ProposalStateError(DomainError):
    """The proposal is not in a state that allows this action."""


@dataclass(frozen=True)
class GateOutcome:
    proposal_id: uuid.UUID
    result: GateResult
    approval_requested: bool  # a new pending approval request was created


class ProposalService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.workflow = WorkflowService(session)
        self.settings = AgentSettingsRepository(session)

    # -- drafting ------------------------------------------------------------

    def draft_for_lead(self, lead_id: uuid.UUID) -> Proposal | None:
        """Draft v1 for a QUALIFIED lead. Returns None when there is nothing to offer."""
        lead = self.session.get(Lead, lead_id)
        if lead is None or lead.stage is not LeadStage.QUALIFIED:
            return None
        existing = self.session.scalars(select(Proposal).where(Proposal.lead_id == lead_id)).first()
        if existing is not None:
            return None
        company = self.session.get(Company, lead.company_id)
        if company is None:
            return None
        opportunities = list(
            self.session.scalars(select(Opportunity).where(Opportunity.company_id == company.id))
        )
        findings = self._latest_findings(company.id)
        services = [(Service(o.service), o.strength) for o in opportunities]
        if not services or not findings:
            return None
        config = self.settings.get(AgentModule.PROPOSAL_REQUIREMENTS).offer_config()
        draft = build_offer(
            OfferInput(
                company_name=company.name,
                language=language_for_country(company.country),
                observations=[Observation(f.key, f.kind is Kind.FACT) for f in findings],
                services=services,
            ),
            config,
        )
        if not draft.services:
            return None
        used = set(draft.observation_keys)
        proposal = Proposal(
            company_id=company.id,
            lead_id=lead.id,
            status=ProposalStatus.DRAFT,
            language=draft.language,
            current_version=1,
        )
        proposal.versions = [
            ProposalVersion(
                number=1,
                title=draft.title[:MAX_TITLE],
                body=draft.body,
                services=[s.value for s in draft.services],
                finding_ids=[str(f.id) for f in findings if f.key in used],
                observation_keys=draft.observation_keys,
                assumptions=draft.assumptions,
                open_questions=draft.open_questions,
                created_by=str(PROPOSAL_ACTOR),
                gate_issues=[],
            )
        ]
        self.session.add(proposal)
        self.session.flush()
        self.workflow.transition_lead(
            lead.id, LeadStage.PROPOSAL_DRAFTED, PROPOSAL_ACTOR, "offer v1 drafted"
        )
        return proposal

    def _latest_findings(self, company_id: uuid.UUID) -> list[ResearchFinding]:
        run_id = self.session.scalars(
            select(ResearchRun.id)
            .where(ResearchRun.company_id == company_id)
            .order_by(ResearchRun.created_at.desc())
            .limit(1)
        ).first()
        if run_id is None:
            return []
        return list(
            self.session.scalars(
                select(ResearchFinding).where(ResearchFinding.research_run_id == run_id)
            )
        )

    # -- Quality Gate --------------------------------------------------------

    def run_gate(self, proposal_id: uuid.UUID, number: int) -> GateOutcome | None:
        """Check one version (no-op if it is not current or already checked)."""
        proposal = self._get(proposal_id)
        version = self._version(proposal, number)
        if version is None or number != proposal.current_version or version.gate_verdict:
            return None
        return self._apply_gate(proposal, version)

    def _apply_gate(self, proposal: Proposal, version: ProposalVersion) -> GateOutcome:
        gate = self.settings.get(AgentModule.QUALITY_GATE)
        result = review(
            version.body,
            language=proposal.language,
            evidence_count=len(version.finding_ids),
            extra_blocked=gate.extra_blocked,
            extra_review=gate.extra_review,
        )
        version.gate_verdict = result.verdict
        version.gate_issues = [
            {"code": i.code, "severity": i.severity.value, "detail": i.detail}
            for i in result.issues
        ]
        version.gate_checked_at = utcnow()
        lead = self.session.get(Lead, proposal.lead_id)
        assert lead is not None  # FK cascade: a proposal never outlives its lead
        self._cancel_pending(proposal.id, keep_version=None)

        if result.verdict is Verdict.REJECTED:
            proposal.status = ProposalStatus.NEEDS_EDIT
            if lead.stage in (LeadStage.AWAITING_APPROVAL, LeadStage.APPROVED):
                self.workflow.transition_lead(
                    lead.id, LeadStage.PROPOSAL_DRAFTED, GATE_ACTOR, "quality gate rejected"
                )
            return GateOutcome(proposal.id, result, approval_requested=False)

        proposal.status = ProposalStatus.AWAITING_APPROVAL
        if lead.stage is LeadStage.APPROVED:  # edited after approval: approve again
            self.workflow.transition_lead(
                lead.id, LeadStage.PROPOSAL_DRAFTED, GATE_ACTOR, "edited after approval"
            )
        if lead.stage is LeadStage.PROPOSAL_DRAFTED:
            self.workflow.transition_lead(
                lead.id, LeadStage.AWAITING_APPROVAL, GATE_ACTOR, f"gate: {result.verdict.value}"
            )
        self.session.add(
            ApprovalRequest(
                entity_type="proposal",
                entity_id=proposal.id,
                version=version.number,
                status=ApprovalStatus.PENDING,
                requested_by=str(GATE_ACTOR),
            )
        )
        self.session.flush()
        return GateOutcome(proposal.id, result, approval_requested=True)

    def _cancel_pending(self, proposal_id: uuid.UUID, *, keep_version: int | None) -> None:
        stmt = update(ApprovalRequest).where(
            ApprovalRequest.entity_type == "proposal",
            ApprovalRequest.entity_id == proposal_id,
            ApprovalRequest.status == ApprovalStatus.PENDING,
        )
        if keep_version is not None:
            stmt = stmt.where(ApprovalRequest.version != keep_version)
        self.session.execute(
            stmt.values(status=ApprovalStatus.CANCELLED, decided_at=utcnow()).execution_options(
                synchronize_session=False
            )
        )

    # -- owner decisions -----------------------------------------------------

    def approve(self, proposal_id: uuid.UUID, actor: Actor) -> Proposal:
        proposal = self._get(proposal_id, lock=True)
        if proposal.status is not ProposalStatus.AWAITING_APPROVAL:
            raise ProposalStateError(f"proposal is {proposal.status.value}, not awaiting approval")
        version = self._version(proposal, proposal.current_version)
        if version is None or version.gate_verdict in (None, Verdict.REJECTED):
            raise ProposalStateError("the current version has not passed the quality gate")
        request = self._pending_request(proposal.id, version.number)
        if request is None:
            raise ProposalStateError("no pending approval request")
        now = utcnow()
        request.status = ApprovalStatus.APPROVED
        request.decided_by = str(actor)
        request.decided_at = now
        proposal.status = ProposalStatus.APPROVED
        self.workflow.transition_lead(
            proposal.lead_id, LeadStage.APPROVED, actor, f"offer v{version.number} approved"
        )
        AuditLogRepository(self.session).add(
            actor=actor,
            action="proposal.approve",
            entity_type="proposal",
            entity_id=proposal.id,
            details={"version": version.number},
        )
        return proposal

    def reject(self, proposal_id: uuid.UUID, actor: Actor, reason: str = "") -> Proposal:
        """The owner decides not to approach this company: lead → DISQUALIFIED."""
        proposal = self._get(proposal_id, lock=True)
        if proposal.status in (ProposalStatus.APPROVED, ProposalStatus.REJECTED):
            raise ProposalStateError(f"proposal is already {proposal.status.value}")
        reason = reason.strip()[:300] or "rejected by owner"
        pending = self._pending_request(proposal.id, proposal.current_version)
        if pending is not None:
            pending.status = ApprovalStatus.REJECTED
            pending.decided_by = str(actor)
            pending.decided_at = utcnow()
            pending.reason = reason
        self._cancel_pending(proposal.id, keep_version=proposal.current_version)
        proposal.status = ProposalStatus.REJECTED
        self.workflow.transition_lead(proposal.lead_id, LeadStage.DISQUALIFIED, actor, reason)
        AuditLogRepository(self.session).add(
            actor=actor,
            action="proposal.reject",
            entity_type="proposal",
            entity_id=proposal.id,
            details={"version": proposal.current_version, "reason": reason},
        )
        return proposal

    def edit(self, proposal_id: uuid.UUID, actor: Actor, *, title: str, body: str) -> GateOutcome:
        """Save a new version and re-check it immediately (deterministic, no AI cost)."""
        proposal = self._get(proposal_id, lock=True)
        if proposal.status is ProposalStatus.REJECTED:
            raise ProposalStateError("a rejected proposal cannot be edited")
        title, body = title.strip(), body.replace("\r\n", "\n").strip()
        if not title or not body:
            raise DomainError("title and text are required")
        if len(title) > MAX_TITLE or len(body) > MAX_BODY:
            raise DomainError(f"title ≤ {MAX_TITLE} and text ≤ {MAX_BODY} characters")
        current = self._version(proposal, proposal.current_version)
        assert current is not None
        version = ProposalVersion(
            proposal_id=proposal.id,
            number=current.number + 1,
            title=title,
            body=body,
            services=list(current.services),
            finding_ids=list(current.finding_ids),
            observation_keys=list(current.observation_keys),
            assumptions=list(current.assumptions),
            open_questions=list(current.open_questions),
            created_by=str(actor),
            gate_issues=[],
        )
        self.session.add(version)
        proposal.current_version = version.number
        self.session.flush()
        self.session.refresh(proposal, ["versions"])
        AuditLogRepository(self.session).add(
            actor=actor,
            action="proposal.edit",
            entity_type="proposal",
            entity_id=proposal.id,
            details={"version": version.number},
        )
        return self._apply_gate(proposal, version)

    # -- reads ---------------------------------------------------------------

    def _get(self, proposal_id: uuid.UUID, *, lock: bool = False) -> Proposal:
        proposal = self.session.get(
            Proposal,
            proposal_id,
            with_for_update=lock,
            options=[selectinload(Proposal.versions)],
        )
        if proposal is None:
            raise NotFoundError("proposal not found")
        return proposal

    @staticmethod
    def _version(proposal: Proposal, number: int) -> ProposalVersion | None:
        return next((v for v in proposal.versions if v.number == number), None)

    def _pending_request(self, proposal_id: uuid.UUID, number: int) -> ApprovalRequest | None:
        return self.session.scalars(
            select(ApprovalRequest).where(
                ApprovalRequest.entity_type == "proposal",
                ApprovalRequest.entity_id == proposal_id,
                ApprovalRequest.version == number,
                ApprovalRequest.status == ApprovalStatus.PENDING,
            )
        ).first()

    def find_by_prefix(self, prefix: str) -> Proposal | None:
        """Owner bot: `/approve 1a2b3c4d` — match an open proposal by id prefix."""
        prefix = prefix.strip().lower()
        if len(prefix) < 6:
            return None
        matches = [
            p
            for p in self.session.scalars(
                select(Proposal)
                .where(
                    Proposal.status.in_(
                        [ProposalStatus.AWAITING_APPROVAL, ProposalStatus.NEEDS_EDIT]
                    )
                )
                .order_by(Proposal.updated_at.desc())
                .limit(200)
            )
            if str(p.id).startswith(prefix)
        ]
        return matches[0] if len(matches) == 1 else None

    def pending(self, limit: int = 10) -> list[tuple[Proposal, Company]]:
        rows = self.session.execute(
            select(Proposal, Company)
            .join(Company, Company.id == Proposal.company_id)
            .where(
                Proposal.status.in_([ProposalStatus.AWAITING_APPROVAL, ProposalStatus.NEEDS_EDIT])
            )
            .order_by(Proposal.updated_at.desc())
            .limit(limit)
        ).all()
        return [(p, c) for p, c in rows]


def owner_notification(
    proposal: Proposal, company_name: str, outcome: GateOutcome, *, base_url: str = ""
) -> tuple[str, list[Button]]:
    """Text + inline buttons for the owner bot (Uzbek, CLAUDE.md §22)."""
    version = next(v for v in proposal.versions if v.number == proposal.current_version)
    verdict = {
        Verdict.APPROVED: "✅ toza",
        Verdict.NEEDS_REVIEW: "⚠️ ko'rib chiqing",
        Verdict.REJECTED: "⛔ rad etdi",
    }[outcome.result.verdict]
    issues = ", ".join(outcome.result.codes) or "—"
    preview = version.body[:PREVIEW_CHARS] + ("…" if len(version.body) > PREVIEW_CHARS else "")
    text = (
        f"📝 Taklif tasdiqlashni kutmoqda: {company_name}\n"
        f"Xizmatlar: {', '.join(version.services)}\n"
        f"Quality Gate: {verdict} ({issues})\n"
        f"ID: {str(proposal.id)[:8]}\n\n{preview}"
    )
    buttons = [
        Button("✅ Tasdiqlayman", data=f"{CALLBACK_APPROVE}:{proposal.id}"),
        Button("❌ Rad etaman", data=f"{CALLBACK_REJECT}:{proposal.id}"),
    ]
    if base_url.startswith("https://"):
        buttons.append(
            Button("✏️ Tahrirlash", url=f"{base_url.rstrip('/')}/proposals/{proposal.id}")
        )
    return text, buttons


def export_markdown(
    proposal: Proposal,
    company: Company,
    findings: list[ResearchFinding],
    t: Callable[[str], str],
) -> str:
    """Owner-side export: offer text plus evidence, assumptions and open questions."""
    version = next(v for v in proposal.versions if v.number == proposal.current_version)
    place = ", ".join(p for p in (company.country, company.city) if p)
    lines = [
        f"# {version.title}",
        "",
        f"- Company: {company.name} ({place})",
        f"- Status: {proposal.status.value} · version {version.number} · "
        f"quality gate: {version.gate_verdict.value if version.gate_verdict else '—'}",
        f"- Services: {', '.join(version.services)}",
        "",
        "## Offer text",
        "",
        version.body,
        "",
        "## Evidence",
        "",
    ]
    for f in findings:
        source = f" — {f.source_url}" if f.source_url else ""
        lines.append(
            f"- [{f.kind.value}, {f.confidence:.0%}] {f.statement} "
            f"({f.retrieved_at:%Y-%m-%d}){source}"
        )
    lines += ["", "## Assumptions", ""] + [f"- {t(k)}" for k in version.assumptions]
    lines += ["", "## Open questions", ""] + [f"- {t(k)}" for k in version.open_questions]
    return "\n".join(lines) + "\n"
