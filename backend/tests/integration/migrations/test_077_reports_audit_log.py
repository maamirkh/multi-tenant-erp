"""[Epic 11, Phase 6] T182 — real-PostgreSQL migration cycle 076 -> 077 ->
076 -> 077 for ``reports_audit_log`` (tasks.md names this ``076``; it was
renumbered to ``077`` because Phase 1's saved-views table already holds
``076`` — see the migration's docstring), plus a JSONB round-trip on the
``before``/``after``/``filter_scope`` columns."""

from __future__ import annotations

import json
import uuid

import sqlalchemy as sa

from .conftest import alembic_downgrade, alembic_upgrade, db_engine

_EXPECTED_INDEXES = {
    "ix_reports_audit_log_company_id",
    "ix_reports_audit_log_company_created_at",
    "ix_reports_audit_log_company_actor",
}


def _table_exists(engine: sa.engine.Engine) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'reports_audit_log'"
            )
        ).fetchone()
    return row is not None


def _indexes(engine: sa.engine.Engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'reports_audit_log'"
            )
        ).fetchall()
    return {str(r[0]) for r in rows}


def _column_types(engine: sa.engine.Engine) -> dict[str, str]:
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = 'reports_audit_log'"
            )
        ).fetchall()
    return {str(r[0]): str(r[1]) for r in rows}


def _version(engine: sa.engine.Engine) -> str:
    with engine.connect() as conn:
        return str(
            conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
        )


def _assert_head(engine: sa.engine.Engine) -> None:
    assert _version(engine) == "077"
    assert _table_exists(engine)
    assert _EXPECTED_INDEXES <= _indexes(engine)
    types = _column_types(engine)
    for column in ("before", "after", "filter_scope"):
        assert types[column] == "jsonb", column
    assert types["row_count"] == "integer"


class TestReportsAuditLogMigrationPostgres:
    def test_up_down_up_cycle(self, pg_test_db: str) -> None:
        engine = db_engine(pg_test_db)
        try:
            alembic_upgrade(pg_test_db, "077")
            _assert_head(engine)

            alembic_downgrade(pg_test_db, "076")
            assert _version(engine) == "076"
            assert not _table_exists(engine)

            alembic_upgrade(pg_test_db, "077")
            _assert_head(engine)
        finally:
            engine.dispose()

    def test_jsonb_round_trip(self, pg_test_db: str) -> None:
        engine = db_engine(pg_test_db)
        try:
            alembic_upgrade(pg_test_db, "077")
            company_id = uuid.uuid4()
            filter_scope = {"date_from": "2026-01-01", "nested": {"ids": [1, 2]}}
            after = {"name": "View", "grouping": None}
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT INTO reports_audit_log "
                        "(company_id, entity_type, entity_id, action, actor_id, "
                        " after, report_key, filter_scope, format, row_count) "
                        "VALUES (:company_id, 'ReportExport', :entity_id, 'EXPORTED', "
                        " :actor_id, CAST(:after AS jsonb), 'sales.summary', "
                        " CAST(:filter_scope AS jsonb), 'CSV', 42)"
                    ),
                    {
                        "company_id": company_id,
                        "entity_id": uuid.uuid4(),
                        "actor_id": uuid.uuid4(),
                        "after": json.dumps(after),
                        "filter_scope": json.dumps(filter_scope),
                    },
                )
            with engine.connect() as conn:
                row = conn.execute(
                    sa.text(
                        "SELECT filter_scope, after, before, row_count, is_deleted, "
                        "id IS NOT NULL, created_at IS NOT NULL "
                        "FROM reports_audit_log WHERE company_id = :company_id"
                    ),
                    {"company_id": company_id},
                ).one()
            assert row[0] == filter_scope
            assert row[1] == after
            assert row[2] is None
            assert row[3] == 42
            assert row[4] is False
            assert row[5] is True and row[6] is True
        finally:
            engine.dispose()
