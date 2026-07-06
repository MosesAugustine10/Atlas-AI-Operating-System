"""Finance — transactions, invoices, and P&L."""

from __future__ import annotations

import dataclasses
from typing import Any

from atlas.business.models import (
    Invoice,
    Transaction,
    TransactionType,
    _new_id,
    _utcnow,
)


class FinanceManager:
    def __init__(self) -> None:
        self._transactions: dict[str, Transaction] = {}
        self._invoices: dict[str, Invoice] = {}

    def add_transaction(
        self,
        type: str = TransactionType.INCOME.value,
        amount: float = 0.0,
        description: str = "",
        customer_id: str = "",
        project_id: str = "",
    ) -> Transaction:
        t = Transaction(
            id=_new_id("txn"),
            type=type,
            amount=amount,
            description=description,
            customer_id=customer_id,
            project_id=project_id,
        )
        self._transactions[t.id] = t
        return t

    def get_transaction(self, tid: str) -> Transaction | None:
        return self._transactions.get(tid)

    def list_transactions(
        self, type: str | None = None, customer_id: str | None = None
    ) -> list[Transaction]:
        ts = list(self._transactions.values())
        if type is not None:
            ts = [t for t in ts if t.type == type]
        if customer_id is not None:
            ts = [t for t in ts if t.customer_id == customer_id]
        return sorted(ts, key=lambda t: t.date)

    def total_income(self) -> float:
        return sum(
            t.amount
            for t in self._transactions.values()
            if t.type == TransactionType.INCOME.value
        )

    def total_expenses(self) -> float:
        return sum(
            t.amount
            for t in self._transactions.values()
            if t.type == TransactionType.EXPENSE.value
        )

    def net_profit(self) -> float:
        return self.total_income() - self.total_expenses()

    def create_invoice(
        self,
        customer_id: str,
        amount: float = 0.0,
        project_id: str = "",
        due_date: Any | None = None,
        line_items: tuple[tuple[str, float], ...] = (),
    ) -> Invoice:
        inv = Invoice(
            id=_new_id("inv"),
            customer_id=customer_id,
            project_id=project_id,
            amount=amount,
            due_date=due_date or _utcnow(),
            line_items=line_items,
        )
        self._invoices[inv.id] = inv
        return inv

    def get_invoice(self, iid: str) -> Invoice | None:
        return self._invoices.get(iid)

    def list_invoices(
        self, customer_id: str | None = None, status: str | None = None
    ) -> list[Invoice]:
        invs = list(self._invoices.values())
        if customer_id is not None:
            invs = [i for i in invs if i.customer_id == customer_id]
        if status is not None:
            invs = [i for i in invs if i.status == status]
        return sorted(invs, key=lambda i: i.issue_date)

    def pay_invoice(self, iid: str) -> Invoice | None:
        inv = self._invoices.get(iid)
        if inv is None:
            return None
        updated = dataclasses.replace(inv, status="paid", paid_date=_utcnow())
        self._invoices[iid] = updated
        self.add_transaction(
            type=TransactionType.INCOME.value,
            amount=inv.amount,
            customer_id=inv.customer_id,
            project_id=inv.project_id,
            description=f"Invoice {inv.id}",
        )
        return updated

    def overdue_invoices(self) -> list[Invoice]:
        now = _utcnow()
        return [
            i
            for i in self._invoices.values()
            if i.status != "paid" and i.due_date < now
        ]

    def transaction_count(self) -> int:
        return len(self._transactions)

    def invoice_count(self) -> int:
        return len(self._invoices)


__all__ = ["FinanceManager"]
