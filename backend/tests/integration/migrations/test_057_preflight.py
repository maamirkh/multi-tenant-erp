"""Real-PostgreSQL tests for migration 057's suspended-company preflight guard.

Covers tasks.md T024, T025, T026, T028 (Gate A). Migration 057 must refuse
to proceed — creating no column and no constraint — if any
``companies.status = 'suspended'`` row already exists, because that row's
true prior lifecycle status is unrecoverable and must never be fabricated
(plan.md §33.1, ADR-12).
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from .conftest import alembic_downgrade, alembic_upgrade, db_engine


def _insert_suspended_company(engine: sa.engine.Engine) -> str:
    """Insert a minimal users + companies(status='suspended') row.

    Returns the company's slug (used to assert it's named in the error).
    """
    user_id = uuid.uuid4()
    company_id = uuid.uuid4()
    slug = f"suspended-co-{uuid.uuid4().hex[:8]}"
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO users (id, email, display_name) "
                "VALUES (:id, :email, :name)"
            ),
            {"id": user_id, "email": f"{user_id}@example.test", "name": "Test Owner"},
        )
        conn.execute(
            sa.text(
                "INSERT INTO companies (id, legal_name, slug, status, owner_id, "
                "email) VALUES (:id, :legal_name, :slug, 'suspended', "
                ":owner_id, :email)"
            ),
            {
                "id": company_id,
                "legal_name": "Suspended Test Co",
                "slug": slug,
                "owner_id": user_id,
                "email": f"{company_id}@example.test",
            },
        )
    return slug


def _companies_column_names(engine: sa.engine.Engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'companies'"
            )
        ).fetchall()
    return {row[0] for row in rows}


def _current_alembic_version(engine: sa.engine.Engine) -> str:
    with engine.connect() as conn:
        return conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()


def _companies_check_constraint_names(engine: sa.engine.Engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name = 'companies' AND constraint_type = 'CHECK'"
            )
        ).fetchall()
    return {row[0] for row in rows}


class TestMigration057PreflightSuccess:
    """T024 — clean database with no suspended companies -> 057 succeeds."""

    def test_057_succeeds_with_no_suspended_companies(self, pg_test_db: str) -> None:
        alembic_upgrade(pg_test_db, "056")
        engine = db_engine(pg_test_db)

        alembic_upgrade(pg_test_db, "057")

        columns = _companies_column_names(engine)
        assert "pre_suspension_status" in columns
        assert "access_invalidated_at" in columns

        checks = _companies_check_constraint_names(engine)
        assert "ck_companies_pre_suspension_status_presence" in checks
        assert "ck_companies_pre_suspension_status_domain" in checks
        engine.dispose()


class TestMigration057PreflightRefusal:
    """T025 — a pre-existing suspended row makes 057 refuse to proceed."""

    def test_057_refuses_with_pre_existing_suspended_row(self, pg_test_db: str) -> None:
        alembic_upgrade(pg_test_db, "056")
        engine = db_engine(pg_test_db)
        slug = _insert_suspended_company(engine)

        with pytest.raises(RuntimeError) as exc_info:
            alembic_upgrade(pg_test_db, "057")

        message = str(exc_info.value)
        assert slug in message
        assert "cannot proceed" in message
        assert "MUST NOT be guessed" in message
        # Remediation options must be named, not just "an error occurred".
        assert "active" in message and "inactive" in message
        engine.dispose()


class TestMigration057PreflightNoPartialState:
    """T026 — a refused 057 leaves the database byte-for-byte unchanged."""

    def test_refused_057_leaves_no_partial_state(self, pg_test_db: str) -> None:
        alembic_upgrade(pg_test_db, "056")
        engine = db_engine(pg_test_db)
        _insert_suspended_company(engine)

        columns_before = _companies_column_names(engine)
        checks_before = _companies_check_constraint_names(engine)
        version_before = _current_alembic_version(engine)

        with pytest.raises(RuntimeError):
            alembic_upgrade(pg_test_db, "057")

        columns_after = _companies_column_names(engine)
        checks_after = _companies_check_constraint_names(engine)
        version_after = _current_alembic_version(engine)

        assert columns_after == columns_before
        assert "pre_suspension_status" not in columns_after
        assert "access_invalidated_at" not in columns_after
        assert checks_after == checks_before
        # Alembic's own transaction wraps the whole upgrade() — a raised
        # exception must roll back the version-stamp bump too.
        assert version_after == version_before == "056"
        engine.dispose()


class TestMigration057RemediationPath:
    """T028 [Gate A] — after remediating a suspended row, 057 succeeds and
    the full migration cycle completes (proves the documented operator
    remediation path actually works, not just that it's documented)."""

    def test_remediation_then_057_succeeds_and_cycle_completes(
        self, pg_test_db: str
    ) -> None:
        alembic_upgrade(pg_test_db, "056")
        engine = db_engine(pg_test_db)
        slug = _insert_suspended_company(engine)

        with pytest.raises(RuntimeError):
            alembic_upgrade(pg_test_db, "057")

        # Operator remediation: set the row's status back to its true prior
        # value. Never inferred/guessed by the migration itself — a human
        # (this test, standing in for the operator) makes the decision.
        with engine.begin() as conn:
            conn.execute(
                sa.text("UPDATE companies SET status = 'active' WHERE slug = :slug"),
                {"slug": slug},
            )

        alembic_upgrade(pg_test_db, "057")
        columns = _companies_column_names(engine)
        assert "pre_suspension_status" in columns
        assert "access_invalidated_at" in columns

        # Re-run continues cleanly through the rest of the Epic 9A chain.
        # Pinned to "061" (Epic 9A's own last migration), not "head" — later
        # epics (e.g. Epic 10, migrations 062+) legitimately extend the
        # chain past 061, and this test's concern is only that Epic 9A's
        # own chain (through 061) still applies cleanly, not the platform's
        # current overall head.
        alembic_upgrade(pg_test_db, "061")
        assert _current_alembic_version(engine) == "061"

        # Up/down/up on real PostgreSQL (partial unique indexes and CHECK
        # constraints are Postgres-specific; SQLite cannot substitute).
        alembic_downgrade(pg_test_db, "056")
        assert _current_alembic_version(engine) == "056"
        alembic_upgrade(pg_test_db, "061")
        assert _current_alembic_version(engine) == "061"
        engine.dispose()
