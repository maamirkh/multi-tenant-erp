"""T268 — ``EXPLAIN (ANALYZE, BUFFERS)`` evidence for Customer 360's four
section queries at representative scale, on real PostgreSQL.

Seeds a target tenant with ≥10K rows in every table a section reads (plus
a same-sized noise tenant, so ``company_id`` filtering is meaningful), runs
the real ``get_customer_360()``, captures every SQL statement it issues,
and re-runs each under ``EXPLAIN (ANALYZE, BUFFERS)`` with its real
parameters. Plans are written to ``$T268_PLAN_OUT`` when set.

**Resolved: Branch B.** Before migration 078, Installments' tenant-scoped
schedule-line read sequential-scanned every tenant's lines (120,000 of
150,000 rows discarded at 5 tenants); 078 adds
``ix_installment_schedule_lines_company_id`` and the read is now
index-served with zero cross-tenant rows touched.

Assertions (the Branch A/B decision): no query carrying a customer
predicate may sequential-scan a large table — each must be served by an
existing index. Company-wide reads (no customer predicate) are recorded,
not asserted: at 50% selectivity a sequential scan is the planner's
correct choice, and no index could change that.
The Installments section deliberately reads the tenant's whole bounded
population (``_DUE_STATE_POPULATION_BOUND``, filtered by customer in
Python — T163 note 5), so its company-wide reads are reported, not held
to the per-customer rule.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    db_engine,
    pg_test_db,
)

_SCALE = 12_000
_CUSTOMERS = 2_000
_CONTRACTS = 10_000
# The target tenant is 1/(1+N) of every table — representative multi-tenant
# selectivity rather than a single-tenant database.
_NOISE_TENANTS = 4
_CUSTOMER_PREDICATES = (
    ".customer_id =",
    ".customer_id IN",
    ".customer_ledger_id =",
    ".customer_ledger_id IN",
)
_PER_CUSTOMER_TABLES = (
    "sales_invoices",
    "accounting_customer_ledgers",
    "accounting_ar_transactions",
    "crm_opportunities",
)


def _seed(conn: sa.Connection, company: str, noise_tenants: list[str]) -> None:
    run = lambda sql, **kw: conn.execute(sa.text(sql), kw)  # noqa: E731
    run(
        """INSERT INTO customers (id, company_id, customer_code, category_id, legal_name)
           SELECT md5('t'||i)::uuid, :c, 'C'||i, gen_random_uuid(), 'Customer '||i
           FROM generate_series(0, :n - 1) i""",
        c=company,
        n=_CUSTOMERS,
    )
    for tenant, prefix in [(company, "t")] + [
        (n, f"n{i}") for i, n in enumerate(noise_tenants)
    ]:
        run(
            """INSERT INTO sales_invoices (company_id, invoice_number, customer_id,
                   invoice_date, due_date, currency_code, status, subtotal,
                   discount_amount, tax_amount, charges_amount, total_amount, version)
               SELECT :c, 'INV-'||i, md5(:p||(i % :k))::uuid, '2026-01-15', '2026-02-14',
                      'USD', 'ISSUED', 100, 0, 0, 0, 100, 1
               FROM generate_series(1, :n) i""",
            c=tenant,
            p=prefix,
            k=_CUSTOMERS,
            n=_SCALE,
        )
    for tenant, prefix in [(company, "t")] + [
        (n, f"n{i}") for i, n in enumerate(noise_tenants)
    ]:
        run(
            """INSERT INTO accounting_customer_ledgers (id, company_id, customer_id)
               SELECT md5(:p||'l'||i)::uuid, :c, md5(:p||i)::uuid
               FROM generate_series(0, :n - 1) i""",
            c=tenant,
            p=prefix,
            n=_CUSTOMERS,
        )
        run(
            """INSERT INTO accounting_ar_transactions (company_id, customer_ledger_id,
                   transaction_type, transaction_date, currency_code, exchange_rate,
                   amount_foreign, amount_base, outstanding_amount, status, due_date)
               SELECT :c, md5(:p||'l'||(i % :k))::uuid, 'INVOICE', DATE '2026-01-15',
                      'USD', 1, 100, 100, 100, 'OPEN', DATE '2026-02-14'
               FROM generate_series(1, :n) i""",
            c=tenant,
            p=prefix,
            k=_CUSTOMERS,
            n=_SCALE,
        )
    for tenant, prefix in [(company, "t")] + [
        (n, f"n{i}") for i, n in enumerate(noise_tenants)
    ]:
        pipeline = str(uuid.uuid4())
        stage = str(uuid.uuid4())
        run(
            "INSERT INTO crm_pipelines (id, company_id, name) VALUES (:p, :c, 'Main')",
            p=pipeline,
            c=tenant,
        )
        run(
            """INSERT INTO crm_pipeline_stages (id, company_id, pipeline_id, name,
                   sequence, probability) VALUES (:s, :c, :p, 'Qualify', 1, 50)""",
            s=stage,
            c=tenant,
            p=pipeline,
        )
        run(
            """INSERT INTO crm_opportunities (company_id, name, customer_id, owner_id,
                   pipeline_id, stage_id, currency_code, probability, value, status)
               SELECT :c, 'Opp '||i, md5(:x||(i % :k))::uuid, gen_random_uuid(), :p, :s,
                      'USD', 50, 250, 'OPEN'
               FROM generate_series(1, :n) i""",
            c=tenant,
            x=prefix,
            k=_CUSTOMERS,
            p=pipeline,
            s=stage,
            n=_SCALE,
        )
    for tenant, prefix in [(company, "t")] + [
        (n, f"n{i}") for i, n in enumerate(noise_tenants)
    ]:
        run(
            """INSERT INTO installment_contracts (id, company_id, contract_number,
                   customer_id, sales_invoice_id, contract_date, principal_amount,
                   down_payment_amount, contractual_total, installment_count, frequency,
                   first_due_date, maturity_date, currency_code, terms_snapshot, status)
               SELECT md5(:p||'k'||i)::uuid, :c, 'IC-'||i, md5(:p||(i % :k))::uuid,
                      gen_random_uuid(), DATE '2026-01-01', 300, 0, 300, 3, 'MONTHLY',
                      DATE '2026-02-01', DATE '2026-04-01', 'USD', '{}'::jsonb, 'ACTIVE'
               FROM generate_series(1, :n) i""",
            c=tenant,
            p=prefix,
            k=_CUSTOMERS,
            n=_CONTRACTS,
        )
        run(
            """INSERT INTO installment_schedule_versions (id, company_id, contract_id,
                   version_number, status)
               SELECT md5(:p||'v'||i)::uuid, :c, md5(:p||'k'||i)::uuid, 1, 'ACTIVE'
               FROM generate_series(1, :n) i""",
            c=tenant,
            p=prefix,
            n=_CONTRACTS,
        )
        run(
            """UPDATE installment_contracts SET active_schedule_version_id =
                   md5(:p||'v'||substr(contract_number, 4))::uuid WHERE company_id = :c""",
            c=tenant,
            p=prefix,
        )
        run(
            """INSERT INTO installment_schedule_lines (company_id, schedule_version_id,
                   sequence, due_date, scheduled_amount)
               SELECT :c, md5(:p||'v'||i)::uuid, s, DATE '2026-01-01' + (s * 30), 100
               FROM generate_series(1, :n) i, generate_series(1, 3) s""",
            c=tenant,
            p=prefix,
            n=_CONTRACTS,
        )
    for table in (
        "customers",
        "sales_invoices",
        "accounting_customer_ledgers",
        "accounting_ar_transactions",
        "crm_opportunities",
        "installment_contracts",
        "installment_schedule_versions",
        "installment_schedule_lines",
    ):
        conn.execute(sa.text(f"ANALYZE {table}"))


@pytest.fixture
def scaled_engine(pg_test_db: str) -> Iterator[sa.Engine]:  # noqa: F811
    alembic_upgrade(pg_test_db, "head")
    engine = db_engine(pg_test_db)
    try:
        yield engine
    finally:
        engine.dispose()


def test_customer_360_section_queries_use_indexes_at_scale(
    scaled_engine: sa.Engine,
) -> None:
    import modules.reports.registry.load_all  # noqa: F401 — populates ADAPTER_REGISTRY
    from modules.accounting.models.foundation import AccountingConfiguration
    from modules.crm.repositories.feature_flag_repository import (
        CrmFeatureFlagRepository,
    )
    from modules.crm.services.feature_flag_service import CrmFeatureFlagService
    from modules.installments.repositories.feature_flag import (
        InstallmentsFeatureFlagRepository,
    )
    from modules.installments.services.feature_flag_service import (
        InstallmentsFeatureFlagService,
    )
    from modules.reports.services.customer_360_service import get_customer_360

    company = uuid.uuid4()
    with scaled_engine.begin() as conn:
        _seed(conn, str(company), [str(uuid.uuid4()) for _ in range(_NOISE_TENANTS)])
        target = conn.execute(sa.text("SELECT md5('t0')::uuid")).scalar_one()

    db: Session = sessionmaker(bind=scaled_engine)()
    CrmFeatureFlagService(
        db=db, flag_repo=CrmFeatureFlagRepository(db), provisioning_service=None
    ).enable(company)
    InstallmentsFeatureFlagService(
        flag_repo=InstallmentsFeatureFlagRepository(db)
    ).enable(company)
    db.add(AccountingConfiguration(company_id=company, base_currency_code="USD"))
    db.commit()

    captured: list[tuple[str, dict[str, object]]] = []

    def capture(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        if statement.lstrip().upper().startswith("SELECT") and isinstance(
            parameters, dict
        ):
            captured.append((statement, dict(parameters)))

    sa.event.listen(scaled_engine, "before_cursor_execute", capture)
    try:
        result = get_customer_360(
            db,
            company_id=company,
            user_id=uuid.uuid4(),
            customer_id=target,
            user_roles=["super_admin"],
        )
    finally:
        sa.event.remove(scaled_engine, "before_cursor_execute", capture)
        db.close()

    # Every section genuinely ran against the scaled data.
    assert result.sales.state == "present"
    assert result.accounting_ar.state == "present"
    assert result.crm.state == "present"
    assert result.installments.state == "present"

    report: list[str] = []
    per_customer_seq_scans: list[str] = []
    per_customer_statements = 0
    with scaled_engine.connect() as conn:
        for statement, parameters in captured:
            touched = [
                t
                for t in _PER_CUSTOMER_TABLES
                + ("installment_contracts", "installment_schedule_lines")
                if t in statement
            ]
            if not touched:
                continue
            plan = "\n".join(
                row[0]
                for row in conn.exec_driver_sql(
                    "EXPLAIN (ANALYZE, BUFFERS) " + statement, parameters
                )
            )
            report.append(f"-- tables: {touched}\n{statement}\n{plan}\n")
            where = statement.split("WHERE", 1)[1] if "WHERE" in statement else ""
            if not any(p in where for p in _CUSTOMER_PREDICATES):
                # Company-wide read (e.g. Accounting's own get_customer_aging()
                # loads the tenant's ledgers; Installments reads its bounded
                # population) — recorded as evidence, not held to the
                # per-customer index rule.
                continue
            per_customer_statements += 1
            for table in _PER_CUSTOMER_TABLES:
                if f"Seq Scan on {table}" in plan:
                    per_customer_seq_scans.append(f"{table}: {statement[:160]}")

    out = os.environ.get("T268_PLAN_OUT")
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write("\n".join(report))
    assert report, "no section query was captured"
    # The per-customer rule must not pass vacuously.
    assert per_customer_statements >= 3, per_customer_statements
    assert per_customer_seq_scans == [], per_customer_seq_scans
    # Branch B (migration 078): the tenant-scoped schedule-line read is
    # index-served, so its cost no longer grows with other tenants' data.
    assert not any("Seq Scan on installment_schedule_lines" in r for r in report)
