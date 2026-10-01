"""Unit tests for InstallmentSettlementService.generate_quote() (tasks.md
T159, FR-INST-191).

Uses fake contract/outstanding/configuration/audit collaborators
(unit-level) so these tests exercise only the settlement service's own
quote-composition logic — the same live outstanding breakdown, queried
twice for an unchanged contract state, must reproduce an identical
quote (FR-INST-191). Real end-to-end wiring through the actual
Postgres-backed gateways is proven by
``test_settlement_quote.py``/``test_settlement_execution.py``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, cast

import pytest

from modules.installments.exceptions import (
    InstallmentNotFoundError,
    InstallmentSettlementNotAllowedError,
)
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.services.audit_service import InstallmentAuditService
from modules.installments.services.configuration_service import (
    InstallmentConfigurationService,
)
from modules.installments.services.outstanding_service import (
    InstallmentOutstandingService,
    OutstandingBreakdown,
)
from modules.installments.services.settlement_service import (
    InstallmentSettlementService,
)


@dataclass
class _FakeContract:
    id: Any
    status: str = "ACTIVE"
    branch_id: Any = None
    currency_code: str = "USD"


class _FakeContractRepo:
    def __init__(self, contract: _FakeContract | None) -> None:
        self._contract = contract

    def get_by_id_or_none(self, contract_id: Any, company_id: Any):
        return self._contract


class _FakeOutstandingService:
    def __init__(self, breakdown: OutstandingBreakdown) -> None:
        self._breakdown = breakdown
        self.calls = 0

    def compute_outstanding_breakdown(self, company_id: Any, contract_id: Any):
        self.calls += 1
        return self._breakdown


@dataclass
class _FakeConfig:
    early_settlement_policy: dict[str, Any] | None = None


class _FakeConfigurationService:
    def __init__(self, config: _FakeConfig | None = None) -> None:
        self._config = config

    def get_effective_config(self, company_id: Any, branch_id: Any = None):
        return self._config


class _FakeAuditService:
    def __init__(self) -> None:
        self.records: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def record(self, *args: Any, **kwargs: Any) -> None:
        self.records.append((args, kwargs))


class _FakeDb:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


def _make_service(
    contract: _FakeContract | None,
    breakdown: OutstandingBreakdown,
    *,
    config: _FakeConfig | None = None,
    audit: _FakeAuditService | None = None,
    db: _FakeDb | None = None,
) -> InstallmentSettlementService:
    return InstallmentSettlementService(
        db=db if db is not None else _FakeDb(),
        contract_repo=cast(InstallmentContractRepository, _FakeContractRepo(contract)),
        outstanding_service=cast(
            InstallmentOutstandingService, _FakeOutstandingService(breakdown)
        ),
        collection_service=None,  # type: ignore[arg-type]
        configuration_service=cast(
            InstallmentConfigurationService, _FakeConfigurationService(config)
        ),
        idempotency_service=None,  # type: ignore[arg-type]
        audit_service=cast(
            InstallmentAuditService,
            audit if audit is not None else _FakeAuditService(),
        ),
    )


class TestSettlementQuoteReproducibility:
    def test_same_state_and_as_of_date_produce_the_same_quote(self) -> None:
        contract = _FakeContract(id=uuid.uuid4())
        breakdown = OutstandingBreakdown(
            schedule_outstanding=Decimal("300.00"),
            late_charge_outstanding=Decimal("25.00"),
        )
        svc = _make_service(contract, breakdown)
        as_of = date(2026, 3, 1)

        first = svc.generate_quote(uuid.uuid4(), contract.id, as_of)
        second = svc.generate_quote(uuid.uuid4(), contract.id, as_of)

        assert first.settlement_amount == second.settlement_amount == Decimal("325.00")
        assert first.schedule_outstanding == second.schedule_outstanding
        assert first.late_charge_outstanding == second.late_charge_outstanding
        assert first.as_of_date == second.as_of_date == as_of

    def test_settlement_amount_is_schedule_plus_late_charge_outstanding(self) -> None:
        contract = _FakeContract(id=uuid.uuid4())
        breakdown = OutstandingBreakdown(
            schedule_outstanding=Decimal("100.00"),
            late_charge_outstanding=Decimal("0"),
        )
        svc = _make_service(contract, breakdown)

        quote = svc.generate_quote(uuid.uuid4(), contract.id, date(2026, 1, 1))

        assert quote.settlement_amount == Decimal("100.00")
        assert quote.currency_code == "USD"

    def test_quote_surfaces_the_tenant_early_settlement_policy_verbatim(self) -> None:
        contract = _FakeContract(id=uuid.uuid4())
        policy = {"discount_pct": "5.00"}
        breakdown = OutstandingBreakdown(
            schedule_outstanding=Decimal("100.00"),
            late_charge_outstanding=Decimal("0"),
        )
        svc = _make_service(
            contract, breakdown, config=_FakeConfig(early_settlement_policy=policy)
        )

        quote = svc.generate_quote(uuid.uuid4(), contract.id, date(2026, 1, 1))

        assert quote.early_settlement_policy == policy

    def test_quote_with_no_configuration_row_has_no_policy(self) -> None:
        contract = _FakeContract(id=uuid.uuid4())
        breakdown = OutstandingBreakdown(
            schedule_outstanding=Decimal("100.00"),
            late_charge_outstanding=Decimal("0"),
        )
        svc = _make_service(contract, breakdown, config=None)

        quote = svc.generate_quote(uuid.uuid4(), contract.id, date(2026, 1, 1))

        assert quote.early_settlement_policy is None

    def test_quote_records_an_audit_entry_even_though_non_mutating(self) -> None:
        contract = _FakeContract(id=uuid.uuid4())
        breakdown = OutstandingBreakdown(
            schedule_outstanding=Decimal("100.00"),
            late_charge_outstanding=Decimal("0"),
        )
        db = _FakeDb()
        audit = _FakeAuditService()
        svc = _make_service(contract, breakdown, audit=audit, db=db)

        svc.generate_quote(uuid.uuid4(), contract.id, date(2026, 1, 1))

        assert len(audit.records) == 1
        _, kwargs = audit.records[0]
        assert kwargs["action"] == "SETTLEMENT_QUOTED"
        assert db.commits == 1

    def test_quote_for_unknown_contract_raises_not_found(self) -> None:
        breakdown = OutstandingBreakdown(
            schedule_outstanding=Decimal("0"), late_charge_outstanding=Decimal("0")
        )
        svc = _make_service(None, breakdown)

        with pytest.raises(InstallmentNotFoundError):
            svc.generate_quote(uuid.uuid4(), uuid.uuid4(), date(2026, 1, 1))

    @pytest.mark.parametrize(
        "status",
        [
            "DRAFT",
            "PENDING_APPROVAL",
            "APPROVED",
            "COMPLETED",
            "CANCELLED",
            "WRITTEN_OFF",
        ],
    )
    def test_quote_rejected_for_non_settleable_contract_status(
        self, status: str
    ) -> None:
        contract = _FakeContract(id=uuid.uuid4(), status=status)
        breakdown = OutstandingBreakdown(
            schedule_outstanding=Decimal("100.00"), late_charge_outstanding=Decimal("0")
        )
        svc = _make_service(contract, breakdown)

        with pytest.raises(InstallmentSettlementNotAllowedError):
            svc.generate_quote(uuid.uuid4(), contract.id, date(2026, 1, 1))
