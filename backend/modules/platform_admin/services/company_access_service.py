"""assert_company_access_allowed — company-scoped access invalidation
(T082, FR-9A-017, ADR-6).

Two layers, checked in one shared helper so every company-scoped route in
the five business modules gets both for free by depending on
``get_current_company_member``/``get_current_company`` (T083/T084):

  Layer 1 — company status: denies when the ``Company`` is ``suspended``
  or ``deleted``.

  Layer 2 — authentication-freshness watermark: denies when the tenant
  ``Session`` that authenticated this request predates
  ``Company.access_invalidated_at`` — i.e. the user authenticated
  *before* the company was (most recently) suspended, and has not
  performed a genuine new login since.

Deliberately compares ``Session.created_at`` (set once, at login, never
advanced by a refresh) — **never** the access token's `iat` claim, which
a refresh *does* advance. Using `iat` would let a pre-suspension refresh
credential mint a fresh token after reactivation and silently restore
access without genuine re-authentication (plan.md §10.2, Correction 1).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session as OrmSession

from modules.auth.models.session import Session as TenantSession
from modules.companies.exceptions import CompanyNotFoundError, CompanySuspendedError
from modules.companies.models.company import Company
from modules.companies.models.enums import CompanyStatus


def assert_company_access_allowed(
    db: OrmSession, company_id: UUID, session_id: UUID | None
) -> None:
    """Raise if access to *company_id* is denied for the request
    authenticated by *session_id*.

    Status-code mapping matches ``get_current_company``'s pre-existing,
    already-shipped behaviour exactly (suspended -> 403
    ``CompanySuspendedError``, deleted -> 404 ``CompanyNotFoundError``) —
    calling this helper from ``get_current_company`` is therefore a
    byte-identical replacement for its manual checks (T084), and calling
    it from ``get_current_company_member`` (T083) adds the same two
    checks where none existed before (closing the §3.3 gap).

    A company with no ``access_invalidated_at`` watermark (every company
    that predates Epic 9A, and any company that has never been suspended)
    denies nothing on Layer 2 — this is what makes rollout safe (T086).

    Company non-existence is intentionally a no-op here, not an error:
    callers that need a genuine 404 for a missing/invalid ``company_id``
    already handle that themselves.
    """
    company = db.get(Company, company_id)
    if company is None:
        return

    if company.status == CompanyStatus.suspended.value:
        raise CompanySuspendedError()
    if company.status == CompanyStatus.deleted.value:
        raise CompanyNotFoundError()

    if company.access_invalidated_at is None:
        return

    session = db.get(TenantSession, session_id) if session_id is not None else None
    if session is None or session.created_at <= company.access_invalidated_at:
        raise CompanySuspendedError()
