"""[Epic 10, Phase 11, T191] Unit test — ``InstallmentAccessPolicy``
operation-class matrix (plan.md §15.2, FR-INST-353/356/357/358).

Every (entitlement-state x operation-class) combination must produce the
exact expected allow/deny outcome. Uses a fake ``PlatformEntitlementService``
stub (unit-level, no database) so this exercises only
``InstallmentAccessPolicy.authorize()``'s own decision logic — real
end-to-end resolution through the actual
``PlatformEntitlementService.resolve_effective_entitlement()`` chain is
proven by the Phase 11 integration tests
(``test_entitlement_servicing_continuity.py``).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import cast

import pytest

from modules.installments.exceptions import InstallmentsNotEntitledError
from modules.installments.services.access_policy import (
    InstallmentAccessPolicy,
    InstallmentOperationClass,
)
from modules.platform_admin.services.entitlement_service import (
    PlatformEntitlementService,
)


@dataclass(frozen=True)
class _FakeEntitlement:
    available: bool


class _FakeEntitlementService:
    """Stands in for ``PlatformEntitlementService`` — returns a
    caller-configured ``available`` value regardless of company_id,
    since this test cares only about ``InstallmentAccessPolicy``'s own
    branching, not the resolver chain itself."""

    def __init__(self, *, available: bool) -> None:
        self.available = available
        self.calls: list[tuple[uuid.UUID, str]] = []

    def resolve_effective_entitlement(
        self, *, company_id: uuid.UUID, capability_key: str
    ) -> _FakeEntitlement:
        self.calls.append((company_id, capability_key))
        return _FakeEntitlement(available=self.available)


class TestInstallmentAccessPolicyMatrix:
    """(entitlement-state x operation-class) -> allow/deny, exhaustively."""

    @pytest.mark.parametrize(
        "operation",
        [
            InstallmentOperationClass.ORIGINATION,
            InstallmentOperationClass.SERVICING,
            InstallmentOperationClass.READ,
            InstallmentOperationClass.ADMIN,
        ],
    )
    def test_entitled_tenant_allows_every_operation_class(
        self, operation: InstallmentOperationClass
    ) -> None:
        entitlement_service = _FakeEntitlementService(available=True)
        policy = InstallmentAccessPolicy(
            entitlement_service=cast(PlatformEntitlementService, entitlement_service)
        )

        policy.authorize(company_id=uuid.uuid4(), operation=operation)
        # No exception raised — success.

    def test_disabled_tenant_blocks_origination(self) -> None:
        entitlement_service = _FakeEntitlementService(available=False)
        policy = InstallmentAccessPolicy(
            entitlement_service=cast(PlatformEntitlementService, entitlement_service)
        )

        with pytest.raises(InstallmentsNotEntitledError) as exc_info:
            policy.authorize(
                company_id=uuid.uuid4(),
                operation=InstallmentOperationClass.ORIGINATION,
            )
        assert exc_info.value.code == "FEATURE_DISABLED"

    def test_disabled_tenant_permits_servicing(self) -> None:
        entitlement_service = _FakeEntitlementService(available=False)
        policy = InstallmentAccessPolicy(
            entitlement_service=cast(PlatformEntitlementService, entitlement_service)
        )

        policy.authorize(
            company_id=uuid.uuid4(), operation=InstallmentOperationClass.SERVICING
        )
        # No exception raised — FR-INST-356 servicing continuity.

    def test_disabled_tenant_permits_read(self) -> None:
        entitlement_service = _FakeEntitlementService(available=False)
        policy = InstallmentAccessPolicy(
            entitlement_service=cast(PlatformEntitlementService, entitlement_service)
        )

        policy.authorize(
            company_id=uuid.uuid4(), operation=InstallmentOperationClass.READ
        )

    def test_disabled_tenant_permits_admin_and_never_resolves_entitlement(
        self,
    ) -> None:
        """ADMIN bypasses the check entirely — the entitlement resolver
        must not even be called (plan.md §15.2's "reachable while
        disabled, chicken-and-egg" — the resolver call itself would be
        wasted work on the module-toggle path)."""
        entitlement_service = _FakeEntitlementService(available=False)
        policy = InstallmentAccessPolicy(
            entitlement_service=cast(PlatformEntitlementService, entitlement_service)
        )

        policy.authorize(
            company_id=uuid.uuid4(), operation=InstallmentOperationClass.ADMIN
        )
        assert entitlement_service.calls == []

    def test_resolution_uses_the_installments_capability_key(self) -> None:
        entitlement_service = _FakeEntitlementService(available=True)
        policy = InstallmentAccessPolicy(
            entitlement_service=cast(PlatformEntitlementService, entitlement_service)
        )
        company_id = uuid.uuid4()

        policy.authorize(
            company_id=company_id, operation=InstallmentOperationClass.ORIGINATION
        )
        assert entitlement_service.calls == [(company_id, "installments")]

    def test_never_caches_across_calls(self) -> None:
        """Each ``authorize()`` call resolves fresh (FR-9A-170) — a
        second call after the fake's ``available`` flips must observe
        the new value, never a stale cached result."""
        entitlement_service = _FakeEntitlementService(available=True)
        policy = InstallmentAccessPolicy(
            entitlement_service=cast(PlatformEntitlementService, entitlement_service)
        )
        company_id = uuid.uuid4()

        policy.authorize(
            company_id=company_id, operation=InstallmentOperationClass.ORIGINATION
        )

        entitlement_service.available = False
        with pytest.raises(InstallmentsNotEntitledError):
            policy.authorize(
                company_id=company_id, operation=InstallmentOperationClass.ORIGINATION
            )
        assert len(entitlement_service.calls) == 2
