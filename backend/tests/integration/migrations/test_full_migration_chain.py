"""[Epic 11, Phase 10] T266 — the complete Epic 11 migration chain on real
PostgreSQL: a clean ``alembic upgrade head`` covering 073 → 074 → 075 →
076 → 077 → 078, a downgrade to 072 (pre-Epic-11) that removes every Epic 11
object, and a re-upgrade that restores them identically.

``077`` is the reports audit log (Phase 6, renumbered from T179's
``076``); ``078`` is T268's Branch B index on
``installment_schedule_lines(company_id)`` (renumbered from ``077``).
"""

from __future__ import annotations

import sqlalchemy as sa

from .conftest import alembic_downgrade, alembic_upgrade, db_engine

_EPIC_11_TABLES = {"reports_feature_flags", "saved_report_views", "reports_audit_log"}
_EPIC_11_INDEXES = {
    "saved_report_views": {
        "ix_saved_report_views_company_user",
        "ix_saved_report_views_company_report_key",
    },
    "reports_audit_log": {
        "ix_reports_audit_log_company_id",
        "ix_reports_audit_log_company_created_at",
        "ix_reports_audit_log_company_actor",
    },
    "installment_schedule_lines": {"ix_installment_schedule_lines_company_id"},
}


def _scalar(engine: sa.engine.Engine, sql: str) -> object:
    with engine.connect() as conn:
        return conn.execute(sa.text(sql)).scalar()


def _tables(engine: sa.engine.Engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        ).fetchall()
    return {str(r[0]) for r in rows}


def _indexes(engine: sa.engine.Engine, table: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text("SELECT indexname FROM pg_indexes WHERE tablename = :t"),
            {"t": table},
        ).fetchall()
    return {str(r[0]) for r in rows}


def _snapshot(engine: sa.engine.Engine) -> dict[str, object]:
    return {
        "version": _scalar(engine, "SELECT version_num FROM alembic_version"),
        "tables": _tables(engine) & _EPIC_11_TABLES,
        "indexes": {t: _indexes(engine, t) for t in _EPIC_11_INDEXES},
        "capability": _scalar(
            engine, "SELECT count(*) FROM capabilities WHERE key = 'reports'"
        ),
        "permissions": _scalar(
            engine, "SELECT count(*) FROM permissions WHERE id LIKE 'reports.%'"
        ),
        "default_grants": _scalar(
            engine,
            "SELECT count(*) FROM role_permissions WHERE permission_id LIKE 'reports.%'",
        ),
    }


def _assert_head(snapshot: dict[str, object]) -> None:
    assert snapshot["version"] == "078"
    assert snapshot["tables"] == _EPIC_11_TABLES
    indexes = snapshot["indexes"]
    assert isinstance(indexes, dict)
    for table, expected in _EPIC_11_INDEXES.items():
        assert expected <= indexes[table], table
    assert snapshot["capability"] == 1
    assert snapshot["permissions"] == 16
    assert snapshot["default_grants"] == 0  # FR-RPT-243: never a default grant


class TestEpic11MigrationChainPostgres:
    def test_upgrade_head_downgrade_072_reupgrade(self, pg_test_db: str) -> None:
        engine = db_engine(pg_test_db)
        try:
            alembic_upgrade(pg_test_db, "head")
            first = _snapshot(engine)
            _assert_head(first)

            alembic_downgrade(pg_test_db, "072")
            assert _scalar(engine, "SELECT version_num FROM alembic_version") == "072"
            assert _tables(engine) & _EPIC_11_TABLES == set()
            assert "ix_installment_schedule_lines_company_id" not in _indexes(
                engine, "installment_schedule_lines"
            )
            assert (
                _scalar(
                    engine, "SELECT count(*) FROM capabilities WHERE key = 'reports'"
                )
                == 0
            )
            assert (
                _scalar(
                    engine, "SELECT count(*) FROM permissions WHERE id LIKE 'reports.%'"
                )
                == 0
            )

            alembic_upgrade(pg_test_db, "head")
            second = _snapshot(engine)
            _assert_head(second)
            assert second == first
        finally:
            engine.dispose()

    def test_each_epic_11_revision_steps_up_and_down(self, pg_test_db: str) -> None:
        engine = db_engine(pg_test_db)
        try:
            alembic_upgrade(pg_test_db, "072")
            for revision in ("073", "074", "075", "076", "077", "078"):
                alembic_upgrade(pg_test_db, revision)
                assert (
                    _scalar(engine, "SELECT version_num FROM alembic_version")
                    == revision
                )
            for revision in ("077", "076", "075", "074", "073", "072"):
                alembic_downgrade(pg_test_db, revision)
                assert (
                    _scalar(engine, "SELECT version_num FROM alembic_version")
                    == revision
                )
        finally:
            engine.dispose()
