"""Integration tests for health check endpoints.

Covers:
    T132 — GET /api/v1/health happy path
    T133 — Exception handler integration (NotFoundException, unhandled Exception)
"""

import json
from datetime import datetime
from typing import cast

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """T132 — Health endpoint happy path tests."""

    def test_health_returns_200(self, test_client: TestClient) -> None:
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_status_field(self, test_client: TestClient) -> None:
        response = test_client.get("/api/v1/health")
        body = response.json()
        assert body["data"]["status"] in ("healthy", "degraded")

    def test_health_version_matches_settings(self, test_client: TestClient) -> None:
        response = test_client.get("/api/v1/health")
        body = response.json()
        assert body["data"]["version"] == "1.0.0"

    def test_health_response_has_request_id_header(
        self, test_client: TestClient
    ) -> None:
        response = test_client.get("/api/v1/health")
        assert "x-request-id" in response.headers

    def test_health_meta_request_id_matches_header(
        self, test_client: TestClient
    ) -> None:
        response = test_client.get("/api/v1/health")
        body = response.json()
        header_id = response.headers.get("x-request-id")
        assert body["meta"]["request_id"] == header_id

    def test_health_timestamp_is_iso8601(self, test_client: TestClient) -> None:
        response = test_client.get("/api/v1/health")
        body = response.json()
        timestamp_str = body["data"]["timestamp"]
        # datetime.fromisoformat() raises ValueError if not valid ISO 8601
        dt = datetime.fromisoformat(timestamp_str)
        assert dt is not None

    def test_liveness_always_200(self, test_client: TestClient) -> None:
        response = test_client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_readiness_returns_200_with_test_db(self, test_client: TestClient) -> None:
        # SQLite in-memory is always available — readiness should succeed
        response = test_client.get("/api/v1/health/ready")
        assert response.status_code == 200

    def test_root_endpoint_returns_api_metadata(self, test_client: TestClient) -> None:
        response = test_client.get("/")
        assert response.status_code == 200
        body = response.json()
        assert "name" in body
        assert "version" in body


class TestExceptionHandlerIntegration:
    """T133 — Exception handler integration tests."""

    @pytest.fixture(autouse=True)
    def _register_test_routes(self, test_client: TestClient) -> None:
        """Register ephemeral test routes on the TestClient's app."""
        app = cast(FastAPI, test_client.app)

        test_router = APIRouter(prefix="/_test", tags=["test-only"])

        @test_router.get("/not-found")
        async def raise_not_found() -> None:
            from core.exceptions.base import NotFoundException

            raise NotFoundException("Resource not found for testing")

        @test_router.get("/unhandled")
        async def raise_unhandled() -> None:
            raise RuntimeError("Unexpected error for testing")

        app.include_router(test_router)

    def test_not_found_exception_returns_404(self, test_client: TestClient) -> None:
        response = test_client.get("/_test/not-found")
        assert response.status_code == 404

    def test_not_found_exception_body_has_correct_code(
        self, test_client: TestClient
    ) -> None:
        response = test_client.get("/_test/not-found")
        body = response.json()
        assert body["error"]["code"] == "NOT_FOUND"

    def test_not_found_exception_body_shape(self, test_client: TestClient) -> None:
        response = test_client.get("/_test/not-found")
        body = response.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

    def test_unhandled_exception_returns_500(self, test_client: TestClient) -> None:
        response = test_client.get("/_test/unhandled")
        assert response.status_code == 500

    def test_unhandled_exception_returns_internal_error_code(
        self, test_client: TestClient
    ) -> None:
        response = test_client.get("/_test/unhandled")
        body = response.json()
        assert body["error"]["code"] == "INTERNAL_ERROR"

    def test_unhandled_exception_no_stack_trace_in_body(
        self, test_client: TestClient
    ) -> None:
        """Stack trace must not appear in the response body (security requirement)."""
        response = test_client.get("/_test/unhandled")
        body_str = json.dumps(response.json())
        assert "Traceback" not in body_str
        assert "RuntimeError" not in body_str
