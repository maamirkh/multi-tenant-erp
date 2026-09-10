"""Unit tests for Supplier domain events.

Tests:
  - All 7 events are instantiable via factory class method
  - All events are JSON-serialisable (to_dict())
  - Correct event_type string on each event
  - Correct aggregate_type ("Supplier") on each event
  - Fields are present on each event

Task: T050
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest

from modules.purchase.events.supplier_events import (
    SupplierActivated,
    SupplierArchived,
    SupplierBlocked,
    SupplierCreated,
    SupplierDeactivated,
    SupplierReactivated,
    SupplierUpdated,
)


def _sid() -> UUID:
    return uuid4()


def _cid() -> UUID:
    return uuid4()


class TestSupplierCreated:
    def test_create_factory(self) -> None:
        sid, cid = _sid(), _cid()
        evt = SupplierCreated.create(
            supplier_id=sid, company_id=cid, supplier_code="SUP-001", legal_name="Acme"
        )
        assert evt.event_type == "supplier.created"
        assert evt.aggregate_type == "Supplier"
        assert evt.aggregate_id == str(sid)
        assert evt.company_id == str(cid)
        assert evt.supplier_code == "SUP-001"
        assert evt.legal_name == "Acme"

    def test_to_dict_serialisable(self) -> None:
        evt = SupplierCreated.create(
            supplier_id=_sid(), company_id=_cid(), supplier_code="S", legal_name="L"
        )
        d = evt.to_dict()
        assert isinstance(d, dict)
        json.dumps(d)  # must not raise
        assert d["event_type"] == "supplier.created"
        assert d["supplier_code"] == "S"
        assert d["legal_name"] == "L"


class TestSupplierUpdated:
    def test_create_factory(self) -> None:
        sid, cid = _sid(), _cid()
        evt = SupplierUpdated.create(
            supplier_id=sid, company_id=cid, changed_fields=["legal_name", "website"]
        )
        assert evt.event_type == "supplier.updated"
        assert evt.aggregate_type == "Supplier"
        assert evt.changed_fields == ["legal_name", "website"]

    def test_to_dict_serialisable(self) -> None:
        evt = SupplierUpdated.create(
            supplier_id=_sid(), company_id=_cid(), changed_fields=["notes"]
        )
        d = evt.to_dict()
        json.dumps(d)
        assert d["changed_fields"] == ["notes"]

    def test_empty_changed_fields(self) -> None:
        evt = SupplierUpdated.create(
            supplier_id=_sid(), company_id=_cid(), changed_fields=[]
        )
        assert evt.changed_fields == []


class TestSupplierActivated:
    def test_create_factory(self) -> None:
        sid, cid = _sid(), _cid()
        evt = SupplierActivated.create(
            supplier_id=sid, company_id=cid, previous_status="DRAFT"
        )
        assert evt.event_type == "supplier.activated"
        assert evt.aggregate_type == "Supplier"
        assert evt.previous_status == "DRAFT"

    def test_to_dict_serialisable(self) -> None:
        evt = SupplierActivated.create(
            supplier_id=_sid(), company_id=_cid(), previous_status="INACTIVE"
        )
        d = evt.to_dict()
        json.dumps(d)
        assert d["previous_status"] == "INACTIVE"


class TestSupplierDeactivated:
    def test_create_factory(self) -> None:
        evt = SupplierDeactivated.create(
            supplier_id=_sid(), company_id=_cid(), reason="Low performance"
        )
        assert evt.event_type == "supplier.deactivated"
        assert evt.aggregate_type == "Supplier"
        assert evt.reason == "Low performance"

    def test_reason_optional(self) -> None:
        evt = SupplierDeactivated.create(supplier_id=_sid(), company_id=_cid())
        assert evt.reason is None

    def test_to_dict_serialisable(self) -> None:
        evt = SupplierDeactivated.create(supplier_id=_sid(), company_id=_cid())
        json.dumps(evt.to_dict())


class TestSupplierBlocked:
    def test_create_factory(self) -> None:
        evt = SupplierBlocked.create(
            supplier_id=_sid(), company_id=_cid(), reason="Compliance issue"
        )
        assert evt.event_type == "supplier.blocked"
        assert evt.reason == "Compliance issue"

    def test_to_dict_serialisable(self) -> None:
        evt = SupplierBlocked.create(
            supplier_id=_sid(), company_id=_cid(), reason="Fraud"
        )
        d = evt.to_dict()
        json.dumps(d)
        assert d["reason"] == "Fraud"


class TestSupplierReactivated:
    def test_create_factory(self) -> None:
        evt = SupplierReactivated.create(
            supplier_id=_sid(),
            company_id=_cid(),
            previous_status="BLOCKED",
            reason="Issue resolved",
        )
        assert evt.event_type == "supplier.reactivated"
        assert evt.previous_status == "BLOCKED"
        assert evt.reason == "Issue resolved"

    def test_from_inactive(self) -> None:
        evt = SupplierReactivated.create(
            supplier_id=_sid(), company_id=_cid(), previous_status="INACTIVE"
        )
        assert evt.previous_status == "INACTIVE"
        assert evt.reason is None

    def test_to_dict_serialisable(self) -> None:
        evt = SupplierReactivated.create(
            supplier_id=_sid(), company_id=_cid(), previous_status="BLOCKED"
        )
        json.dumps(evt.to_dict())


class TestSupplierArchived:
    def test_create_factory(self) -> None:
        evt = SupplierArchived.create(
            supplier_id=_sid(), company_id=_cid(), previous_status="INACTIVE"
        )
        assert evt.event_type == "supplier.archived"
        assert evt.previous_status == "INACTIVE"

    def test_to_dict_serialisable(self) -> None:
        evt = SupplierArchived.create(
            supplier_id=_sid(), company_id=_cid(), previous_status="ACTIVE"
        )
        d = evt.to_dict()
        json.dumps(d)
        assert d["previous_status"] == "ACTIVE"


class TestEventFieldInvariants:
    """Cross-event invariant checks."""

    ALL_EVENTS = [
        SupplierCreated.create(
            supplier_id=_sid(), company_id=_cid(), supplier_code="X", legal_name="Y"
        ),
        SupplierUpdated.create(
            supplier_id=_sid(), company_id=_cid(), changed_fields=[]
        ),
        SupplierActivated.create(
            supplier_id=_sid(), company_id=_cid(), previous_status="DRAFT"
        ),
        SupplierDeactivated.create(supplier_id=_sid(), company_id=_cid()),
        SupplierBlocked.create(supplier_id=_sid(), company_id=_cid(), reason="reason"),
        SupplierReactivated.create(
            supplier_id=_sid(), company_id=_cid(), previous_status="BLOCKED"
        ),
        SupplierArchived.create(
            supplier_id=_sid(), company_id=_cid(), previous_status="ACTIVE"
        ),
    ]

    @pytest.mark.parametrize("evt", ALL_EVENTS)
    def test_aggregate_type_is_supplier(self, evt) -> None:
        assert evt.aggregate_type == "Supplier"

    @pytest.mark.parametrize("evt", ALL_EVENTS)
    def test_has_event_id(self, evt) -> None:
        assert isinstance(evt.event_id, UUID)

    @pytest.mark.parametrize("evt", ALL_EVENTS)
    def test_to_dict_has_required_keys(self, evt) -> None:
        d = evt.to_dict()
        for key in (
            "event_id",
            "event_type",
            "aggregate_type",
            "aggregate_id",
            "company_id",
            "occurred_at",
        ):
            assert key in d, f"Missing key '{key}' in {evt.event_type}"

    @pytest.mark.parametrize("evt", ALL_EVENTS)
    def test_all_json_serialisable(self, evt) -> None:
        json.dumps(evt.to_dict())  # must not raise
