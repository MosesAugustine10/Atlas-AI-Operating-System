"""Revenue tracking and snapshots."""

from __future__ import annotations

from atlas.business.customers import CustomerManager
from atlas.business.finance import FinanceManager
from atlas.business.models import CustomerStatus, DealStage, RevenueSnapshot, _new_id
from atlas.business.sales import SalesManager


class RevenueManager:
    def __init__(
        self,
        finance: FinanceManager | None = None,
        sales: SalesManager | None = None,
        customers: CustomerManager | None = None,
    ) -> None:
        self.finance = finance or FinanceManager()
        self.sales = sales or SalesManager()
        self.customers = customers or CustomerManager()
        self._snapshots: dict[str, RevenueSnapshot] = {}

    def snapshot(self, period: str = "") -> RevenueSnapshot:
        deals_won = self.sales.count_by_stage().get(DealStage.CLOSED_WON.value, 0)
        deals_lost = self.sales.count_by_stage().get(DealStage.CLOSED_LOST.value, 0)
        customer_counts = self.customers.count_by_status()
        new_customers = customer_counts.get(
            CustomerStatus.LEAD.value, 0
        ) + customer_counts.get(CustomerStatus.PROSPECT.value, 0)
        churned = customer_counts.get(CustomerStatus.CHURNED.value, 0)
        total_rev = self.finance.total_income()
        total_exp = self.finance.total_expenses()
        snap = RevenueSnapshot(
            id=_new_id("rev"),
            period=period,
            total_revenue=total_rev,
            total_expenses=total_exp,
            net_profit=total_rev - total_exp,
            deals_won=deals_won,
            deals_lost=deals_lost,
            new_customers=new_customers,
            churned_customers=churned,
        )
        self._snapshots[snap.id] = snap
        return snap

    def get(self, sid: str) -> RevenueSnapshot | None:
        return self._snapshots.get(sid)

    def list(self) -> list[RevenueSnapshot]:
        return list(self._snapshots.values())

    def latest(self) -> RevenueSnapshot | None:
        snaps = self.list()
        return snaps[-1] if snaps else None

    def count(self) -> int:
        return len(self._snapshots)


__all__ = ["RevenueManager"]
