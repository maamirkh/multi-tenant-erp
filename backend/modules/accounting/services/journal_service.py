"""JournalEntryService — journal lifecycle facade — Phase 5.

Thin delegating wrapper around ``PostingEngine`` for the capabilities
tasks.md T120-T122 name at this file/class location. Reversal (T120) and
self-approval prevention (T121) were already implemented and fully tested
directly inside ``PostingEngine`` in Phase 4 (``reverse()``/``approve()``)
— ``PostingEngine`` IS "the single GL posting gate" (research.md Decision
2), so re-implementing the same validation here would violate DRY and
create a second code path that could drift out of sync. This class
delegates those two, and owns the one genuinely new capability from this
phase: ``batch_post()`` (T122), whose atomic-batch implementation lives on
``PostingEngine`` itself (it needs direct access to the same
``_finalize_posting_uncommitted`` internals reversal/post already use).

Spec ref: specs/008-accounting-finance/tasks.md T120, T121, T122
"""

from __future__ import annotations

from uuid import UUID

from modules.accounting.models.gl import JournalEntry
from modules.accounting.services.posting_engine import PostingEngine, PostingResult


class JournalEntryService:
    """Facade over ``PostingEngine`` for reversal, approval, and batch posting."""

    def __init__(self, posting_engine: PostingEngine) -> None:
        self._engine = posting_engine

    def reverse_journal(
        self,
        company_id: UUID,
        journal_id: UUID,
        actor_id: UUID | None,
        reason: str | None = None,
    ) -> JournalEntry:
        """Reverse a POSTED journal entry. See ``PostingEngine.reverse()``."""
        return self._engine.reverse(company_id, journal_id, actor_id, reason)

    def approve_journal(
        self, company_id: UUID, journal_id: UUID, approver_id: UUID | None
    ) -> JournalEntry:
        """Approve a SUBMITTED journal entry. Self-approval prevention is
        enforced inside ``PostingEngine.approve()`` — see
        ``SelfApprovalNotAllowedError``.
        """
        return self._engine.approve(company_id, journal_id, approver_id)

    def batch_post(
        self, company_id: UUID, journal_ids: list[UUID], actor_id: UUID | None
    ) -> list[PostingResult]:
        """Post multiple journal entries atomically — all or none.

        See ``PostingEngine.batch_post()`` for the atomicity guarantee.
        """
        return self._engine.batch_post(company_id, journal_ids, actor_id)
