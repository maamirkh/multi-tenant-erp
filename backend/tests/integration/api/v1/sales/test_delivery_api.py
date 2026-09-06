"""API integration tests for Delivery Note endpoints — Phase 5.

Tests:
  - POST /delivery-notes              — create DN from approved SO
  - GET  /delivery-notes              — list DNs (order/status/customer filters)
  - GET  /delivery-notes/{id}         — get DN detail
  - POST /delivery-notes/{id}/dispatch — DRAFT → DISPATCHED
  - POST /delivery-notes/{id}/deliver  — DISPATCHED → DELIVERED
  - POST /delivery-notes/{id}/cancel   — cancel DN
  - GET  /delivery-notes/{id}/lines    — list DN lines
  - 404 on unknown DN
  - 409 on invalid transitions / quantity exceeded
  - RBAC: unauthenticated requests are rejected
  - Tenant isolation: Company B cannot access Company A's DNs

Task: T156
Spec ref: specs/007-sales-management/spec.md §Order Fulfilment
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.sales.models.order import OrderLine, SalesOrder
from tests.fixtures.auth_fixtures import create_test_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_email() -> str:
    return f"dn-test-{uuid4().hex[:8]}@example.com"


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _dn_url(company_id: str, path: str = "") -> str:
    return f"/api/v1/companies/{company_id}/sales/delivery-notes{path}"


def _create_company(client: TestClient, token: str) -> UUID:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Sales Test Co {suffix}",
            "email": f"contact-{suffix}@sales-test.example.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return UUID(resp.json()["data"]["id"])


def _create_approved_order(
    db: Session,
    company_id,
) -> tuple[SalesOrder, OrderLine]:
    """Create an APPROVED SalesOrder with one line for testing."""
    order = SalesOrder(
        company_id=company_id,
        order_number=f"SO-API-{uuid4().hex[:8]}",
        customer_id=str(uuid4()),
        order_date="2026-08-03",
        currency_code="USD",
        sales_rep_id=str(uuid4()),
        priority="NORMAL",
        status="APPROVED",
        subtotal=Decimal("100.00"),
        discount_amount=Decimal("0"),
        tax_amount=Decimal("0"),
        charges_amount=Decimal("0"),
        total_amount=Decimal("100.00"),
        approval_version=1,
        version=1,
    )
    db.add(order)
    db.flush()

    line = OrderLine(
        company_id=company_id,
        order_id=str(order.id),
        line_number=1,
        description="Test product",
        quantity_ordered=Decimal("10"),
        quantity_delivered=Decimal("0"),
        unit_of_measure="EA",
        unit_price=Decimal("10.00"),
        extended_amount=Decimal("100.00"),
        delivery_status="PENDING",
    )
    db.add(line)
    db.flush()
    return order, line


def _create_dn_payload(order_id, order_line_id, qty: int = 5) -> dict:
    return {
        "order_id": str(order_id),
        "lines": [
            {
                "order_line_id": str(order_line_id),
                "description": "Test product",
                "quantity_dispatched": qty,
                "unit_of_measure": "EA",
            }
        ],
    }


# ---------------------------------------------------------------------------
# Tests: Create
# ---------------------------------------------------------------------------


class TestCreateDeliveryNote:
    def test_create_dn_from_approved_order(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, _unique_email())
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        order, line = _create_approved_order(db_session, company_id)

        resp = test_client.post(
            _dn_url(str(company_id)),
            json=_create_dn_payload(order.id, line.id, qty=5),
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["status"] == "DRAFT"
        assert data["order_id"] == str(order.id)

    def test_create_dn_from_draft_order_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, _unique_email())
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        # Create a DRAFT order
        order = SalesOrder(
            company_id=company_id,
            order_number=f"SO-DRAFT-{uuid4().hex[:8]}",
            customer_id=str(uuid4()),
            order_date="2026-08-03",
            currency_code="USD",
            sales_rep_id=str(uuid4()),
            priority="NORMAL",
            status="DRAFT",
            subtotal=Decimal("0"),
            discount_amount=Decimal("0"),
            tax_amount=Decimal("0"),
            charges_amount=Decimal("0"),
            total_amount=Decimal("0"),
            approval_version=1,
            version=1,
        )
        db_session.add(order)
        db_session.flush()
        line = OrderLine(
            company_id=company_id,
            order_id=str(order.id),
            line_number=1,
            description="Test",
            quantity_ordered=Decimal("5"),
            quantity_delivered=Decimal("0"),
            unit_of_measure="EA",
            unit_price=Decimal("10"),
            extended_amount=Decimal("50"),
            delivery_status="PENDING",
        )
        db_session.add(line)
        db_session.flush()

        resp = test_client.post(
            _dn_url(str(company_id)),
            json=_create_dn_payload(order.id, line.id, qty=5),
            headers=_auth(token),
        )
        assert resp.status_code == 409, resp.text

    def test_create_dn_exceeds_remaining_quantity(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, _unique_email())
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        order, line = _create_approved_order(db_session, company_id)

        resp = test_client.post(
            _dn_url(str(company_id)),
            json=_create_dn_payload(order.id, line.id, qty=20),  # > 10 ordered
            headers=_auth(token),
        )
        assert resp.status_code == 409, resp.text

    def test_create_dn_unauthenticated_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        resp = test_client.post(
            _dn_url(str(uuid4())),
            json={},
        )
        assert resp.status_code in (401, 422)

    def test_create_dn_auto_generates_delivery_number(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, _unique_email())
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        order, line = _create_approved_order(db_session, company_id)

        resp = test_client.post(
            _dn_url(str(company_id)),
            json=_create_dn_payload(order.id, line.id, qty=5),
            headers=_auth(token),
        )
        assert resp.status_code == 201
        delivery_number = resp.json()["data"]["delivery_number"]
        assert delivery_number.startswith("DN-")


# ---------------------------------------------------------------------------
# Tests: List
# ---------------------------------------------------------------------------


class TestListDeliveryNotes:
    def test_list_returns_company_dns(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, _unique_email())
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        order, line = _create_approved_order(db_session, company_id)
        test_client.post(
            _dn_url(str(company_id)),
            json=_create_dn_payload(order.id, line.id, qty=5),
            headers=_auth(token),
        )

        resp = test_client.get(_dn_url(str(company_id)), headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] >= 1

    def test_list_filter_by_status(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, _unique_email())
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        order, line = _create_approved_order(db_session, company_id)
        test_client.post(
            _dn_url(str(company_id)),
            json=_create_dn_payload(order.id, line.id, qty=5),
            headers=_auth(token),
        )

        resp = test_client.get(
            _dn_url(str(company_id)) + "?status=DRAFT",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        for item in items:
            assert item["status"] == "DRAFT"


# ---------------------------------------------------------------------------
# Tests: Get detail
# ---------------------------------------------------------------------------


class TestGetDeliveryNote:
    def test_get_dn_returns_correct_data(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, _unique_email())
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        order, line = _create_approved_order(db_session, company_id)
        create_resp = test_client.post(
            _dn_url(str(company_id)),
            json=_create_dn_payload(order.id, line.id, qty=5),
            headers=_auth(token),
        )
        dn_id = create_resp.json()["data"]["id"]

        resp = test_client.get(
            _dn_url(str(company_id), f"/{dn_id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == dn_id

    def test_get_unknown_dn_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, _unique_email())
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        resp = test_client.get(
            _dn_url(str(company_id), f"/{uuid4()}"),
            headers=_auth(token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Dispatch
# ---------------------------------------------------------------------------


class TestDispatchDeliveryNote:
    def test_dispatch_transitions_to_dispatched(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, _unique_email())
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        order, line = _create_approved_order(db_session, company_id)
        create_resp = test_client.post(
            _dn_url(str(company_id)),
            json=_create_dn_payload(order.id, line.id, qty=5),
            headers=_auth(token),
        )
        dn_id = create_resp.json()["data"]["id"]

        resp = test_client.post(
            _dn_url(str(company_id), f"/{dn_id}/dispatch"),
            json={"dispatch_date": "2026-08-03"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "DISPATCHED"

    def test_dispatch_updates_order_to_partially_delivered(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, _unique_email())
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        order, line = _create_approved_order(db_session, company_id)
        create_resp = test_client.post(
            _dn_url(str(company_id)),
            json=_create_dn_payload(order.id, line.id, qty=5),  # 5 of 10
            headers=_auth(token),
        )
        dn_id = create_resp.json()["data"]["id"]

        test_client.post(
            _dn_url(str(company_id), f"/{dn_id}/dispatch"),
            json={"dispatch_date": "2026-08-03"},
            headers=_auth(token),
        )

        db_session.refresh(order)
        assert order.status == "PARTIALLY_DELIVERED"

    def test_dispatch_already_dispatched_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, _unique_email())
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        order, line = _create_approved_order(db_session, company_id)
        create_resp = test_client.post(
            _dn_url(str(company_id)),
            json=_create_dn_payload(order.id, line.id, qty=5),
            headers=_auth(token),
        )
        dn_id = create_resp.json()["data"]["id"]

        test_client.post(
            _dn_url(str(company_id), f"/{dn_id}/dispatch"),
            json={"dispatch_date": "2026-08-03"},
            headers=_auth(token),
        )

        resp = test_client.post(
            _dn_url(str(company_id), f"/{dn_id}/dispatch"),
            json={"dispatch_date": "2026-08-04"},
            headers=_auth(token),
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Tests: Deliver
# ---------------------------------------------------------------------------


class TestDeliverDeliveryNote:
    def test_deliver_transitions_to_delivered(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, _unique_email())
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        order, line = _create_approved_order(db_session, company_id)
        create_resp = test_client.post(
            _dn_url(str(company_id)),
            json=_create_dn_payload(order.id, line.id, qty=5),
            headers=_auth(token),
        )
        dn_id = create_resp.json()["data"]["id"]

        test_client.post(
            _dn_url(str(company_id), f"/{dn_id}/dispatch"),
            json={"dispatch_date": "2026-08-03"},
            headers=_auth(token),
        )

        resp = test_client.post(
            _dn_url(str(company_id), f"/{dn_id}/deliver"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "DELIVERED"

    def test_deliver_from_draft_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, _unique_email())
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        order, line = _create_approved_order(db_session, company_id)
        create_resp = test_client.post(
            _dn_url(str(company_id)),
            json=_create_dn_payload(order.id, line.id, qty=5),
            headers=_auth(token),
        )
        dn_id = create_resp.json()["data"]["id"]

        # Try to deliver without dispatching first
        resp = test_client.post(
            _dn_url(str(company_id), f"/{dn_id}/deliver"),
            headers=_auth(token),
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Tests: Cancel
# ---------------------------------------------------------------------------


class TestCancelDeliveryNote:
    def test_cancel_draft_dn(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, _unique_email())
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        order, line = _create_approved_order(db_session, company_id)
        create_resp = test_client.post(
            _dn_url(str(company_id)),
            json=_create_dn_payload(order.id, line.id, qty=5),
            headers=_auth(token),
        )
        dn_id = create_resp.json()["data"]["id"]

        resp = test_client.post(
            _dn_url(str(company_id), f"/{dn_id}/cancel"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "CANCELLED"

    def test_cancel_delivered_dn_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, _unique_email())
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        order, line = _create_approved_order(db_session, company_id)
        create_resp = test_client.post(
            _dn_url(str(company_id)),
            json=_create_dn_payload(order.id, line.id, qty=5),
            headers=_auth(token),
        )
        dn_id = create_resp.json()["data"]["id"]

        # Dispatch then deliver
        test_client.post(
            _dn_url(str(company_id), f"/{dn_id}/dispatch"),
            json={"dispatch_date": "2026-08-03"},
            headers=_auth(token),
        )
        test_client.post(
            _dn_url(str(company_id), f"/{dn_id}/deliver"),
            headers=_auth(token),
        )

        resp = test_client.post(
            _dn_url(str(company_id), f"/{dn_id}/cancel"),
            headers=_auth(token),
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Tests: List lines
# ---------------------------------------------------------------------------


class TestListDeliveryNoteLines:
    def test_list_lines_returns_correct_count(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, _unique_email())
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        order, line = _create_approved_order(db_session, company_id)
        create_resp = test_client.post(
            _dn_url(str(company_id)),
            json=_create_dn_payload(order.id, line.id, qty=5),
            headers=_auth(token),
        )
        dn_id = create_resp.json()["data"]["id"]

        resp = test_client.get(
            _dn_url(str(company_id), f"/{dn_id}/lines"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        lines = resp.json()["data"]
        assert len(lines) == 1
        assert lines[0]["quantity_dispatched"] == "5.000"


# ---------------------------------------------------------------------------
# Tests: Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolationAPI:
    def test_company_b_cannot_access_company_a_dn(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user_a, password_a = create_test_user(db_session, _unique_email())
        user_b, password_b = create_test_user(db_session, _unique_email())
        token_a = _login(test_client, user_a.email, password_a)
        token_b = _login(test_client, user_b.email, password_b)
        company_a = _create_company(test_client, token_a)
        company_b = _create_company(test_client, token_b)

        order, line = _create_approved_order(db_session, company_a)
        create_resp = test_client.post(
            _dn_url(str(company_a)),
            json=_create_dn_payload(order.id, line.id, qty=5),
            headers=_auth(token_a),
        )
        dn_id = create_resp.json()["data"]["id"]

        # Company B tries to access Company A's DN
        resp = test_client.get(
            _dn_url(str(company_b), f"/{dn_id}"),
            headers=_auth(token_b),
        )
        assert resp.status_code == 404

        # Company B list returns empty
        list_resp = test_client.get(
            _dn_url(str(company_b)),
            headers=_auth(token_b),
        )
        assert list_resp.json()["data"]["total"] == 0
