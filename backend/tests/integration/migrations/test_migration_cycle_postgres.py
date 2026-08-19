"""[Gate A] Real-PostgreSQL migration cycle 056 -> 061 -> 056 -> 061.

Covers tasks.md T027. Partial unique indexes and CHECK constraints
introduced by migrations 057-061 are PostgreSQL-specific; SQLite cannot
substitute (plan.md §32). Verifies ``\\dt platform_*``, ``\\d companies``,
``\\d subscriptions``-equivalent catalogue state after each step of the
cycle, on a real Docker Compose ``db`` service.
"""

from __future__ import annotations

import sqlalchemy as sa

from .conftest import alembic_downgrade, alembic_upgrade, db_engine

_PLATFORM_TABLES = (
    "platform_administrators",
    "platform_roles",
    "platform_permissions",
    "platform_role_permissions",
    "platform_admin_role_assignments",
    "platform_sessions",
    "platform_refresh_tokens",
    "platform_audit_events",
    "capabilities",
    "plans",
    "plan_capabilities",
    "subscriptions",
    "quota_definitions",
    "plan_quotas",
    "tenant_quota_overrides",
    "entitlement_overrides",
    "usage_records",
    "ai_credit_ledger_entries",
    "support_access_grants",
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


def _companies_columns(engine: sa.engine.Engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'companies'"
            )
        ).fetchall()
    return {row[0] for row in rows}


def _subscriptions_partial_index_exists(engine: sa.engine.Engine) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT 1 FROM pg_indexes WHERE tablename = 'subscriptions' "
                "AND indexname = 'uq_subscriptions_company_active'"
            )
        ).fetchone()
    return row is not None


def _alembic_version(engine: sa.engine.Engine) -> str:
    with engine.connect() as conn:
        return conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()


class TestGateAMigrationCyclePostgres:
    def test_full_up_down_up_cycle_on_real_postgres(self, pg_test_db: str) -> None:
        engine = db_engine(pg_test_db)

        # --- Step 1: 056 -> 061 ---
        alembic_upgrade(pg_test_db, "056")
        alembic_upgrade(pg_test_db, "061")
        assert _alembic_version(engine) == "061"

        tables = _existing_tables(engine)
        for table in _PLATFORM_TABLES:
            assert table in tables, f"{table} missing after upgrade to 061"

        companies_cols = _companies_columns(engine)
        assert "pre_suspension_status" in companies_cols
        assert "access_invalidated_at" in companies_cols
        assert "subscription_id" in companies_cols
        assert _subscriptions_partial_index_exists(engine)

        # --- Step 2: 061 -> 056 ---
        alembic_downgrade(pg_test_db, "056")
        assert _alembic_version(engine) == "056"

        tables = _existing_tables(engine)
        for table in _PLATFORM_TABLES:
            assert table not in tables, f"{table} still present after downgrade to 056"

        companies_cols = _companies_columns(engine)
        assert "pre_suspension_status" not in companies_cols
        assert "access_invalidated_at" not in companies_cols
        # subscription_id predates Epic 9A — downgrade must NOT drop it,
        # only its FK constraint (T017's acceptance).
        assert "subscription_id" in companies_cols

        # --- Step 3: 056 -> 061 again ---
        alembic_upgrade(pg_test_db, "061")
        assert _alembic_version(engine) == "061"

        tables = _existing_tables(engine)
        for table in _PLATFORM_TABLES:
            assert table in tables, f"{table} missing after second upgrade to 061"

        companies_cols = _companies_columns(engine)
        assert "pre_suspension_status" in companies_cols
        assert "access_invalidated_at" in companies_cols
        assert _subscriptions_partial_index_exists(engine)

        engine.dispose()
