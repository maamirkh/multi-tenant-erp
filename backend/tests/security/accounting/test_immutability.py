"""GL immutability security tests — Phase 14 T285.

``JournalLine`` (modules/accounting/models/gl.py) is documented as
"append-only. NO soft-delete, NO update, ever". This file verifies that
claim two ways:

1. API surface: no PUT/DELETE route exists anywhere in the accounting
   router that targets a journal entry or journal line, posted or not.
   Enumerated directly off ``modules.accounting.router.router.routes``
   (not guessed/hardcoded), so this stays correct if routes are added or
   removed later.

2. DB layer: migration 038 (``migrations/versions/038_accounting_general_ledger.py``)
   defines a Postgres ``BEFORE UPDATE OR DELETE`` trigger
   (``trg_accounting_journal_lines_immutable``) on ``accounting_journal_lines``
   that raises on any mutation attempt. That trigger is PL/pgSQL and only
   applies in a real Postgres database reached via Alembic migrations.

   IMPORTANT — verified discrepancy: this test suite's ``db_session``/
   ``test_client`` fixtures (tests/conftest.py) build the schema with
   ``Base.metadata.create_all()`` against an in-memory SQLite database and
   explicitly patch out ``main.run_migrations`` at TestClient startup ("the
   test DB is already set up by the test_db_engine fixture and SQLite
   doesn't use Alembic" — see conftest.py's own comment). Alembic migrations,
   including migration 038's trigger, never run against the test database.
   SQLite also does not support the PL/pgSQL syntax the trigger uses, so it
   could not be ported as-is even if migrations did run.

   Net effect: a raw SQL UPDATE against a posted ``accounting_journal_lines``
   row is NOT blocked in this test environment — this is a test-harness gap,
   not a production one (production Postgres runs the real migration and
   trigger). The test below documents this honestly: it asserts the
   migration source defines the trigger (proving the production-level
   protection exists) and separately demonstrates + documents that the
   in-memory SQLite test database does not enforce it.

Task: T285
Spec ref: specs/008-accounting-finance/tasks.md T285
"""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import Uuid, bindparam, select, text
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.accounting.models.coa import Account
from modules.accounting.models.gl import JournalLine
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.router import router as accounting_router
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from tests.fixtures.auth_fixtures import create_test_user

_TEST_PASSWORD = "Immutable@12345"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    user, pw = create_test_user(db_session, email=email, password=_TEST_PASSWORD)
    return _login(test_client, user.email, pw)


def _create_company(client: TestClient, token: str) -> uuid.UUID:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Immutable Acct Co {suffix}",
            "email": f"contact-{suffix}@immutable-acct.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _post_a_journal(
    test_client: TestClient, token: str, db_session: Session, cid: uuid.UUID
) -> str:
    """Create GL accounts + fiscal year, create a balanced journal, and post
    it directly (below the (unset) approval threshold — DRAFT can be posted
    directly per PostingEngine.post()'s docstring "Post a DRAFT/APPROVED
    journal entry"). Returns the posted journal_id."""
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
    ar = account_repo.create(
        Account(
            company_id=cid, account_code="1100", account_name="AR", account_type="ASSET"
        )
    )
    revenue = account_repo.create(
        Account(
            company_id=cid,
            account_code="4000",
            account_name="Revenue",
            account_type="REVENUE",
        )
    )
    today = utcnow().date()
    fiscal_service.create_fiscal_year(
        cid,
        f"FY-{uuid.uuid4().hex[:8]}",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )

    cid_str = str(cid)
    resp = test_client.post(
        _url(cid_str, "/journals"),
        json={
            "journal_type": "STANDARD",
            "posting_source": "MANUAL",
            "posting_date": today.isoformat(),
            "currency_code": "USD",
            "lines": [
                {
                    "account_id": str(ar.id),
                    "debit_amount": "500.00",
                    "credit_amount": "0",
                },
                {
                    "account_id": str(revenue.id),
                    "debit_amount": "0",
                    "credit_amount": "500.00",
                },
            ],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    journal_id = resp.json()["data"]["id"]

    resp = test_client.post(
        _url(cid_str, f"/journals/{journal_id}/post"), headers=_auth(token)
    )
    assert resp.status_code == 200, resp.text

    return journal_id


# ---------------------------------------------------------------------------
# API surface: no PUT/DELETE route touches journal entries or journal lines
# ---------------------------------------------------------------------------


class TestNoMutationRouteForJournals:
    def test_no_put_or_delete_route_targets_journals_or_lines(self) -> None:
        """Restricted to the actual GL journal-entry prefix (``/journals``,
        ``/journals/{id}``, etc.) rather than a bare "journal" substring
        match — the router also has an unrelated ``PUT
        /recurring-journals/{template_id}`` route (a mutable *template*
        that generates future journal entries, not a posted ledger entry
        itself; mutating the template is fine and expected)."""
        offending = []
        for route in accounting_router.routes:
            methods = getattr(route, "methods", None) or set()
            path = getattr(route, "path", "")
            if not methods & {"PUT", "DELETE", "PATCH"}:
                continue
            if (
                path == "/journals"
                or path.startswith("/journals/")
                or path.startswith("/journals{")
            ):
                offending.append((sorted(methods), path))
        assert offending == [], (
            f"Found mutation route(s) touching journals: {offending} — "
            "journal entries/lines must be append-only (create/transition "
            "only, never PUT/DELETE)."
        )

    def test_journal_lines_have_no_dedicated_endpoint_at_all(self) -> None:
        """There is no ``/journals/{id}/lines`` sub-resource route of any
        HTTP method — journal lines are only ever created as part of
        creating the parent journal entry, never addressed individually.
        (Restricted to the ``/journals`` prefix — the router separately has
        an unrelated, legitimately mutable ``/tax-groups/{id}/lines``
        sub-resource for tax group composition, nothing to do with the GL.)
        """
        line_routes = [
            (
                sorted(getattr(route, "methods", set()) or set()),
                getattr(route, "path", ""),
            )
            for route in accounting_router.routes
            if getattr(route, "path", "").lower().startswith("/journals")
            and "/lines" in getattr(route, "path", "").lower()
        ]
        assert (
            line_routes == []
        ), f"Unexpected dedicated journal-line route(s): {line_routes}"


# ---------------------------------------------------------------------------
# DB layer: migration defines the trigger; SQLite test DB does not run it
# ---------------------------------------------------------------------------


class TestDatabaseLevelImmutability:
    def test_migration_038_defines_a_postgres_immutability_trigger(self) -> None:
        """Confirms the production-level protection exists in source, since
        it cannot be exercised against the SQLite test database (see class
        and module docstrings)."""
        migration_path = (
            Path(__file__).resolve().parents[3]
            / "migrations"
            / "versions"
            / "038_accounting_general_ledger.py"
        )
        assert migration_path.exists(), f"Expected migration file at {migration_path}"
        source = migration_path.read_text()
        assert "accounting_journal_lines_block_mutation" in source
        assert "trg_accounting_journal_lines_immutable" in source
        assert "BEFORE UPDATE OR DELETE ON accounting_journal_lines" in source

    def test_raw_sql_update_against_posted_line_not_blocked_in_sqlite_test_db(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """DOCUMENTED GAP (test-infrastructure only, not production):

        In the real deployment, migration 038's trigger blocks this exact
        UPDATE at the Postgres level. In THIS test suite, the schema is
        built via ``Base.metadata.create_all()`` on SQLite (Alembic is
        explicitly bypassed — see tests/conftest.py), so no such trigger
        exists here, and SQLite could not run its PL/pgSQL body anyway.

        This test proves that fact honestly (the UPDATE succeeds against
        the test DB) rather than asserting a 403/blocked outcome that does
        not occur in this environment. It should NOT be read as "GL
        immutability is unenforced" — modules/accounting/models/gl.py's
        JournalLine class deliberately exposes no update()/delete() path at
        the ORM/repository layer either (append-only by construction), and
        production Postgres enforces it at the DB layer per migration 038.
        """
        token = _user_token(
            test_client, db_session, f"immut-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, token)
        journal_id = _post_a_journal(test_client, token, db_session, cid)

        line = (
            db_session.execute(
                select(JournalLine).where(
                    JournalLine.journal_entry_id == uuid.UUID(journal_id)
                )
            )
            .scalars()
            .first()
        )
        assert line is not None, "Posted journal must have at least one line"
        original_debit = line.debit_amount
        line_id = line.id

        # Bind the id parameter with the same SQLAlchemy `Uuid` type the
        # column uses, so the raw UPDATE's WHERE clause matches the
        # dialect-specific on-disk representation SQLite stores UUIDs in
        # (a plain str/UUID literal via `text()` params bypasses the
        # column's bind processor and silently matches zero rows).
        update_stmt = text(
            "UPDATE accounting_journal_lines SET debit_amount = :amt WHERE id = :id"
        ).bindparams(bindparam("id", type_=Uuid(as_uuid=True)))
        result = db_session.execute(update_stmt, {"amt": 999999, "id": line_id})
        db_session.commit()
        assert result.rowcount == 1, (
            f"Raw UPDATE matched {result.rowcount} row(s), expected exactly 1 "
            "— the WHERE id = :id clause failed to match the posted line."
        )

        db_session.expire_all()
        mutated = db_session.get(JournalLine, line_id)
        assert mutated is not None
        # This assertion documents the gap: the raw UPDATE succeeded against
        # the SQLite test database. If a SQLite-compatible trigger/guard is
        # ever added to the test schema, this line should start failing and
        # should be updated to assert the UPDATE is rejected instead.
        assert mutated.debit_amount != original_debit, (
            "Expected the SQLite test DB to allow this raw UPDATE (no "
            "trigger ported from migration 038) — if it was blocked, the "
            "test environment now enforces DB-level immutability and this "
            "test should be updated to assert that instead."
        )
