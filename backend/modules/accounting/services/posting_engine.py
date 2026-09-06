"""PostingEngine — the single GL posting gate — Phase 4 (CRITICAL).

Research ref: research.md Decision 2 — ALL journal creation (manual
journals, automated postings from Sales/Purchase/Inventory events) goes
through this one service. No other code path ever writes to
``accounting_journal_entries``/``accounting_journal_lines``.

Two entry points create/post journals:
  - ``create_journal()`` → persists a DRAFT (Step 1 balance-checked only;
    lines are inserted immediately and are immutable from that point on —
    see models/gl.py docstring; this phase has no edit-draft endpoint).
  - ``post_direct()`` → creates AND posts in a single atomic transaction
    (no DRAFT/SUBMIT/APPROVE lifecycle) — used by integration handlers and
    any caller that doesn't need the approval workflow. Matches T094's
    "auto-posted entries skip to POSTED directly."

Manual lifecycle: ``submit()`` → ``approve()``/``reject()`` → ``post()``.
``post()`` runs the full 8-step validation pipeline (T093) against an
existing DRAFT (under-threshold, auto-postable) or APPROVED entry.

``reverse()`` creates a new balanced entry with every line's debit/credit
swapped, posts it atomically, and marks the original POSTED entry REVERSED
— all within one transaction (spec.md §15.5).

Every state-changing method performs exactly ONE ``db.commit()`` — the
sequence-number lock (``AccountingSequenceService``, held via
``SELECT ... FOR UPDATE``), the entry/line/approval writes, and the audit
record are all staged via ``add()``/``flush()`` beforehand and committed
together, so a failure at any step rolls back everything, including the
sequence increment (research.md Decision 2's gap-free guarantee).

Spec ref: specs/008-accounting-finance/tasks.md T093, T094
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.accounting.constants import (
    ApprovalStatus,
    FiscalPeriodStatus,
    JournalEntryStatus,
    JournalType,
)
from modules.accounting.events import get_event_bus
from modules.accounting.events.gl_events import JournalPostedEvent, JournalReversedEvent
from modules.accounting.exceptions import (
    AccountNotFoundError,
    ApprovalPermissionDeniedError,
    InvalidJournalStateTransitionError,
    JournalEntryNotFoundError,
    JournalNotReversibleError,
    PostingValidationError,
    SelfApprovalNotAllowedError,
)
from modules.accounting.models.gl import JournalApproval, JournalEntry, JournalLine
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import FiscalPeriodRepository
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import (
    JournalApprovalRepository,
    JournalEntryRepository,
    JournalLineRepository,
)
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.feature_flag_service import (
    AccountingFeatureFlagService,
)
from modules.accounting.services.permission_check import user_has_accounting_permission
from modules.accounting.services.sequence_service import AccountingSequenceService

logger = logging.getLogger(__name__)


@dataclass
class PostingResult:
    """Domain-layer result of a successful posting. See schemas/gl.py for the API schema."""

    journal_entry_id: UUID
    journal_number: str
    posted_at: datetime


class JournalEntryStateMachine:
    """Enforces valid ``JournalEntry`` status transitions.

    Valid transitions (spec.md §15.2, tasks.md T094):
      DRAFT -> SUBMITTED
      DRAFT -> POSTED        (auto-post — skips approval)
      SUBMITTED -> APPROVED
      SUBMITTED -> REJECTED
      APPROVED -> POSTED
      POSTED -> REVERSED
    REJECTED and REVERSED are terminal. POSTED has no backward transition —
    the only outgoing edge is REVERSED (spec.md §15.2: "Posted: Finalized;
    immutable; reflected in GL").
    """

    _VALID_TRANSITIONS: dict[JournalEntryStatus, frozenset[JournalEntryStatus]] = {
        JournalEntryStatus.DRAFT: frozenset(
            {JournalEntryStatus.SUBMITTED, JournalEntryStatus.POSTED}
        ),
        JournalEntryStatus.SUBMITTED: frozenset(
            {JournalEntryStatus.APPROVED, JournalEntryStatus.REJECTED}
        ),
        JournalEntryStatus.APPROVED: frozenset({JournalEntryStatus.POSTED}),
        JournalEntryStatus.POSTED: frozenset({JournalEntryStatus.REVERSED}),
        JournalEntryStatus.REJECTED: frozenset(),
        JournalEntryStatus.REVERSED: frozenset(),
    }

    @classmethod
    def validate_transition(cls, current_status: str, target_status: str) -> None:
        """Raise ``InvalidJournalStateTransitionError`` if not allowed."""
        current = JournalEntryStatus(current_status)
        target = JournalEntryStatus(target_status)
        if target not in cls._VALID_TRANSITIONS[current]:
            raise InvalidJournalStateTransitionError(current.value, target.value)


class PostingEngine:
    """The single domain service authorised to write to the General Ledger."""

    def __init__(
        self,
        db: Session,
        journal_repo: JournalEntryRepository,
        line_repo: JournalLineRepository,
        approval_repo: JournalApprovalRepository,
        account_repo: AccountRepository,
        fiscal_period_repo: FiscalPeriodRepository,
        sequence_service: AccountingSequenceService,
        config_repo: AccountingConfigurationRepository,
        flag_service: AccountingFeatureFlagService,
        audit_service: AuditLogService,
    ) -> None:
        self.db = db
        self._journals = journal_repo
        self._lines = line_repo
        self._approvals = approval_repo
        self._accounts = account_repo
        self._periods = fiscal_period_repo
        self._sequences = sequence_service
        self._config_repo = config_repo
        self._flags = flag_service
        self._audit = audit_service

    # ------------------------------------------------------------------
    # Draft creation
    # ------------------------------------------------------------------

    def create_journal(
        self,
        company_id: UUID,
        journal_type: str,
        posting_source: str,
        posting_date: date,
        lines: list[dict[str, Any]],
        currency_code: str | None = None,
        exchange_rate: Decimal = Decimal("1"),
        reference: str | None = None,
        description: str | None = None,
        notes: str | None = None,
        source_document_type: str | None = None,
        source_document_id: UUID | None = None,
        created_by: UUID | None = None,
    ) -> JournalEntry:
        """Create a DRAFT journal entry with its lines (Step 1 balance-checked only).

        Raises:
            PostingValidationError: Fewer than 2 lines, unbalanced, or a
                line has an invalid debit/credit combination.
            AccountNotFoundError: A referenced account does not exist.
        """
        entry = self._build_entry_and_lines(
            company_id=company_id,
            journal_type=journal_type,
            posting_source=posting_source,
            posting_date=posting_date,
            lines=lines,
            currency_code=currency_code,
            exchange_rate=exchange_rate,
            reference=reference,
            description=description,
            notes=notes,
            source_document_type=source_document_type,
            source_document_id=source_document_id,
            created_by=created_by,
        )
        self._audit.record(
            company_id=company_id,
            entity_type="JournalEntry",
            entity_id=entry.id,
            action="CREATED",
            actor_id=created_by,
            after=self._snapshot(entry),
        )
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def _build_entry_and_lines(
        self,
        company_id: UUID,
        journal_type: str,
        posting_source: str,
        posting_date: date,
        lines: list[dict[str, Any]],
        currency_code: str | None,
        exchange_rate: Decimal,
        reference: str | None,
        description: str | None,
        notes: str | None,
        source_document_type: str | None,
        source_document_id: UUID | None,
        created_by: UUID | None,
    ) -> JournalEntry:
        if len(lines) < 2:
            raise PostingValidationError(
                "A journal entry must have at least two lines."
            )

        if currency_code is None:
            config = self._config_repo.get_for_company(company_id=company_id)
            currency_code = config.base_currency_code if config else "USD"

        total_debit, total_credit = self._sum_and_validate_lines(lines)
        if total_debit != total_credit:
            raise PostingValidationError("Journal must balance")

        entry = JournalEntry(
            company_id=company_id,
            journal_type=journal_type,
            posting_source=posting_source,
            posting_date=posting_date,
            reference=reference,
            description=description,
            notes=notes,
            status=JournalEntryStatus.DRAFT.value,
            source_document_type=source_document_type,
            source_document_id=source_document_id,
            currency_code=currency_code,
            exchange_rate=exchange_rate,
            total_debit_base=total_debit,
            total_credit_base=total_credit,
            created_by=created_by,
        )
        self.db.add(entry)
        self.db.flush()

        for idx, line in enumerate(lines, start=1):
            self._add_line(entry, idx, line, currency_code, exchange_rate)

        return entry

    def _add_line(
        self,
        entry: JournalEntry,
        line_number: int,
        line: dict[str, Any],
        default_currency: str,
        default_exchange_rate: Decimal,
    ) -> JournalLine:
        account = self._accounts.get_by_id_or_none(
            id=line["account_id"], company_id=entry.company_id
        )
        if account is None:
            raise AccountNotFoundError(account_id=str(line["account_id"]))

        debit = Decimal(str(line.get("debit_amount", 0)))
        credit = Decimal(str(line.get("credit_amount", 0)))
        line_currency = line.get("currency_code") or default_currency
        raw_rate = line.get("exchange_rate")
        line_rate = (
            Decimal(str(raw_rate)) if raw_rate is not None else default_exchange_rate
        )

        journal_line = JournalLine(
            company_id=entry.company_id,
            journal_entry_id=entry.id,
            line_number=line_number,
            account_id=account.id,
            account_code=account.account_code,
            debit_amount=debit,
            credit_amount=credit,
            debit_amount_base=debit * line_rate,
            credit_amount_base=credit * line_rate,
            currency_code=line_currency,
            exchange_rate=line_rate,
            cost_center_id=line.get("cost_center_id"),
            department_id=line.get("department_id"),
            project_id=line.get("project_id"),
            description=line.get("description"),
            reference=line.get("reference"),
        )
        return self._lines.create(journal_line)

    @staticmethod
    def _sum_and_validate_lines(lines: list[dict[str, Any]]) -> tuple[Decimal, Decimal]:
        total_debit = Decimal("0")
        total_credit = Decimal("0")
        for line in lines:
            debit = Decimal(str(line.get("debit_amount", 0)))
            credit = Decimal(str(line.get("credit_amount", 0)))
            if debit < 0 or credit < 0:
                raise PostingValidationError("Line amounts must not be negative.")
            if debit > 0 and credit > 0:
                raise PostingValidationError(
                    "A line cannot have both a debit and a credit amount."
                )
            if debit == 0 and credit == 0:
                raise PostingValidationError(
                    "A line must have a non-zero debit or credit amount."
                )
            total_debit += debit
            total_credit += credit
        return total_debit, total_credit

    # ------------------------------------------------------------------
    # Manual lifecycle: submit / approve / reject
    # ------------------------------------------------------------------

    def submit(
        self, company_id: UUID, journal_id: UUID, actor_id: UUID | None
    ) -> JournalEntry:
        entry = self._get_entry(company_id, journal_id)
        JournalEntryStateMachine.validate_transition(
            entry.status, JournalEntryStatus.SUBMITTED.value
        )
        before = self._snapshot(entry)
        entry.status = JournalEntryStatus.SUBMITTED.value
        self._audit.record(
            company_id=company_id,
            entity_type="JournalEntry",
            entity_id=entry.id,
            action="SUBMITTED",
            actor_id=actor_id,
            before=before,
            after=self._snapshot(entry),
        )
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def approve(
        self, company_id: UUID, journal_id: UUID, approver_id: UUID | None
    ) -> JournalEntry:
        """Approve a SUBMITTED entry. Rejects self-approval by the creator
        and requires the ``accounting.journal.approve`` permission (SoD).

        Raises:
            SelfApprovalNotAllowedError: ``approver_id`` created this entry.
            ApprovalPermissionDeniedError: approver lacks the permission.
        """
        entry = self._get_entry(company_id, journal_id)
        JournalEntryStateMachine.validate_transition(
            entry.status, JournalEntryStatus.APPROVED.value
        )
        if (
            entry.created_by is not None
            and approver_id is not None
            and entry.created_by == approver_id
        ):
            raise SelfApprovalNotAllowedError(entry.journal_number)
        if not user_has_accounting_permission(
            self.db, company_id, approver_id, "accounting.journal.approve"
        ):
            raise ApprovalPermissionDeniedError("accounting.journal.approve")

        before = self._snapshot(entry)
        entry.status = JournalEntryStatus.APPROVED.value
        approval = JournalApproval(
            company_id=company_id,
            journal_entry_id=entry.id,
            approver_user_id=approver_id,
            approval_status=ApprovalStatus.APPROVED.value,
            approved_at=utcnow(),
        )
        self.db.add(approval)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="JournalEntry",
            entity_id=entry.id,
            action="APPROVED",
            actor_id=approver_id,
            before=before,
            after=self._snapshot(entry),
        )
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def reject(
        self,
        company_id: UUID,
        journal_id: UUID,
        actor_id: UUID | None,
        rejection_reason: str,
    ) -> JournalEntry:
        entry = self._get_entry(company_id, journal_id)
        JournalEntryStateMachine.validate_transition(
            entry.status, JournalEntryStatus.REJECTED.value
        )
        # RBAC gap fixed during pre-Epic-9 hardening audit (2026-08-14):
        # reject is the mirror decision of approve() on the same SUBMITTED
        # entry and had no permission check at all. Reuses the same
        # accounting.journal.approve permission code approve() requires.
        if not user_has_accounting_permission(
            self.db, company_id, actor_id, "accounting.journal.approve"
        ):
            raise ApprovalPermissionDeniedError("accounting.journal.approve")
        before = self._snapshot(entry)
        entry.status = JournalEntryStatus.REJECTED.value
        approval = JournalApproval(
            company_id=company_id,
            journal_entry_id=entry.id,
            approver_user_id=actor_id,
            approval_status=ApprovalStatus.REJECTED.value,
            rejection_reason=rejection_reason,
        )
        self.db.add(approval)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="JournalEntry",
            entity_id=entry.id,
            action="REJECTED",
            actor_id=actor_id,
            before=before,
            after=self._snapshot(entry),
            reason=rejection_reason,
        )
        self.db.commit()
        self.db.refresh(entry)
        return entry

    # ------------------------------------------------------------------
    # Posting — the 8-step pipeline (T093)
    # ------------------------------------------------------------------

    def post(
        self, company_id: UUID, journal_id: UUID, actor_id: UUID | None
    ) -> PostingResult:
        """Post an existing DRAFT (under-threshold) or APPROVED journal entry.

        Runs the full validation pipeline (Steps 1-5), assigns a gap-free
        journal number (Step 6), finalizes the entry (Step 7), and
        publishes ``accounting.journal.posted`` (Step 8).

        Raises:
            JournalEntryNotFoundError
            InvalidJournalStateTransitionError: Entry is not DRAFT/APPROVED.
            PostingValidationError: Any of Steps 1-5 fails.
        """
        entry = self._get_entry(company_id, journal_id)
        journal_number, posted_at = self._finalize_posting_uncommitted(entry, actor_id)
        self.db.commit()
        self.db.refresh(entry)
        self._publish_posted_event(entry, actor_id, posted_at)
        return PostingResult(
            journal_entry_id=entry.id,
            journal_number=journal_number,
            posted_at=posted_at,
        )

    def batch_post(
        self, company_id: UUID, journal_ids: list[UUID], actor_id: UUID | None
    ) -> list[PostingResult]:
        """Post multiple existing journal entries atomically — all or none.

        Every entry runs the same Steps 1-7 as ``post()`` (via
        ``_finalize_posting_uncommitted``), all staged in the SAME
        transaction. If any entry fails validation, nothing in the batch is
        committed — the whole batch rolls back together (tasks.md T122;
        plan.md Phase 4 acceptance criteria: "Batch posting is atomic: if
        one entry in batch fails, no entries are posted").

        Raises:
            JournalEntryNotFoundError, InvalidJournalStateTransitionError,
            PostingValidationError: Same as ``post()`` — propagates from
                whichever entry in the batch failed first; no entry in the
                batch is posted.
        """
        entries = [self._get_entry(company_id, jid) for jid in journal_ids]
        try:
            staged = [
                (entry, *self._finalize_posting_uncommitted(entry, actor_id))
                for entry in entries
            ]
        except Exception:
            self.db.rollback()
            raise

        self.db.commit()

        results: list[PostingResult] = []
        for entry, journal_number, posted_at in staged:
            self.db.refresh(entry)
            self._publish_posted_event(entry, actor_id, posted_at)
            results.append(
                PostingResult(
                    journal_entry_id=entry.id,
                    journal_number=journal_number,
                    posted_at=posted_at,
                )
            )
        return results

    def post_direct(
        self,
        company_id: UUID,
        journal_type: str,
        posting_source: str,
        posting_date: date,
        lines: list[dict[str, Any]],
        currency_code: str | None = None,
        exchange_rate: Decimal = Decimal("1"),
        reference: str | None = None,
        description: str | None = None,
        notes: str | None = None,
        source_document_type: str | None = None,
        source_document_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> PostingResult:
        """Create AND post a journal in one atomic transaction.

        No DRAFT/SUBMIT/APPROVE lifecycle — used by integration handlers
        (auto-posted entries) and any manual caller bypassing the approval
        workflow. Matches tasks.md T094 "auto-posted entries skip to
        POSTED directly."

        Thin wrapper over ``stage_direct_posting()`` + ``finalize_and_publish()``
        — callers that need to add MORE writes to the same DB transaction
        before committing (e.g. Phase 6's AR integration, which must create
        an ``ARTransaction`` atomically with the GL entry) should call those
        two methods directly instead of this one.
        """
        entry, journal_number, posted_at = self.stage_direct_posting(
            company_id=company_id,
            journal_type=journal_type,
            posting_source=posting_source,
            posting_date=posting_date,
            lines=lines,
            currency_code=currency_code,
            exchange_rate=exchange_rate,
            reference=reference,
            description=description,
            notes=notes,
            source_document_type=source_document_type,
            source_document_id=source_document_id,
            actor_id=actor_id,
        )
        return self.finalize_and_publish(entry, journal_number, posted_at, actor_id)

    def stage_direct_posting(
        self,
        company_id: UUID,
        journal_type: str,
        posting_source: str,
        posting_date: date,
        lines: list[dict[str, Any]],
        currency_code: str | None = None,
        exchange_rate: Decimal = Decimal("1"),
        reference: str | None = None,
        description: str | None = None,
        notes: str | None = None,
        source_document_type: str | None = None,
        source_document_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> tuple[JournalEntry, str, datetime]:
        """Stage a create+post operation WITHOUT committing.

        Adds and flushes the entry, lines, and audit records into the
        current session but does not commit or publish the domain event —
        the caller may add further writes (e.g. an ``ARTransaction``) to
        the SAME session and must call ``finalize_and_publish()`` to
        commit everything together atomically.
        """
        entry = self._build_entry_and_lines(
            company_id=company_id,
            journal_type=journal_type,
            posting_source=posting_source,
            posting_date=posting_date,
            lines=lines,
            currency_code=currency_code,
            exchange_rate=exchange_rate,
            reference=reference,
            description=description,
            notes=notes,
            source_document_type=source_document_type,
            source_document_id=source_document_id,
            created_by=actor_id,
        )
        self._audit.record(
            company_id=company_id,
            entity_type="JournalEntry",
            entity_id=entry.id,
            action="CREATED",
            actor_id=actor_id,
            after=self._snapshot(entry),
        )
        journal_number, posted_at = self._finalize_posting_uncommitted(entry, actor_id)
        return entry, journal_number, posted_at

    def finalize_and_publish(
        self,
        entry: JournalEntry,
        journal_number: str,
        posted_at: datetime,
        actor_id: UUID | None,
    ) -> PostingResult:
        """Commit the current transaction, refresh ``entry``, and publish
        ``accounting.journal.posted``. Pairs with ``stage_direct_posting()``.
        """
        self.db.commit()
        self.db.refresh(entry)
        self._publish_posted_event(entry, actor_id, posted_at)
        return PostingResult(
            journal_entry_id=entry.id,
            journal_number=journal_number,
            posted_at=posted_at,
        )

    def _finalize_posting_uncommitted(
        self, entry: JournalEntry, actor_id: UUID | None
    ) -> tuple[str, datetime]:
        """Run Steps 1-7 against ``entry``, staging all writes via flush.

        Does NOT commit and does NOT publish the domain event — callers
        (``post``, ``post_direct``, ``reverse``) control the commit/publish
        boundary so ``reverse()`` can finalize the reversal AND flip the
        original entry's status within a single transaction.
        """
        JournalEntryStateMachine.validate_transition(
            entry.status, JournalEntryStatus.POSTED.value
        )

        lines = self._lines.find_by_journal_entry(entry.id)

        # Step 1: balance
        total_debit = sum((line.debit_amount for line in lines), Decimal("0"))
        total_credit = sum((line.credit_amount for line in lines), Decimal("0"))
        if total_debit != total_credit:
            raise PostingValidationError("Journal must balance")

        # Step 2: accounts exist, active, leaf
        accounts_by_id = {}
        for line in lines:
            account = self._accounts.get_by_id_or_none(
                id=line.account_id, company_id=entry.company_id
            )
            if account is None or not account.is_active or not account.is_leaf:
                raise PostingValidationError(f"Invalid account: {line.account_code}")
            accounts_by_id[line.account_id] = account

        # Step 3: posting_date falls in an OPEN fiscal period
        period = self._periods.find_open_period_for_date(
            entry.company_id, entry.posting_date
        )
        if period is None or period.status != FiscalPeriodStatus.OPEN.value:
            raise PostingValidationError("Period is locked/closed")

        # Step 4: cost center required
        for line in lines:
            account = accounts_by_id[line.account_id]
            if account.requires_cost_center and line.cost_center_id is None:
                raise PostingValidationError(
                    f"Cost center required for account: {line.account_code}"
                )

        # Step 5: approval required above threshold (only reachable for
        # DRAFT entries — APPROVED already cleared governance; SUBMITTED/
        # REJECTED/POSTED/REVERSED were already rejected by the transition
        # check above).
        if entry.status == JournalEntryStatus.DRAFT.value and self._flags.is_enabled(
            entry.company_id, "accounting.approvalworkflow.enabled"
        ):
            config = self._config_repo.get_for_company(company_id=entry.company_id)
            threshold = config.journal_approval_threshold if config else None
            if threshold is not None and max(total_debit, total_credit) > threshold:
                raise PostingValidationError("Approval required")

        # Step 6: gap-free journal number
        journal_number = self._sequences.generate_next_journal_number(entry.company_id)

        # Step 7: finalize
        before = self._snapshot(entry)
        posted_at = utcnow()
        entry.journal_number = journal_number
        entry.status = JournalEntryStatus.POSTED.value
        entry.posted_at = posted_at
        entry.posted_by_user_id = actor_id
        entry.fiscal_period_id = period.id
        entry.fiscal_year_id = period.fiscal_year_id
        entry.total_debit_base = total_debit
        entry.total_credit_base = total_credit
        entry.is_balanced = True

        self._audit.record(
            company_id=entry.company_id,
            entity_type="JournalEntry",
            entity_id=entry.id,
            action="POSTED",
            actor_id=actor_id,
            before=before,
            after=self._snapshot(entry),
        )
        return journal_number, posted_at

    def _publish_posted_event(
        self, entry: JournalEntry, actor_id: UUID | None, posted_at: datetime
    ) -> None:
        get_event_bus().publish(
            JournalPostedEvent(
                event_type="accounting.journal.posted",
                aggregate_type="JournalEntry",
                aggregate_id=entry.id,
                company_id=entry.company_id,
                actor_id=actor_id,
                journal_entry_id=entry.id,
                journal_number=entry.journal_number,
                journal_type=entry.journal_type,
                posting_source=entry.posting_source,
                posting_date=entry.posting_date.isoformat(),
                total_debit_base=entry.total_debit_base,
                total_credit_base=entry.total_credit_base,
                posted_at=posted_at,
            )
        )

    # ------------------------------------------------------------------
    # Reversal (spec.md §15.5)
    # ------------------------------------------------------------------

    def reverse(
        self,
        company_id: UUID,
        journal_id: UUID,
        actor_id: UUID | None,
        reason: str | None = None,
    ) -> JournalEntry:
        """Reverse a POSTED entry: create a new entry with swapped DR/CR lines.

        Both the reversal (posted immediately) and the original's
        ``REVERSED`` status transition commit in a single transaction.

        Raises:
            JournalNotReversibleError: ``original`` is not POSTED.
        """
        original = self._get_entry(company_id, journal_id)
        if original.status != JournalEntryStatus.POSTED.value:
            raise JournalNotReversibleError(original.journal_number, original.status)

        original_lines = self._lines.find_by_journal_entry(original.id)
        reversal_lines_input: list[dict[str, Any]] = [
            {
                "account_id": line.account_id,
                "debit_amount": line.credit_amount,
                "credit_amount": line.debit_amount,
                "currency_code": line.currency_code,
                "exchange_rate": line.exchange_rate,
                "cost_center_id": line.cost_center_id,
                "department_id": line.department_id,
                "project_id": line.project_id,
                "description": line.description,
                "reference": line.reference,
            }
            for line in original_lines
        ]

        reversal_entry = self._build_entry_and_lines(
            company_id=company_id,
            journal_type=JournalType.REVERSING.value,
            posting_source=original.posting_source,
            posting_date=utcnow().date(),
            lines=reversal_lines_input,
            currency_code=original.currency_code,
            exchange_rate=original.exchange_rate,
            reference=original.reference,
            description=f"Reversal of {original.journal_number}",
            notes=reason,
            source_document_type=original.source_document_type,
            source_document_id=original.source_document_id,
            created_by=actor_id,
        )
        reversal_entry.reversal_of_journal_id = original.id
        reversal_entry.is_reversal = True
        self.db.flush()

        self._audit.record(
            company_id=company_id,
            entity_type="JournalEntry",
            entity_id=reversal_entry.id,
            action="CREATED",
            actor_id=actor_id,
            after=self._snapshot(reversal_entry),
            reason=reason,
        )
        journal_number, posted_at = self._finalize_posting_uncommitted(
            reversal_entry, actor_id
        )

        JournalEntryStateMachine.validate_transition(
            original.status, JournalEntryStatus.REVERSED.value
        )
        before = self._snapshot(original)
        original.status = JournalEntryStatus.REVERSED.value
        self._audit.record(
            company_id=company_id,
            entity_type="JournalEntry",
            entity_id=original.id,
            action="REVERSED",
            actor_id=actor_id,
            before=before,
            after=self._snapshot(original),
            reason=reason,
        )

        self.db.commit()
        self.db.refresh(original)
        self.db.refresh(reversal_entry)

        self._publish_posted_event(reversal_entry, actor_id, posted_at)
        get_event_bus().publish(
            JournalReversedEvent(
                event_type="accounting.journal.reversed",
                aggregate_type="JournalEntry",
                aggregate_id=original.id,
                company_id=company_id,
                actor_id=actor_id,
                original_journal_entry_id=original.id,
                original_journal_number=original.journal_number,
                reversal_journal_entry_id=reversal_entry.id,
                reversal_journal_number=journal_number,
                reason=reason,
            )
        )
        return reversal_entry

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_journal(self, company_id: UUID, journal_id: UUID) -> JournalEntry:
        return self._get_entry(company_id, journal_id)

    def get_lines(self, journal_id: UUID) -> list[JournalLine]:
        return self._lines.find_by_journal_entry(journal_id)

    def _get_entry(self, company_id: UUID, journal_id: UUID) -> JournalEntry:
        entry = self._journals.get_by_id_or_none(id=journal_id, company_id=company_id)
        if entry is None:
            raise JournalEntryNotFoundError(journal_entry_id=str(journal_id))
        return entry

    @staticmethod
    def _snapshot(entry: JournalEntry) -> dict[str, Any]:
        return {
            "id": str(entry.id),
            "journal_number": entry.journal_number,
            "status": entry.status,
            "journal_type": entry.journal_type,
            "posting_source": entry.posting_source,
            "posting_date": (
                entry.posting_date.isoformat() if entry.posting_date else None
            ),
            "total_debit_base": str(entry.total_debit_base),
            "total_credit_base": str(entry.total_credit_base),
        }
