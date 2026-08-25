"""[Phase 0 Exit Gate] Real-PostgreSQL migration cycle 061 -> 071 -> 061 -> 071.

Covers tasks.md T011 (Epic 10, Phase 0). Partial unique indexes and CHECK
constraints introduced by migrations 062-071 are PostgreSQL-specific;
SQLite cannot substitute (plan.md §31/§32 — "SQLite is NOT final proof of
PostgreSQL-specific behavior"). Verifies table/constraint/index presence
after each step of the cycle, on a real Docker Compose ``db`` service,
using the project's existing throwaway-per-test-database convention
(``pg_test_db``, shared with the Epic 9A migration-cycle test — never the
live ``devsphere_dev`` database).
"""

from __future__ import annotations

import sqlalchemy as sa

from .conftest import alembic_downgrade, alembic_upgrade, db_engine

_INSTALLMENTS_TABLES = (
    "installments_feature_flags",
    "installment_sequences",
    "installment_configurations",
    "installment_plan_templates",
    "installment_contracts",
    "installment_schedule_versions",
    "installment_schedule_lines",
    "installment_allocation_references",
    "installment_late_charges",
    "installment_idempotency_keys",
    "installment_audit_log",
)


def _existing_tables(engine: sa.engine.Engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        ).fetchall()
    return {row[0] for row in rows}


def _index_exists(engine: sa.engine.Engine, table: str, index: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT 1 FROM pg_indexes WHERE tablename = :table "
                "AND indexname = :index"
            ),
            {"table": table, "index": index},
        ).fetchone()
    return row is not None


def _check_constraint_exists(engine: sa.engine.Engine, name: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT 1 FROM pg_constraint WHERE conname = :name AND contype = 'c'"
            ),
            {"name": name},
        ).fetchone()
    return row is not None


def _fk_constraint_exists(engine: sa.engine.Engine, name: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT 1 FROM pg_constraint WHERE conname = :name AND contype = 'f'"
            ),
            {"name": name},
        ).fetchone()
    return row is not None


def _capability_row_exists(engine: sa.engine.Engine) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            sa.text("SELECT 1 FROM capabilities WHERE key = 'installments'")
        ).fetchone()
    return row is not None


def _installments_permission_count(engine: sa.engine.Engine) -> int:
    with engine.connect() as conn:
        return conn.execute(
            sa.text("SELECT count(*) FROM permissions WHERE id LIKE 'installments.%'")
        ).scalar_one()


def _alembic_version(engine: sa.engine.Engine) -> str:
    with engine.connect() as conn:
        return conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()


def _assert_head_state(engine: sa.engine.Engine) -> None:
    assert _alembic_version(engine) == "071"

    tables = _existing_tables(engine)
    for table in _INSTALLMENTS_TABLES:
        assert table in tables, f"{table} missing after upgrade to 071"

    # Partial unique indexes — the T001 correction (NULL-semantics-safe
    # config uniqueness), not a plain UNIQUE(company_id, branch_id).
    assert _index_exists(
        engine, "installment_configurations", "uq_installment_configurations_branch"
    )
    assert _index_exists(
        engine,
        "installment_configurations",
        "uq_installment_configurations_company_default",
    )

    # BR-INST-042/ADR-INST-03 one-non-terminal-contract-per-obligation.
    assert _index_exists(
        engine,
        "installment_contracts",
        "uq_installment_contracts_one_nonterminal_per_obligation",
    )

    # CHECK constraints.
    assert _check_constraint_exists(engine, "ck_installment_contracts_status")
    assert _check_constraint_exists(engine, "ck_installment_contracts_positive_amounts")
    assert _check_constraint_exists(engine, "ck_installment_schedule_versions_status")
    assert _check_constraint_exists(
        engine, "ck_installment_schedule_lines_positive_amount"
    )
    assert _check_constraint_exists(engine, "ck_installment_idempotency_status")

    # Deferred FK closing the installment_contracts <-> schedule_versions cycle.
    assert _fk_constraint_exists(
        engine, "fk_installment_contracts_active_schedule_version_id"
    )

    # Capability seed + permission backfill.
    assert _capability_row_exists(engine)
    assert _installments_permission_count(engine) == 16


class TestPhase0MigrationCyclePostgres:
    def test_full_up_down_up_cycle_on_real_postgres(self, pg_test_db: str) -> None:
        engine = db_engine(pg_test_db)

        # --- Step 1: 061 -> 071 ---
        alembic_upgrade(pg_test_db, "061")
        alembic_upgrade(pg_test_db, "071")
        _assert_head_state(engine)

        # --- Step 2: 071 -> 061 ---
        alembic_downgrade(pg_test_db, "061")
        assert _alembic_version(engine) == "061"

        tables = _existing_tables(engine)
        for table in _INSTALLMENTS_TABLES:
            assert table not in tables, f"{table} still present after downgrade to 061"
        assert not _capability_row_exists(engine)
        assert _installments_permission_count(engine) == 0

        # --- Step 3: 061 -> 071 again ---
        alembic_upgrade(pg_test_db, "071")
        _assert_head_state(engine)

        engine.dispose()

    def test_upgrade_from_empty_database_reaches_071(self, pg_test_db: str) -> None:
        """`alembic upgrade head` from a fresh empty database succeeds
        end-to-end (Phase 0 exit gate's explicit final clause)."""
        engine = db_engine(pg_test_db)
        alembic_upgrade(pg_test_db, "071")
        _assert_head_state(engine)
        engine.dispose()
