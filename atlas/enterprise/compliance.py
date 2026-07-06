"""Compliance engine — policies, audit trail, risk, violations."""

from __future__ import annotations

from atlas.enterprise.models import (
    AuditRecord,
    CompanyPolicy,
    ComplianceReport,
    ComplianceStatus,
    RiskAssessment,
    RiskLevel,
    _new_id,
    _utcnow,
)


class ComplianceEngine:
    """Tracks policies, audits, risks, and compliance status."""

    def __init__(self) -> None:
        self._policies: dict[str, CompanyPolicy] = {}
        self._audits: dict[str, AuditRecord] = {}
        self._risks: dict[str, RiskAssessment] = {}

    def add_policy(
        self,
        name: str,
        description: str = "",
        category: str = "general",
        rules: tuple[str, ...] = (),
    ) -> CompanyPolicy:
        p = CompanyPolicy(
            id=_new_id("pol"),
            name=name,
            description=description,
            category=category,
            rules=rules,
        )
        self._policies[p.id] = p
        return p

    def get_policy(self, pid: str) -> CompanyPolicy | None:
        return self._policies.get(pid)

    def list_policies(
        self, category: str | None = None, enabled_only: bool = False
    ) -> list[CompanyPolicy]:
        ps = list(self._policies.values())
        if category is not None:
            ps = [p for p in ps if p.category == category]
        if enabled_only:
            ps = [p for p in ps if p.enabled]
        return ps

    def audit(
        self,
        action: str,
        actor: str = "",
        target: str = "",
        details: tuple[tuple[str, str], ...] = (),
    ) -> AuditRecord:
        r = AuditRecord(
            id=_new_id("audit"),
            action=action,
            actor=actor,
            target=target,
            details=details,
        )
        self._audits[r.id] = r
        return r

    def get_audit(self, aid: str) -> AuditRecord | None:
        return self._audits.get(aid)

    def list_audits(
        self, actor: str | None = None, action: str | None = None, limit: int = 100
    ) -> list[AuditRecord]:
        rs = list(self._audits.values())
        if actor is not None:
            rs = [r for r in rs if r.actor == actor]
        if action is not None:
            rs = [r for r in rs if r.action == action]
        return sorted(rs, key=lambda r: r.timestamp, reverse=True)[:limit]

    def assess_risk(
        self,
        title: str,
        description: str = "",
        level: str = RiskLevel.LOW.value,
        mitigation: str = "",
    ) -> RiskAssessment:
        r = RiskAssessment(
            id=_new_id("risk"),
            title=title,
            description=description,
            level=level,
            mitigation=mitigation,
        )
        self._risks[r.id] = r
        return r

    def get_risk(self, rid: str) -> RiskAssessment | None:
        return self._risks.get(rid)

    def list_risks(
        self, level: str | None = None, resolved: bool | None = None
    ) -> list[RiskAssessment]:
        rs = list(self._risks.values())
        if level is not None:
            rs = [r for r in rs if r.level == level]
        if resolved is not None:
            if resolved:
                rs = [r for r in rs if r.resolved_at is not None]
            else:
                rs = [r for r in rs if r.resolved_at is None]
        return rs

    def resolve_risk(self, rid: str) -> RiskAssessment | None:
        r = self._risks.get(rid)
        if r is None:
            return None
        import dataclasses

        updated = dataclasses.replace(r, resolved_at=_utcnow())
        self._risks[rid] = updated
        return updated

    def generate_report(self) -> ComplianceReport:
        violations = sum(
            1
            for r in self._risks.values()
            if r.level == RiskLevel.CRITICAL.value and r.resolved_at is None
        )
        warnings = sum(
            1
            for r in self._risks.values()
            if r.level == RiskLevel.HIGH.value and r.resolved_at is None
        )
        checked = len(self._policies)
        status = (
            ComplianceStatus.VIOLATION.value
            if violations > 0
            else (
                ComplianceStatus.WARNING.value
                if warnings > 0
                else ComplianceStatus.COMPLIANT.value
            )
        )
        return ComplianceReport(
            id=_new_id("crep"),
            status=status,
            violations=violations,
            warnings=warnings,
            checked_policies=checked,
        )

    def open_risk_count(self) -> int:
        return sum(1 for r in self._risks.values() if r.resolved_at is None)

    def audit_count(self) -> int:
        return len(self._audits)

    def policy_count(self) -> int:
        return len(self._policies)


__all__ = ["ComplianceEngine"]
