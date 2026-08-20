"""[T080] [BR-9A-023] Platform audit records are append-only through
every API surface.

Two independent proofs:

1.  Structural: ``PlatformAuditRepository`` exposes no update/delete
    method at all (not even a raising stub) — T036's Result note already
    established this; this test makes it a durable, automatically-
    re-checked invariant rather than a one-time manual observation.
2.  Structural, whole-app: the live OpenAPI schema (which reflects every
    route FastAPI has actually registered, regardless of how routers are
    internally composed) contains no PUT/PATCH/DELETE operation on any
    path mentioning "audit". No `GET /platform/audit` route exists yet
    either (T170, Phase 13) — this test does not require one; once T170
    adds it, this test keeps passing unmodified as long as it stays
    GET-only, which is exactly the property under test.
"""

from __future__ import annotations

import inspect

from fastapi.testclient import TestClient

from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)

_MUTATING_METHOD_NAMES = {"update", "delete", "edit", "remove", "patch"}
_MUTATING_HTTP_METHODS = {"put", "patch", "delete"}


class TestRepositoryExposesNoMutationMethod:
    def test_no_update_or_delete_method_exists(self) -> None:
        members = {name for name, _ in inspect.getmembers(PlatformAuditRepository)}
        offending = members & _MUTATING_METHOD_NAMES
        assert offending == set(), (
            f"PlatformAuditRepository exposes mutation method(s): {offending} — "
            "audit records must be append-only (BR-9A-023)."
        )

    def test_public_methods_are_limited_to_record_and_read_operations(self) -> None:
        public_methods = {
            name
            for name, _ in inspect.getmembers(
                PlatformAuditRepository, predicate=inspect.isfunction
            )
            if not name.startswith("_")
        }
        # `record` (insert-only, flush-only) and `list_filtered` (T078,
        # read-only) are the only two public methods this repository may
        # ever expose.
        assert public_methods == {"record", "list_filtered"}


class TestNoApiSurfaceMutatesAuditRecords:
    def test_openapi_schema_has_no_mutating_audit_operation(
        self, test_client: TestClient
    ) -> None:
        response = test_client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()

        offending: list[str] = []
        for path, operations in schema.get("paths", {}).items():
            # Scoped to /platform paths specifically — the tenant-side
            # `/companies/{company_id}/audit-logs` routes are a separate,
            # unrelated module (`CompanyAuditLogRepository`), out of this
            # test's scope.
            if "/platform" not in path or "audit" not in path.lower():
                continue
            for method in operations:
                if method.lower() in _MUTATING_HTTP_METHODS:
                    offending.append(f"{method.upper()} {path}")

        assert (
            offending == []
        ), f"Found mutating HTTP operation(s) on a Platform audit path: {offending}"

    def test_no_platform_audit_path_declared_at_all_yet(
        self, test_client: TestClient
    ) -> None:
        """Documents the current state explicitly (Phase 6 scope discipline
        — T170/Phase 13 adds the read route): if this ever starts failing
        because a route now exists, the failure is expected and this
        assertion should be updated/removed alongside that phase's work,
        not silently left stale."""
        response = test_client.get("/openapi.json")
        schema = response.json()
        platform_audit_paths = [
            p
            for p in schema.get("paths", {})
            if "/platform" in p and "audit" in p.lower()
        ]
        assert platform_audit_paths == []
