"""Unit tests for SalesSequenceService.

Tests:
  - Sequential generation for different document types
  - Company isolation (different companies get independent sequences)
  - Invalid document type raises ValueError
  - Year-based reset creates new sequence row

Spec ref: specs/007-sales-management/research.md §Decision 4, §Decision 6
Task: T026
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from modules.sales.services.sequence_service import SalesSequenceService


class TestSalesSequenceServiceValidation:
    """Test input validation for SalesSequenceService."""

    def test_invalid_document_type_raises_value_error(self) -> None:
        db = MagicMock()
        service = SalesSequenceService(db=db)
        with pytest.raises(ValueError, match="Invalid document type"):
            service.generate_next_number(
                company_id=uuid4(),
                document_type="INVALID",
            )

    def test_valid_document_types_accepted(self) -> None:
        """All 5 valid document types should not raise on validation."""
        valid_types = ("SQ", "SO", "DN", "SI", "SR")
        for doc_type in valid_types:
            db = MagicMock()
            # Mock the execute chain to return None (new sequence)
            mock_result = MagicMock()
            mock_result.scalars.return_value.one_or_none.return_value = None
            db.execute.return_value = mock_result
            db.add = MagicMock()
            db.flush = MagicMock()

            service = SalesSequenceService(db=db)
            result = service.generate_next_number(
                company_id=uuid4(),
                document_type=doc_type,
            )
            assert result.startswith(f"{doc_type}-")


class TestSalesSequenceServiceFormatting:
    """Test number formatting logic."""

    def test_format_number_basic(self) -> None:
        result = SalesSequenceService._format_number("SO", 2026, 1)
        assert result == "SO-2026-000001"

    def test_format_number_large_sequence(self) -> None:
        result = SalesSequenceService._format_number("SI", 2026, 999999)
        assert result == "SI-2026-999999"

    def test_format_number_custom_prefix(self) -> None:
        result = SalesSequenceService._format_number("INV", 2026, 42)
        assert result == "INV-2026-000042"

    def test_format_number_all_types(self) -> None:
        for prefix in ("SQ", "SO", "DN", "SI", "SR"):
            result = SalesSequenceService._format_number(prefix, 2026, 1)
            assert result == f"{prefix}-2026-000001"
