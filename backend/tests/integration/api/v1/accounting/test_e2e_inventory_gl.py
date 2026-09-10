"""End-to-end integration test: Inventory adjustment -> GL — Phase 16 (T297).

**Documents a real, open gap rather than inventing a capability that does
not exist**, per the established convention throughout this epic's tasks.md
(e.g. T073, T076, T099 all explicitly document deferred integration points
instead of silently completing them out of phase order).

Per ``modules/accounting/handlers/integration_handlers.py``'s module
docstring and ADR-0004 (``history/adr/0004-gl-account-resolution-for-sales-
purchase-inventory-integration-events.md``): Inventory's real events (`StockAdjusted`/`InventoryAdjustmentApproved`,
``modules/inventory/domain_events.py``) carry no GL account fields and no
cost/value breakdown, and ADR-0004 explicitly leaves "Inventory GL-value
sufficiency" as an open item — there is no default inventory-control/
inventory-adjustment account mapping defined anywhere in the codebase yet.
``handle_inventory_adjustment_posted`` therefore exists only as an
unsubscribed stub (see ``register_integration_handlers()`` — it subscribes
only the 2 live Sales handlers).

This test verifies that CURRENT documented behavior — publishing a real
``StockAdjusted`` event on Inventory's live event bus produces **no** GL
entry for the company, because nothing is subscribed — and that the stub
handler itself is a safe no-op if invoked directly. When Phase 4's open
ADR-0004 item is resolved and this handler is actually wired to Inventory's
bus, this test's first assertion (`assert entries == []`) is exactly the
line that must flip to a real DR/CR GL assertion — a deliberate tripwire,
not an oversight.

Spec ref: specs/008-accounting-finance/tasks.md T297
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.accounting.handlers.integration_handlers import (
    handle_inventory_adjustment_posted,
)
from modules.accounting.models.coa import Account
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.gl import (
    AccountingAuditLogRepository,
    JournalEntryRepository,
)
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from modules.inventory.domain_events import StockAdjusted
from modules.inventory.events import get_event_bus as get_inventory_event_bus
from tests.fixtures.auth_fixtures import create_test_user


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["data"]["access_token"])


def _create_company(client: TestClient, token: str) -> uuid.UUID:
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Inv GL Test Co {suffix}",
            "email": f"contact-{suffix}@inv-gl-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _setup_gl(db_session: Session, company_id: uuid.UUID) -> dict[str, Any]:
    account_repo = AccountRepository(db_session)
    fiscal_service = FiscalCalendarService(
        db=db_session,
        year_repo=FiscalYearRepository(db_session),
        period_repo=FiscalPeriodRepository(db_session),
        opening_balance_repo=OpeningBalanceRepository(db_session),
        audit_service=AuditLogService(
            db=db_session, audit_repo=AccountingAuditLogRepository(db_session)
        ),
    )
    inventory_control = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1300",
            account_name="Inventory Control",
            account_type="ASSET",
        )
    )
    today = date.today()
    fiscal_service.create_fiscal_year(
        company_id,
        f"FY-{uuid.uuid4().hex[:8]}",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )
    return {"inventory_control": inventory_control, "today": today}


class TestInventoryAdjustmentGLGap:
    def test_stock_adjusted_event_produces_no_gl_entry_yet(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Publishing the real Inventory event produces zero GL entries for
        the company — ``handle_inventory_adjustment_posted`` is not
        subscribed to Inventory's bus (ADR-0004 open item)."""
        user, pw = create_test_user(db_session, email="inv_gl_gap@example.com")
        token = _login(test_client, user.email, pw)
        cid = _create_company(test_client, token)
        _setup_gl(db_session, cid)

        get_inventory_event_bus().publish(
            StockAdjusted(
                aggregate_id=uuid.uuid4(),
                company_id=cid,
                product_id=str(uuid.uuid4()),
                warehouse_id=str(uuid.uuid4()),
                adjustment_qty="-10",
                adjustment_id=str(uuid.uuid4()),
                reason_code="DAMAGE",
            )
        )

        entries, total = JournalEntryRepository(db_session).search(
            company_id=cid, filters={}
        )
        assert entries == []
        assert total == 0

    def test_stub_handler_is_a_safe_noop(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Directly invoking the documented stub must not raise — it only
        logs a warning per ADR-0004's deferral."""
        event = StockAdjusted(
            aggregate_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            product_id=str(uuid.uuid4()),
            warehouse_id=str(uuid.uuid4()),
            adjustment_qty="5",
            adjustment_id=str(uuid.uuid4()),
            reason_code="RECOUNT",
        )
        handle_inventory_adjustment_posted(event)  # must not raise
