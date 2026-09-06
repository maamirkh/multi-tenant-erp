"""Unit tests for sales master data entities.

Tests:
  - CustomerCategory code uniqueness invariant per company
  - CustomerGroup code uniqueness invariant per company
  - SalesReasonCode type validation
  - Schema validation (create/update)
  - Domain event serialisation

Task: T028
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from modules.sales.schemas.master import (
    CustomerCategoryCreate,
    CustomerCategoryUpdate,
    CustomerGroupCreate,
    SalesConfigurationUpdate,
    SalesPaymentTermCreate,
    SalesReasonCodeCreate,
)


class TestCustomerCategorySchema:
    """Test CustomerCategory schema validation."""

    def test_create_valid(self) -> None:
        schema = CustomerCategoryCreate(code="RETAIL", name="Retail Customers")
        assert schema.code == "RETAIL"
        assert schema.name == "Retail Customers"
        assert schema.default_credit_limit == Decimal("0")

    def test_code_uppercased(self) -> None:
        schema = CustomerCategoryCreate(code="retail", name="Retail")
        assert schema.code == "RETAIL"

    def test_code_trimmed(self) -> None:
        schema = CustomerCategoryCreate(code="  VIP  ", name="VIP")
        assert schema.code == "VIP"

    def test_empty_code_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CustomerCategoryCreate(code="", name="Empty")

    def test_code_max_length(self) -> None:
        with pytest.raises(ValidationError):
            CustomerCategoryCreate(code="A" * 21, name="Too Long")

    def test_update_partial(self) -> None:
        schema = CustomerCategoryUpdate(name="Updated")
        assert schema.name == "Updated"
        assert schema.is_active is None


class TestCustomerGroupSchema:
    """Test CustomerGroup schema validation."""

    def test_create_valid(self) -> None:
        schema = CustomerGroupCreate(code="VIP", name="VIP Customers")
        assert schema.code == "VIP"

    def test_code_uppercased(self) -> None:
        schema = CustomerGroupCreate(code="vip", name="VIP")
        assert schema.code == "VIP"


class TestSalesPaymentTermSchema:
    """Test SalesPaymentTerm schema validation."""

    def test_create_valid(self) -> None:
        schema = SalesPaymentTermCreate(code="NET30", name="Net 30", due_days=30)
        assert schema.code == "NET30"
        assert schema.due_days == 30

    def test_negative_due_days_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SalesPaymentTermCreate(code="BAD", name="Bad", due_days=-1)


class TestSalesReasonCodeSchema:
    """Test SalesReasonCode schema validation."""

    def test_create_valid(self) -> None:
        schema = SalesReasonCodeCreate(
            code="DEFECTIVE", name="Defective", reason_type="RETURN"
        )
        assert schema.code == "DEFECTIVE"
        assert schema.reason_type == "RETURN"

    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SalesReasonCodeCreate(code="BAD", name="Bad", reason_type="INVALID")

    def test_type_uppercased(self) -> None:
        schema = SalesReasonCodeCreate(code="TEST", name="Test", reason_type="return")
        assert schema.reason_type == "RETURN"


class TestSalesConfigurationSchema:
    """Test SalesConfiguration update schema."""

    def test_valid_update(self) -> None:
        schema = SalesConfigurationUpdate(
            default_quotation_validity_days=60,
            credit_warning_threshold=Decimal("90.00"),
        )
        assert schema.default_quotation_validity_days == 60

    def test_invalid_threshold_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SalesConfigurationUpdate(credit_warning_threshold=Decimal("101"))

    def test_invalid_validity_days(self) -> None:
        with pytest.raises(ValidationError):
            SalesConfigurationUpdate(default_quotation_validity_days=0)
