"""T272 — cross-precision money on real PostgreSQL ``NUMERIC`` columns.

Sales amounts live in ``NUMERIC(15,2)``; Accounting AR in
``NUMERIC(20,6)``. Reports promotes every figure to the shared
``NUMERIC(20,6)`` precision (``money_normalization.normalize_amount``) and
rounds **only at display** (``round_for_display``) — never mid-calculation
(FR-RPT-150/151/154, Assumption A4).

Both figures are read back through the real HTTP endpoints (dashboard and
Customer 360) from real ``NUMERIC`` columns, as strings — never floats.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.reports.services.money_normalization import (
    normalize_amount,
    round_for_display,
)
from tests.integration.api.v1.reports.conftest import (
    configure_accounting_minimal,
    create_sales_customer,
    reports_url,
    seed_sales_invoice,
    setup_company,
)

# NUMERIC(15,2) sales amounts: 33.33 × 3 + 0.01 = 100.00 exactly.
_SALES_AMOUNTS = ("33.33", "33.33", "33.33", "0.01")
# NUMERIC(20,6) AR outstanding: 0.004999 × 2 = 0.009998 — sub-cent, so any
# 2-dp rounding before combination would erase it.
_AR_OUTSTANDING = (Decimal("0.004999"), Decimal("0.004999"))


def _seed(db: Session, company_id: uuid.UUID) -> uuid.UUID:
    configure_accounting_minimal(db, company_id)
    customer = create_sales_customer(db, company_id)
    today = date.today().isoformat()
    for amount in _SALES_AMOUNTS:
        seed_sales_invoice(
            db, company_id, amount=amount, customer_id=customer.id, invoice_date=today
        )
    ledger = CustomerLedger(company_id=company_id, customer_id=customer.id)
    db.add(ledger)
    db.flush()
    for outstanding in _AR_OUTSTANDING:
        db.add(
            ARTransaction(
                company_id=company_id,
                customer_ledger_id=ledger.id,
                transaction_type="INVOICE",
                transaction_date=date.today(),
                due_date=date.today(),
                currency_code="USD",
                exchange_rate=Decimal("1"),
                amount_foreign=outstanding,
                amount_base=outstanding,
                outstanding_amount=outstanding,
                status="OPEN",
            )
        )
    db.commit()
    return customer.id


def test_mixed_precision_is_combined_at_numeric_20_6_and_rounded_only_at_display(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    customer_id = _seed(db_session, company_id)
    headers = {"Authorization": f"Bearer {token}"}

    dashboard = test_client.get(reports_url(company_id, "/dashboard"), headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    gross_raw = dashboard.json()["data"]["gross_sales"]["value"]
    assert isinstance(gross_raw, str)  # Decimal on the wire, never a float
    gross = Decimal(gross_raw)
    # The NUMERIC(15,2) sum is promoted exactly to 6 decimal places.
    assert gross == Decimal("100.000000")
    assert gross.as_tuple().exponent == -6

    c360 = test_client.get(
        reports_url(company_id, f"/customer-360/{customer_id}"), headers=headers
    )
    assert c360.status_code == 200, c360.text
    body = c360.json()["data"]
    assert Decimal(body["sales"]["total_revenue"]) == Decimal("100.00")
    ar_raw = body["accounting_ar"]["balance"]
    assert isinstance(ar_raw, str)
    ar = Decimal(ar_raw)
    # The NUMERIC(20,6) sub-cent balance survives un-rounded end to end.
    assert ar == sum(_AR_OUTSTANDING) == Decimal("0.009998")

    # Combining the two precisions happens at NUMERIC(20,6)…
    combined = normalize_amount(gross) + normalize_amount(ar)
    assert combined == Decimal("100.009998")
    # …and rounds only at display: 100.01.
    assert round_for_display(combined, 2) == Decimal("100.01")
    # Rounding the *rows* before combining — the error the display-only rule
    # prevents — erases the sub-cent AR balance entirely (0.00 instead of 0.01).
    per_row_rounded = sum(round_for_display(a, 2) for a in _AR_OUTSTANDING)
    assert per_row_rounded == Decimal("0.00")
    assert round_for_display(gross, 2) + per_row_rounded == Decimal("100.00")
