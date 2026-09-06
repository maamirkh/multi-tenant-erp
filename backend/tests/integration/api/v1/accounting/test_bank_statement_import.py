"""API integration test: bank statement CSV import — Phase 16 (T301).

Verifies importing a 5000-line bank statement completes in < 30s and every
line is stored correctly.

No server-side raw-CSV-text endpoint exists — confirmed in
``bank_service.py``'s docstring ("CSV parsing happens at the API layer —
this accepts already-parsed dicts") and matching the convention already
established by Phase 2's COA bulk import (``POST /accounts/bulk-import``
also accepts pre-parsed JSON rows, not a raw file upload). This test
therefore generates a real CSV text blob via Python's ``csv`` module (as a
real bank export would look), parses it client-side exactly as a real
client integration would, and POSTs the parsed rows as JSON — timing the
parse+import path together, since that is the actual end-to-end cost a
caller pays.

Spec ref: specs/008-accounting-finance/tasks.md T301
"""

from __future__ import annotations

import csv
import io
import time
import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.accounting.models.banking import BankAccount
from modules.accounting.models.coa import Account
from modules.accounting.repositories.banking import (
    BankAccountRepository,
    BankStatementLineRepository,
)
from modules.accounting.repositories.coa import AccountRepository
from tests.fixtures.auth_fixtures import create_test_user

_LINE_COUNT = 5000
_TARGET_SECONDS = 30


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _url(company_id: str, path: str) -> str:
    return f"/api/v1/companies/{company_id}/accounting{path}"


def _user_token(test_client: TestClient, db_session: Session, email: str) -> str:
    user, pw = create_test_user(db_session, email=email)
    return _login(test_client, user.email, pw)


def _create_company(client: TestClient, token: str) -> uuid.UUID:
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Bank Import Test Co {suffix}",
            "email": f"contact-{suffix}@bank-import-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _make_statement_csv(line_count: int, start_date: date) -> str:
    """Build a realistic bank-statement CSV: date, amount, reference, description."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["statement_date", "amount", "reference", "description"])
    for i in range(line_count):
        line_date = start_date + timedelta(days=i % 28)
        amount = Decimal("10.00") + Decimal(i)
        writer.writerow(
            [line_date.isoformat(), str(amount), f"REF-{i:06d}", f"Statement line {i}"]
        )
    return buf.getvalue()


def _parse_statement_csv(csv_text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(csv_text))
    return [
        {
            "statement_date": row["statement_date"],
            "amount": row["amount"],
            "reference": row["reference"],
            "description": row["description"],
        }
        for row in reader
    ]


class TestBankStatementCSVImport:
    def test_5000_line_csv_import_under_30_seconds(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "bank_csv_import@example.com")
        cid = str(_create_company(test_client, token))

        bank_gl = AccountRepository(db_session).create(
            Account(
                company_id=uuid.UUID(cid),
                account_code="1000",
                account_name="Bank",
                account_type="ASSET",
            )
        )
        bank_account = BankAccountRepository(db_session).create(
            BankAccount(
                company_id=uuid.UUID(cid),
                bank_name="CSV Import Test Bank",
                account_number="ACC-CSV-0001",
                currency_code="USD",
                gl_account_id=bank_gl.id,
            )
        )

        resp = test_client.post(
            _url(cid, f"/bank-accounts/{bank_account.id}/reconciliations"),
            json={
                "statement_date": date.today().isoformat(),
                "statement_closing_balance": "0.00",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        reconciliation_id = resp.json()["data"]["id"]

        csv_text = _make_statement_csv(_LINE_COUNT, date.today() - timedelta(days=90))

        start = time.perf_counter()
        parsed_lines = _parse_statement_csv(csv_text)
        assert len(parsed_lines) == _LINE_COUNT

        resp = test_client.post(
            _url(
                cid,
                f"/bank-accounts/{bank_account.id}/reconciliations/{reconciliation_id}/import-statement",
            ),
            json={"lines": parsed_lines},
            headers=_auth(token),
        )
        elapsed_seconds = time.perf_counter() - start

        assert resp.status_code == 201, resp.text
        results = resp.json()["data"]
        print(
            f"\nBank statement CSV import: {_LINE_COUNT} lines in {elapsed_seconds:.2f}s"
        )

        assert len(results) == _LINE_COUNT
        assert elapsed_seconds < _TARGET_SECONDS, (
            f"Bank statement import of {_LINE_COUNT} lines took {elapsed_seconds:.2f}s, "
            f"exceeding the {_TARGET_SECONDS}s target."
        )

        # Every line is actually persisted and matches the source CSV.
        stored = BankStatementLineRepository(db_session).find_by_bank_account(
            company_id=uuid.UUID(cid), bank_account_id=bank_account.id
        )
        assert len(stored) == _LINE_COUNT
        stored_references = {line.reference for line in stored}
        expected_references = {row["reference"] for row in parsed_lines}
        assert stored_references == expected_references

        sample = next(line for line in stored if line.reference == "REF-000042")
        assert sample.amount == Decimal("10.00") + Decimal(42)
        assert sample.description == "Statement line 42"
