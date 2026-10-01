"""Payment processing performance benchmark — Phase 18 (T314).

Verifies plan.md Phase 18 acceptance criterion: "payment processing < 2
seconds." Times the full HTTP request path for ``POST /payments/customer``
(the ``PaymentService.create_customer_payment()`` DR Bank/CR AR posting +
paired ``ARTransaction`` creation, atomically, per Phase 10) — not just the
service call in isolation, since that end-to-end path (auth, FastAPI
routing/validation, DB commit) is what a real caller experiences.

Spec ref: specs/008-accounting-finance/tasks.md T314
Plan ref: specs/008-accounting-finance/plan.md Phase 18 Scope
"""

from __future__ import annotations

import time
import uuid
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.accounting.models.banking import BankAccount
from modules.accounting.models.coa import Account
from modules.accounting.repositories.banking import BankAccountRepository
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from tests.fixtures.auth_fixtures import create_test_user

_TARGET_SECONDS = 2
_SAMPLE_COUNT = 10


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _url(company_id: str, path: str) -> str:
    return f"/api/v1/companies/{company_id}/accounting{path}"


def _create_company(client: TestClient, token: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Payment Perf Test Co {suffix}",
            "email": f"contact-{suffix}@payment-perf-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["data"]["id"])


class TestPaymentProcessingPerformance:
    def test_customer_payment_processes_under_2_seconds(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"pay-perf-{uuid.uuid4().hex[:8]}@test.com"
        password = "TestPass123!"
        create_test_user(db_session, email=email, password=password)
        token = _login(test_client, email, password)
        cid = _create_company(test_client, token)

        account_repo = AccountRepository(db_session)
        bank_gl = account_repo.create(
            Account(
                company_id=uuid.UUID(cid),
                account_code="1000",
                account_name="Bank",
                account_type="ASSET",
            )
        )
        ar_gl = account_repo.create(
            Account(
                company_id=uuid.UUID(cid),
                account_code="1100",
                account_name="AR",
                account_type="ASSET",
            )
        )
        bank_account = BankAccountRepository(db_session).create(
            BankAccount(
                company_id=uuid.UUID(cid),
                bank_name="Perf Test Bank",
                account_number="ACC-PERF-0001",
                currency_code="USD",
                gl_account_id=bank_gl.id,
            )
        )
        resp = test_client.put(
            _url(cid, "/system-accounts"),
            json={"role": "default_ar_account_id", "account_id": str(ar_gl.id)},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text

        today = date.today()
        fiscal_service = FiscalCalendarService(
            db=db_session,
            year_repo=FiscalYearRepository(db_session),
            period_repo=FiscalPeriodRepository(db_session),
            opening_balance_repo=OpeningBalanceRepository(db_session),
            audit_service=AuditLogService(
                db=db_session, audit_repo=AccountingAuditLogRepository(db_session)
            ),
        )
        fiscal_service.create_fiscal_year(
            uuid.UUID(cid),
            f"FY-{uuid.uuid4().hex[:8]}",
            date(today.year, 1, 1),
            date(today.year, 12, 31),
            "USD",
        )

        elapsed_times: list[float] = []
        for i in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = test_client.post(
                _url(cid, "/payments/customer"),
                json={
                    "customer_id": str(uuid.uuid4()),
                    "payment_method": "BANK_TRANSFER",
                    "payment_date": date.today().isoformat(),
                    "amount": "100.00",
                    "currency_code": "USD",
                    "bank_account_id": str(bank_account.id),
                    "reference": f"PERF-PAY-{i:03d}",
                },
                headers=_auth(token),
            )
            elapsed = time.perf_counter() - start
            assert resp.status_code == 201, resp.text
            assert resp.json()["data"]["status"] == "POSTED"
            elapsed_times.append(elapsed)

        max_elapsed = max(elapsed_times)
        avg_elapsed = sum(elapsed_times) / len(elapsed_times)
        print(
            f"\nCustomer payment processing over {_SAMPLE_COUNT} samples: "
            f"avg={avg_elapsed:.3f}s max={max_elapsed:.3f}s"
        )
        assert max_elapsed < _TARGET_SECONDS, (
            f"Slowest payment took {max_elapsed:.2f}s, exceeding the "
            f"{_TARGET_SECONDS}s target."
        )
