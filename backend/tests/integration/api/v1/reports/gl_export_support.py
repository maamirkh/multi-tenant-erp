"""Shared GL fixtures/spies for the T207/T208 GL export tests."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_posting_engine
from modules.accounting.services.report_service import ReportService


def post_extra_entries(
    db: Session, company_id: uuid.UUID, fixture: dict[str, Any], count: int
) -> None:
    """Post *count* more balanced 2-line journal entries (2 GL lines each)."""
    engine = build_posting_engine(db)
    today: date = fixture["today"]
    for index in range(count):
        amount = Decimal(f"{index + 1}.00")
        engine.post_direct(
            company_id=company_id,
            journal_type="STANDARD",
            posting_source="MANUAL",
            posting_date=today,
            lines=[
                {
                    "account_id": fixture["cash"].id,
                    "debit_amount": amount,
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": fixture["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": amount,
                },
            ],
            currency_code="USD",
        )
    db.commit()


def spy_gl_page_fetches(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Records the ``limit`` of every ``ReportService.get_gl_report`` call —
    one entry per cursor page requested from the database."""
    calls: list[int] = []
    original = ReportService.get_gl_report

    def spy(
        self: ReportService,
        company_id: uuid.UUID,
        filters: dict[str, Any] | None = None,
        cursor: tuple[date, uuid.UUID, int] | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        calls.append(limit)
        return original(self, company_id, filters, cursor, limit)

    monkeypatch.setattr(ReportService, "get_gl_report", spy)
    return calls
