"""[Epic 11, Phase 1] Real-PostgreSQL migration cycle 072 -> 075 -> 072 -> 075.

Covers tasks.md T038 — verifies migrations 073 (Phase 0's
``reports_feature_flags`` table), 074 (``reports`` capability seed), and
075 (``reports.*`` permission catalog seed) upgrade/downgrade/round-trip
cleanly against real Postgres, and that the permission seed contains
exactly the 16 ``reports.*`` codes with **zero** ``role_permissions``
grants (FR-RPT-243 — deliberately distinct from Installments' 071
precedent, which does grant default roles).
"""

from __future__ import annotations

import sqlalchemy as sa

from .conftest import alembic_downgrade, alembic_upgrade, db_engine


def _table_exists(engine: sa.engine.Engine, table: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = :table"
            ),
            {"table": table},
        ).fetchone()
    return row is not None


def _capability_row_exists(engine: sa.engine.Engine) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            sa.text("SELECT 1 FROM capabilities WHERE key = 'reports'")
        ).fetchone()
    return row is not None


def _reports_permission_count(engine: sa.engine.Engine) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                sa.text("SELECT count(*) FROM permissions WHERE id LIKE 'reports.%'")
            ).scalar_one()
        )


def _reports_role_permission_grant_count(engine: sa.engine.Engine) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                sa.text(
                    "SELECT count(*) FROM role_permissions "
                    "WHERE permission_id LIKE 'reports.%'"
                )
            ).scalar_one()
        )


def _alembic_version(engine: sa.engine.Engine) -> str:
    with engine.connect() as conn:
        version = conn.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar()
        assert version is not None
        return str(version)


def _assert_head_state(engine: sa.engine.Engine) -> None:
    assert _alembic_version(engine) == "075"
    assert _table_exists(engine, "reports_feature_flags")
    assert _capability_row_exists(engine)
    assert _reports_permission_count(engine) == 16
    # FR-RPT-243: no default role mapping is ever seeded for reports.*.
    assert _reports_role_permission_grant_count(engine) == 0


class TestReportsPhase1MigrationCyclePostgres:
    def test_full_up_down_up_cycle_on_real_postgres(self, pg_test_db: str) -> None:
        engine = db_engine(pg_test_db)

        alembic_upgrade(pg_test_db, "072")
        alembic_upgrade(pg_test_db, "075")
        _assert_head_state(engine)

        alembic_downgrade(pg_test_db, "072")
        assert _alembic_version(engine) == "072"
        assert not _table_exists(engine, "reports_feature_flags")
        assert not _capability_row_exists(engine)
        assert _reports_permission_count(engine) == 0

        alembic_upgrade(pg_test_db, "075")
        _assert_head_state(engine)

        engine.dispose()

    def test_upgrade_from_empty_database_reaches_075(self, pg_test_db: str) -> None:
        engine = db_engine(pg_test_db)
        alembic_upgrade(pg_test_db, "075")
        _assert_head_state(engine)
        engine.dispose()
