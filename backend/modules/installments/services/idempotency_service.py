"""InstallmentIdempotencyService — the race-safe reservation primitive
required before any high-risk Installments command (activation,
collection, settlement, reversal, rescheduling, cancellation, default,
write-off) can be implemented safely (plan.md §20, tasks.md Phase 5.5).

Uses ``INSERT...ON CONFLICT DO NOTHING...RETURNING`` — this **never
raises** for the conflicting case, eliminating PostgreSQL's aborted-
transaction problem by construction rather than by recovering from it
with a savepoint (plan.md §20's correction; no savepoint/bare-unique-
violation-catch pattern is used anywhere here). This is a deliberate,
Postgres-specific construct with no dialect-agnostic equivalent in this
module — never a bare ``INSERT`` + caught ``IntegrityError``.

Spec ref: specs/010-installments/plan.md §20.1-20.4.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.installments.exceptions import InstallmentIdempotencyConflictError
from modules.installments.models.idempotency import InstallmentIdempotencyKey

_UNIQUE_INDEX_ELEMENTS = ["company_id", "operation", "idempotency_key"]


@dataclass(frozen=True)
class ReservationResult:
    """Outcome of ``InstallmentIdempotencyService.reserve()`` — one of
    the two normal, non-error outcomes (plan.md §20.3): a fresh
    reservation to proceed with, or a replay of an already-completed
    prior result. The other two possible outcomes (payload mismatch;
    the defensive unexpected-state branch) are raised as
    ``InstallmentIdempotencyConflictError``, never returned as data."""

    outcome: str  # "RESERVED" | "REPLAY"
    reservation_id: UUID
    result_payload: dict[str, Any] | None = None


class InstallmentIdempotencyService:
    """Reserves and completes idempotency keys for high-risk commands."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def reserve(
        self,
        company_id: UUID,
        operation: str,
        idempotency_key: str,
        request_fingerprint: str,
        contract_id: UUID | None = None,
    ) -> ReservationResult:
        """Attempt to reserve ``(company_id, operation, idempotency_key)``.

        This statement never raises ``IntegrityError`` and never leaves
        the session in an aborted state — ``ON CONFLICT DO NOTHING``
        guarantees a clean outcome either way (plan.md §20.2).

        Raises:
            InstallmentIdempotencyConflictError: ``code=
                "IDEMPOTENCY_PAYLOAD_MISMATCH"`` when an existing
                ``COMPLETED`` row's fingerprint differs from this
                request's (the normal, documented conflict outcome);
                ``code="IDEMPOTENCY_UNEXPECTED_STATE"`` for the
                defensive-only branch of observing another session's
                still-``IN_PROGRESS`` row — should be impossible under
                PostgreSQL's READ COMMITTED isolation combined with the
                unique-index block, retained only as a guard, never a
                documented "try again" response for API clients
                (plan.md §20.3).
        """
        stmt = (
            pg_insert(InstallmentIdempotencyKey)
            .values(
                company_id=company_id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                status="IN_PROGRESS",
                contract_id=contract_id,
                created_at=utcnow(),
            )
            .on_conflict_do_nothing(index_elements=_UNIQUE_INDEX_ELEMENTS)
            .returning(InstallmentIdempotencyKey.id)
        )
        reservation_id = self.db.execute(stmt).scalar_one_or_none()
        if reservation_id is not None:
            return ReservationResult(outcome="RESERVED", reservation_id=reservation_id)

        # A conflicting row already exists. If the other request's INSERT
        # was still uncommitted, our own INSERT above blocked at the
        # database level until it resolved — by the time we reach this
        # SELECT, the other transaction has always already committed or
        # rolled back (plan.md §20.2).
        existing = self.db.execute(
            select(InstallmentIdempotencyKey).where(
                InstallmentIdempotencyKey.company_id == company_id,
                InstallmentIdempotencyKey.operation == operation,
                InstallmentIdempotencyKey.idempotency_key == idempotency_key,
            )
        ).scalar_one()

        if (
            existing.status == "COMPLETED"
            and existing.request_fingerprint == request_fingerprint
        ):
            return ReservationResult(
                outcome="REPLAY",
                reservation_id=existing.id,
                result_payload=existing.result_payload,
            )
        if existing.status == "COMPLETED":
            raise InstallmentIdempotencyConflictError(idempotency_key=idempotency_key)

        # existing.status == "IN_PROGRESS" — defensive-only branch,
        # plan.md §20.3: should never occur under normal operation.
        raise InstallmentIdempotencyConflictError(
            message=(
                "Idempotency reservation observed in an unexpected in-progress state."
            ),
            code="IDEMPOTENCY_UNEXPECTED_STATE",
            idempotency_key=idempotency_key,
        )

    def complete(self, reservation_id: UUID, result_payload: dict[str, Any]) -> None:
        """Flush only — the caller commits this together with the
        business mutation the reservation guards, in the same
        transaction (plan.md §21)."""
        stmt = (
            update(InstallmentIdempotencyKey)
            .where(InstallmentIdempotencyKey.id == reservation_id)
            .values(
                status="COMPLETED",
                result_payload=result_payload,
                completed_at=utcnow(),
            )
        )
        self.db.execute(stmt)
