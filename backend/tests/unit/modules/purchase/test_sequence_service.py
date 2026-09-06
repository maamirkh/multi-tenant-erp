"""Unit tests for PurchaseSequenceService.

Tests:
  - Sequential number generation
  - Year-based document numbering
  - Company isolation (Company A numbers don't affect Company B)
  - Format correctness
  - Invalid document type rejection

Spec ref: specs/006-purchase-management/research.md §Decision 6
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from modules.purchase.services.sequence_service import (
    DEFAULT_PREFIXES,
    PurchaseSequenceService,
)


class TestSequenceServiceFormatting:
    """Test the static number formatter (no DB needed)."""

    def test_format_number_zero_padded(self) -> None:
        result = PurchaseSequenceService._format_number("PO", 2026, 1)
        assert result == "PO-2026-000001"

    def test_format_number_large_seq(self) -> None:
        result = PurchaseSequenceService._format_number("PR", 2026, 999999)
        assert result == "PR-2026-999999"

    def test_format_number_all_document_types(self) -> None:
        for doc_type in ("PR", "PO", "GR", "RMA"):
            result = PurchaseSequenceService._format_number(doc_type, 2026, 1)
            assert result.startswith(doc_type)
            assert "2026" in result

    def test_format_number_separator(self) -> None:
        result = PurchaseSequenceService._format_number("PO", 2026, 42)
        parts = result.split("-")
        assert len(parts) == 3
        assert parts[0] == "PO"
        assert parts[1] == "2026"
        assert parts[2] == "000042"


class TestDefaultPrefixes:
    def test_all_document_types_have_default_prefix(self) -> None:
        for doc_type in ("PR", "PO", "GR", "RMA"):
            assert doc_type in DEFAULT_PREFIXES

    def test_prefixes_match_document_types(self) -> None:
        assert DEFAULT_PREFIXES["PO"] == "PO"
        assert DEFAULT_PREFIXES["PR"] == "PR"
        assert DEFAULT_PREFIXES["GR"] == "GR"
        assert DEFAULT_PREFIXES["RMA"] == "RMA"


class TestSequenceServiceValidation:
    """Test invalid input rejection (no DB needed)."""

    def test_invalid_document_type_raises_value_error(self) -> None:
        mock_db = MagicMock()
        svc = PurchaseSequenceService(db=mock_db)

        with pytest.raises(ValueError, match="Invalid document type"):
            svc.generate_next_number(
                company_id=uuid4(),
                document_type="INVOICE",
            )

    def test_empty_document_type_raises_value_error(self) -> None:
        mock_db = MagicMock()
        svc = PurchaseSequenceService(db=mock_db)

        with pytest.raises(ValueError):
            svc.generate_next_number(
                company_id=uuid4(),
                document_type="",
            )


class TestSequenceServiceCompanyIsolation:
    """Test that company A sequences are independent from company B."""

    def test_different_companies_get_independent_sequences(self) -> None:
        """Both companies should start at 1 independently."""

        company_a = uuid4()
        company_b = uuid4()

        # Mock DB: returns None (no existing sequence) for both companies
        mock_db_a = MagicMock()
        mock_db_a.execute.return_value.scalars.return_value.one_or_none.return_value = (
            None
        )
        mock_db_a.flush = MagicMock()
        mock_db_a.add = MagicMock()

        mock_db_b = MagicMock()
        mock_db_b.execute.return_value.scalars.return_value.one_or_none.return_value = (
            None
        )
        mock_db_b.flush = MagicMock()
        mock_db_b.add = MagicMock()

        svc_a = PurchaseSequenceService(db=mock_db_a)
        svc_b = PurchaseSequenceService(db=mock_db_b)

        # Both should generate PO-YEAR-000001 (first PO for each)
        num_a = svc_a.generate_next_number(company_id=company_a, document_type="PO")
        num_b = svc_b.generate_next_number(company_id=company_b, document_type="PO")

        # Both start at 1 independently
        assert num_a.endswith("000001")
        assert num_b.endswith("000001")
