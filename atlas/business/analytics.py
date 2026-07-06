"""Business analytics and KPI aggregation."""

from __future__ import annotations

from atlas.business.models import KPI, KPICategory, _new_id


class AnalyticsManager:
    def __init__(self) -> None:
        self._kpis: dict[str, KPI] = {}

    def record(
        self,
        name: str,
        value: float = 0.0,
        target: float = 0.0,
        category: str = KPICategory.OPERATIONAL.value,
        unit: str = "",
        period: str = "",
    ) -> KPI:
        k = KPI(
            id=_new_id("kpi"),
            name=name,
            value=value,
            target=target,
            category=category,
            unit=unit,
            period=period,
        )
        self._kpis[k.id] = k
        return k

    def get(self, kid: str) -> KPI | None:
        return self._kpis.get(kid)

    def list(self, category: str | None = None, period: str | None = None) -> list[KPI]:
        ks = list(self._kpis.values())
        if category is not None:
            ks = [k for k in ks if k.category == category]
        if period is not None:
            ks = [k for k in ks if k.period == period]
        return ks

    def top_kpis(self, limit: int = 5) -> list[KPI]:
        return sorted(
            self._kpis.values(), key=lambda k: k.achievement_rate, reverse=True
        )[:limit]

    def underperforming(self, threshold: float = 0.5) -> list[KPI]:
        return [
            k
            for k in self._kpis.values()
            if k.target > 0 and k.achievement_rate < threshold
        ]

    def count(self) -> int:
        return len(self._kpis)

    def count_by_category(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for k in self._kpis.values():
            counts[k.category] = counts.get(k.category, 0) + 1
        return counts

    def average_achievement(self) -> float:
        targeted = [k for k in self._kpis.values() if k.target > 0]
        if not targeted:
            return 0.0
        return sum(k.achievement_rate for k in targeted) / len(targeted)


__all__ = ["AnalyticsManager"]
