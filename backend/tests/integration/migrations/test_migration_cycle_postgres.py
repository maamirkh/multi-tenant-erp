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

    def test_downgrade_after_a_populated_subscription_id_re_upgrades_clean(
        self, pg_test_db: str
    ) -> None:
        """Regression guard for a real defect found live during Epic 9A
        Phase 17 (T214): this test's sibling above never populates
        ``companies.subscription_id`` before downgrading, so it never
        exercised the one scenario Epic 9A's own rollout creates — a
        company whose ``subscription_id`` genuinely points at a row in
        ``subscriptions``. Migration 058's original ``downgrade()``
        dropped the FK constraint and the ``subscriptions`` table but
        never reset that dangling value back to NULL, so the *next*
        ``upgrade head`` failed re-adding ``fk_companies_subscription_id``
        (``ForeignKeyViolation`` — the stale UUID no longer resolves to
        anything). Fixed by adding an explicit
        ``UPDATE companies SET subscription_id = NULL`` before dropping
        ``subscriptions`` in the downgrade path.
        """
        engine = db_engine(pg_test_db)
        alembic_upgrade(pg_test_db, "061")

        with engine.begin() as conn:
            user_id = conn.execute(
                sa.text(
                    "INSERT INTO users (email, display_name) "
                    "VALUES ('t214-regress@example.com', 'T214 Regress') "
                    "RETURNING id"
                )
            ).scalar_one()
            company_id = conn.execute(
                sa.text(
                    "INSERT INTO companies (legal_name, slug, owner_id, email) "
                    "VALUES ('T214 Regress Co', 't214-regress-co', :owner_id, "
                    "'t214-regress-co@example.com') RETURNING id"
                ),
                {"owner_id": user_id},
            ).scalar_one()
            admin_id = conn.execute(
                sa.text(
                    "INSERT INTO platform_administrators (user_id) "
                    "VALUES (:user_id) RETURNING id"
                ),
                {"user_id": user_id},
            ).scalar_one()
            plan_id = conn.execute(
                sa.text(
                    "INSERT INTO plans (code, name, status) "
                    "VALUES ('t214-regress-plan', 'T214 Regress Plan', 'published') "
                    "RETURNING id"
                )
            ).scalar_one()
            subscription_id = conn.execute(
                sa.text(
                    "INSERT INTO subscriptions "
                    "(company_id, plan_id, status, effective_date, actor_id) "
                    "VALUES (:company_id, :plan_id, 'active', CURRENT_DATE, :actor_id) "
                    "RETURNING id"
                ),
                {
                    "company_id": company_id,
                    "plan_id": plan_id,
                    "actor_id": admin_id,
                },
            ).scalar_one()
            conn.execute(
                sa.text(
                    "UPDATE companies SET subscription_id = :sub_id WHERE id = :company_id"
                ),
                {"sub_id": subscription_id, "company_id": company_id},
            )

        # The exact sequence that broke pre-fix: downgrade with a
        # genuinely populated subscription_id, then upgrade again.
        alembic_downgrade(pg_test_db, "056")

        with engine.connect() as conn:
            remaining = conn.execute(
                sa.text("SELECT subscription_id FROM companies WHERE id = :id"),
                {"id": company_id},
            ).scalar_one()
        assert remaining is None, (
            "subscription_id must be reset to NULL on downgrade, matching "
            "the column's pre-058 invariant"
        )

        # This is the line that raised ForeignKeyViolation before the fix.
        alembic_upgrade(pg_test_db, "061")
        assert _alembic_version(engine) == "061"

        engine.dispose()
