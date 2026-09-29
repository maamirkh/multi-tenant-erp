"""Epic 11 T269 — the additive, read-only
``CustomerRepository.get_names_by_ids()`` seam (the fix for Reports'
``sales.by_customer``/``top_customers`` N+1). Proves it is tenant-scoped,
soft-delete-aware and batched, and that the pre-existing single lookup it
sits beside is unchanged.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from modules.sales.repositories.customer import CustomerRepository
from tests.integration.api.v1.reports.conftest import create_sales_customer


def test_returns_names_for_own_tenant_only(db_session: Session) -> None:
    company = uuid.uuid4()
    other = uuid.uuid4()
    mine = [create_sales_customer(db_session, company) for _ in range(3)]
    theirs = create_sales_customer(db_session, other)
    missing = uuid.uuid4()

    names = CustomerRepository(db_session).get_names_by_ids(
        company, {c.id for c in mine} | {theirs.id, missing}
    )

    assert names == {c.id: c.legal_name for c in mine}


def test_soft_deleted_customers_are_absent(db_session: Session) -> None:
    company = uuid.uuid4()
    kept = create_sales_customer(db_session, company)
    deleted = create_sales_customer(db_session, company)
    deleted.is_deleted = True
    db_session.commit()

    names = CustomerRepository(db_session).get_names_by_ids(
        company, {kept.id, deleted.id}
    )

    assert names == {kept.id: kept.legal_name}


def test_one_query_for_many_ids_and_none_for_empty(db_session: Session) -> None:
    company = uuid.uuid4()
    ids = {create_sales_customer(db_session, company).id for _ in range(5)}
    repo = CustomerRepository(db_session)
    statements: list[str] = []

    def count(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(statement)

    engine = db_session.get_bind()
    sa.event.listen(engine, "before_cursor_execute", count)
    try:
        assert len(repo.get_names_by_ids(company, ids)) == 5
        assert len(statements) == 1
        assert repo.get_names_by_ids(company, set()) == {}
        assert len(statements) == 1  # empty input never hits the database
    finally:
        sa.event.remove(engine, "before_cursor_execute", count)


def test_existing_single_lookup_is_unchanged(db_session: Session) -> None:
    company = uuid.uuid4()
    customer = create_sales_customer(db_session, company)
    repo = CustomerRepository(db_session)
    found = repo.get_by_id_or_none(customer.id, company)
    assert found is not None and found.legal_name == customer.legal_name
    assert repo.get_by_id_or_none(customer.id, uuid.uuid4()) is None
