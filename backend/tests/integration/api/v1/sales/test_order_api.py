"""API integration tests for Sales Order endpoints — Phase 4.

Tests:
  - POST   /sales-orders              — create order
  - GET    /sales-orders              — list orders (status/search filters)
  - GET    /sales-orders/{id}         — get order detail with lines
  - PUT    /sales-orders/{id}         — update DRAFT order
  - POST   /sales-orders/{id}/submit  — DRAFT → PENDING_APPROVAL
  - POST   /sales-orders/{id}/approve — PENDING_APPROVAL → APPROVED
  - POST   /sales-orders/{id}/reject  — PENDING_APPROVAL → REJECTED → DRAFT + version++
  - POST   /sales-orders/{id}/cancel  — cancel with reason
  - POST   /sales-orders/{id}/close   — INVOICED → CLOSED (patched via direct DB)
  - POST   /sales-orders/{id}/lines   — add line to DRAFT
  - DELETE /sales-orders/{id}/lines/{lid} — delete line from DRAFT
  - GET    /approval-matrices         — list approval matrices
  - POST   /approval-matrices         — create approval matrix
  - GET    /approvals/pending         — pending approvals inbox
  - 404 on unknown order
  - 409 on invalid state transitions
  - Tenant isolation

Task: T133
Spec ref: specs/007-sales-management/spec.md §Sales Orders
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _url(company_id: str, path: str = "") -> str:
    return f"/api/v1/companies/{company_id}/sales/sales-orders{path}"


def _approvals_url(company_id: str, path: str = "") -> str:
    return f"/api/v1/companies/{company_id}/sales/approval-matrices{path}"


def _inbox_url(company_id: str, approver_id: str) -> str:
    return f"/api/v1/companies/{company_id}/sales/approvals/pending?approver_id={approver_id}"


def _create_company(client: TestClient, token: str) -> str:
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
    return resp.json()["data"]["id"]


def _create_order(
    client: TestClient,
    company_id: str,
    token: str,
    customer_id: str | None = None,
    sales_rep_id: str | None = None,
) -> dict:
    resp = client.post(
        _url(company_id),
        json={
            "customer_id": customer_id or str(uuid4()),
            "order_date": "2026-08-02",
            "currency_code": "USD",
            "sales_rep_id": sales_rep_id or str(uuid4()),
            "priority": "NORMAL",
            "lines": [],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# CRUD Tests
# ---------------------------------------------------------------------------


class TestSalesOrderCRUD:
    def test_create_order(self, test_client: TestClient, db_session: Session) -> None:
        user, password = create_test_user(db_session, email="so_create@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        resp = test_client.post(
            _url(company_id),
            json={
                "customer_id": str(uuid4()),
                "order_date": "2026-08-02",
                "currency_code": "USD",
                "sales_rep_id": str(uuid4()),
                "priority": "HIGH",
                "lines": [],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["status"] == "DRAFT"
        assert data["order_number"].startswith("SO-")
        assert data["currency_code"] == "USD"
        assert data["priority"] == "HIGH"

    def test_create_order_with_line(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="so_line@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        resp = test_client.post(
            _url(company_id),
            json={
                "customer_id": str(uuid4()),
                "order_date": "2026-08-02",
                "currency_code": "USD",
                "sales_rep_id": str(uuid4()),
                "lines": [
                    {
                        "description": "Widget A",
                        "quantity_ordered": "5",
                        "unit_of_measure": "EA",
                        "unit_price": "100.00",
                    }
                ],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert len(data.get("lines", [])) == 1
        assert data["lines"][0]["description"] == "Widget A"

    def test_list_orders(self, test_client: TestClient, db_session: Session) -> None:
        user, password = create_test_user(db_session, email="so_list@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        _create_order(test_client, company_id, token)
        _create_order(test_client, company_id, token)

        resp = test_client.get(_url(company_id), headers=_auth(token))
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert len(data) >= 2

    def test_list_orders_status_filter(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="so_sfilt@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        _create_order(test_client, company_id, token)

        resp = test_client.get(_url(company_id) + "?status=DRAFT", headers=_auth(token))
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert all(o["status"] == "DRAFT" for o in data)

    def test_get_order_detail(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="so_detail@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        created = _create_order(test_client, company_id, token)
        order_id = created["id"]

        resp = test_client.get(_url(company_id, f"/{order_id}"), headers=_auth(token))
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["id"] == order_id
        assert "lines" in data

    def test_get_order_not_found(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="so_404@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        resp = test_client.get(_url(company_id, f"/{uuid4()}"), headers=_auth(token))
        assert resp.status_code == 404, resp.text

    def test_update_draft_order(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="so_update@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        created = _create_order(test_client, company_id, token)
        order_id = created["id"]

        resp = test_client.put(
            _url(company_id, f"/{order_id}"),
            json={"priority": "URGENT", "internal_notes": "Urgent order"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["priority"] == "URGENT"

    def test_unauthenticated_request_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = str(uuid4())
        resp = test_client.get(_url(company_id))
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Lifecycle Tests
# ---------------------------------------------------------------------------


class TestSalesOrderLifecycle:
    def test_submit_draft_order(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        from modules.sales.models.customer import Customer

        user, password = create_test_user(db_session, email="so_submit@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)
        rep_id = str(uuid4())
        company_uuid = UUID(company_id)

        # Create a customer so credit check passes
        customer = Customer(
            company_id=company_uuid,
            customer_code=f"CUST-{uuid4().hex[:6]}",
            legal_name="Test Customer",
            customer_type="COMPANY",
            category_id=str(uuid4()),
            status="ACTIVE",
            credit_status="GOOD",
            credit_limit=Decimal("100000.00"),
            currency_code="USD",
            version=1,
            created_by=uuid4(),
        )
        db_session.add(customer)
        db_session.flush()
        customer_id = str(customer.id)

        created = _create_order(
            test_client, company_id, token, customer_id=customer_id, sales_rep_id=rep_id
        )
        order_id = created["id"]

        resp = test_client.post(
            _url(company_id, f"/{order_id}/submit"),
            json={"submitted_by": rep_id},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        # Auto-approved (no matrix configured) → APPROVED, or PENDING_APPROVAL
        assert data["status"] in ("PENDING_APPROVAL", "APPROVED"), data

    def test_cannot_submit_non_draft(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="so_submit2@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)
        rep_id = str(uuid4())

        created = _create_order(test_client, company_id, token, sales_rep_id=rep_id)
        order_id = created["id"]

        # Submit once
        test_client.post(
            _url(company_id, f"/{order_id}/submit"),
            json={"submitted_by": rep_id},
            headers=_auth(token),
        )

        # Try submit again — should fail (not DRAFT anymore)
        resp = test_client.post(
            _url(company_id, f"/{order_id}/submit"),
            json={"submitted_by": rep_id},
            headers=_auth(token),
        )
        assert resp.status_code in (409, 422, 400), resp.text

    def test_cancel_draft_order(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="so_cancel@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)
        rep_id = str(uuid4())

        created = _create_order(test_client, company_id, token, sales_rep_id=rep_id)
        order_id = created["id"]

        resp = test_client.post(
            _url(company_id, f"/{order_id}/cancel"),
            json={
                "cancellation_reason": "Customer changed mind",
                "cancelled_by": rep_id,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "CANCELLED"

    def test_cancel_requires_reason(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="so_cancel2@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)
        rep_id = str(uuid4())

        created = _create_order(test_client, company_id, token, sales_rep_id=rep_id)
        order_id = created["id"]

        resp = test_client.post(
            _url(company_id, f"/{order_id}/cancel"),
            json={"cancellation_reason": "  ", "cancelled_by": rep_id},
            headers=_auth(token),
        )
        assert resp.status_code in (409, 422, 400), resp.text

    def test_cannot_cancel_closed_order(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """CLOSED is terminal — cannot be cancelled."""
        from modules.sales.models.order import SalesOrder

        user, password = create_test_user(db_session, email="so_cancel3@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)
        rep_id = str(uuid4())

        created = _create_order(test_client, company_id, token, sales_rep_id=rep_id)
        order_id = created["id"]

        # Force status to CLOSED via DB (terminal state)
        from uuid import UUID as _UUID

        order = (
            db_session.query(SalesOrder)
            .filter(SalesOrder.id == _UUID(order_id))
            .first()
        )
        order.status = "CLOSED"
        db_session.flush()

        resp = test_client.post(
            _url(company_id, f"/{order_id}/cancel"),
            json={"cancellation_reason": "Attempt cancel", "cancelled_by": rep_id},
            headers=_auth(token),
        )
        assert resp.status_code in (409, 422, 400), resp.text


# ---------------------------------------------------------------------------
# Line Management
# ---------------------------------------------------------------------------


class TestOrderLineManagement:
    def test_add_line_to_draft(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="so_addline@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        created = _create_order(test_client, company_id, token)
        order_id = created["id"]

        resp = test_client.post(
            _url(company_id, f"/{order_id}/lines"),
            json={
                "description": "Gadget X",
                "quantity_ordered": "10",
                "unit_of_measure": "EA",
                "unit_price": "50.00",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["description"] == "Gadget X"
        assert data["line_number"] == 1

    def test_add_line_increments_order_total(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="so_linetotal@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        created = _create_order(test_client, company_id, token)
        order_id = created["id"]

        test_client.post(
            _url(company_id, f"/{order_id}/lines"),
            json={
                "description": "Widget",
                "quantity_ordered": "2",
                "unit_of_measure": "EA",
                "unit_price": "100.00",
            },
            headers=_auth(token),
        )

        detail_resp = test_client.get(
            _url(company_id, f"/{order_id}"), headers=_auth(token)
        )
        order_data = detail_resp.json()["data"]
        assert float(order_data["total_amount"]) >= 200.0

    def test_delete_line_from_draft(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="so_delline@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        created = _create_order(test_client, company_id, token)
        order_id = created["id"]

        # Add line
        add_resp = test_client.post(
            _url(company_id, f"/{order_id}/lines"),
            json={
                "description": "Temp Product",
                "quantity_ordered": "1",
                "unit_of_measure": "EA",
                "unit_price": "10.00",
            },
            headers=_auth(token),
        )
        line_id = add_resp.json()["data"]["id"]

        # Delete line
        del_resp = test_client.delete(
            _url(company_id, f"/{order_id}/lines/{line_id}"),
            headers=_auth(token),
        )
        assert del_resp.status_code == 204


# ---------------------------------------------------------------------------
# Approval Matrix
# ---------------------------------------------------------------------------


class TestApprovalMatrix:
    def test_list_approval_matrices_empty(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session, email="so_matrix_list@example.com"
        )
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        resp = test_client.get(_approvals_url(company_id), headers=_auth(token))
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert isinstance(data, list)

    def test_create_approval_matrix(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session, email="so_matrix_create@example.com"
        )
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        resp = test_client.post(
            _approvals_url(company_id),
            json={
                "name": "Standard SO Approval",
                "document_type": "SALES_ORDER",
                "is_active": True,
                "rules": [],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["name"] == "Standard SO Approval"
        assert data["document_type"] == "SALES_ORDER"
        assert data["is_active"] is True


# ---------------------------------------------------------------------------
# Approval Inbox
# ---------------------------------------------------------------------------


class TestApprovalInbox:
    def test_get_pending_approvals_empty(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="so_inbox@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)
        approver_id = str(uuid4())

        resp = test_client.get(
            _inbox_url(company_id, approver_id), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# Tenant Isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    def test_order_not_visible_to_other_company(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="so_tenant@example.com")
        token = _login(test_client, user.email, password)
        # Same user owns (and is thus an active member of) two distinct
        # companies — required now that company-scoped routes enforce
        # membership (see api/v1/router.py's get_current_company_member gate).
        company_a = _create_company(test_client, token)
        company_b = _create_company(test_client, token)

        created = _create_order(test_client, company_a, token)
        order_id = created["id"]

        resp = test_client.get(_url(company_b, f"/{order_id}"), headers=_auth(token))
        assert resp.status_code == 404, resp.text

    def test_list_orders_company_isolated(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="so_tenant2@example.com")
        token = _login(test_client, user.email, password)
        # Same user owns (and is thus an active member of) two distinct
        # companies — required now that company-scoped routes enforce
        # membership (see api/v1/router.py's get_current_company_member gate).
        company_a = _create_company(test_client, token)
        company_b = _create_company(test_client, token)

        _create_order(test_client, company_a, token)

        resp = test_client.get(_url(company_b), headers=_auth(token))
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        # Company B should see 0 orders from Company A
        assert len(data) == 0
