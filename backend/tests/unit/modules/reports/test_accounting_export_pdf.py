"""T063 — ``export_pdf()`` delegates to Accounting's existing
``report_export.py::export_to_pdf()`` for its four PDF-eligible keys
(narrowed from spec's stated six — see ``accounting_adapter.py``'s
``_PDF_ELIGIBLE_KEYS`` docstring for the genuine template-shape mismatch
discovered for AR/AP aging during implementation).
"""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from modules.reports.schemas.accounting import (
    ArAgingFilter,
    BalanceSheetFilter,
    GlFilter,
)
from modules.reports.services.adapters.accounting_adapter import AccountingAdapter
from tests.integration.api.v1.accounting.test_reports_api import _setup


def test_balance_sheet_exports_to_pdf_bytes(db_session: Session) -> None:
    company_id = uuid.uuid4()
    fixture = _setup(db_session, company_id)

    adapter = AccountingAdapter()
    pdf_bytes = adapter.export_pdf(
        db_session,
        company_id,
        "accounting.balance_sheet",
        BalanceSheetFilter(as_of_date=fixture["today"]),
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")


def test_gl_is_not_pdf_eligible() -> None:
    with pytest.raises(ValueError, match="not PDF-eligible"):
        AccountingAdapter().export_pdf(
            MagicMock(),
            uuid.uuid4(),
            "accounting.gl",
            GlFilter(),
        )


def test_ar_aging_is_not_pdf_eligible_due_to_template_mismatch() -> None:
    """Documents the deliberate narrowing: CSV/XLSX remain available for
    ``ar_aging`` (see ``count_export_rows``/``iter_export_rows`` tests) —
    only PDF is withheld, since no correct template exists for it."""
    with pytest.raises(ValueError, match="not PDF-eligible"):
        AccountingAdapter().export_pdf(
            MagicMock(),
            uuid.uuid4(),
            "accounting.ar_aging",
            ArAgingFilter(as_of_date=date(2026, 1, 1)),
        )
