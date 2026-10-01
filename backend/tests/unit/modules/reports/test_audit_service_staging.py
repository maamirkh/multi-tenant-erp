"""T183 — ``ReportsAuditService.record()`` stages (flushes) but never
commits; a caller rollback also rolls back the staged row."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.reports.models.reports_audit_log import ReportsAuditLog
from modules.reports.repositories.reports_audit_repository import (
    ReportsAuditRepository,
)
from modules.reports.services.audit_service import ReportsAuditService


def _count(db: Session, company_id: uuid.UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(ReportsAuditLog)
        .where(ReportsAuditLog.company_id == company_id)
    )
    return int(db.execute(stmt).scalar_one())


def _record(db: Session, company_id: uuid.UUID) -> ReportsAuditLog:
    return ReportsAuditService(ReportsAuditRepository(db)).record(
        company_id=company_id,
        entity_type="ReportExport",
        entity_id=uuid.uuid4(),
        action="EXPORTED",
        actor_id=uuid.uuid4(),
        report_key="sales.summary",
        filter_scope={"date_from": "2026-01-01"},
        export_format="CSV",
        row_count=3,
    )


def test_record_flushes_without_committing(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    company_id = uuid.uuid4()
    commits: list[str] = []
    original_commit = db_session.commit

    def tracking_commit() -> None:
        commits.append("commit")
        original_commit()

    monkeypatch.setattr(db_session, "commit", tracking_commit)
    log = _record(db_session, company_id)
    monkeypatch.undo()

    assert commits == []
    assert log.id is not None  # flushed — server-generated PK assigned
    assert _count(db_session, company_id) == 1  # visible inside the transaction


def test_caller_rollback_discards_staged_row(db_session: Session) -> None:
    company_id = uuid.uuid4()
    _record(db_session, company_id)
    assert _count(db_session, company_id) == 1

    db_session.rollback()

    assert _count(db_session, company_id) == 0


def test_caller_commit_persists_staged_row(db_session: Session) -> None:
    company_id = uuid.uuid4()
    _record(db_session, company_id)
    db_session.commit()

    rows = ReportsAuditRepository(db_session).list_for_company(company_id)
    assert len(rows) == 1
    assert rows[0].filter_scope == {"date_from": "2026-01-01"}
    assert rows[0].format == "CSV"
