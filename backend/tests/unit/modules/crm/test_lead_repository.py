"""Unit tests: LeadRepository.find_matching_customer_candidates() priority
order — email checked first, phone/legal_name only queried when the prior
tier found no match (spec.md §16.1). Uses a mocked DB session, per plan.md
§48.1's "in isolation from the DB" instruction — the three ``_match_by_*``
methods are monkeypatched directly rather than hitting a real database.

Each mock is kept as a named local variable (returned alongside the
repository) rather than re-read off the repository instance afterward —
mypy strict statically types ``LeadRepository``'s attributes by their
real, declared method signatures regardless of what is assigned to them at
runtime, so ``repo._match_by_email.assert_called_once()`` does not
type-check even though it works fine at runtime. Asserting against the
named mock variable directly needs no suppression and is equally clear.

Task: T033 (tasks.md Phase 3).
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock
from uuid import uuid4

from modules.crm.repositories.lead import LeadRepository


@dataclass
class _MockedRepo:
    repo: LeadRepository
    match_by_email: MagicMock
    match_by_phone: MagicMock
    match_by_legal_name: MagicMock


def _repo_with_mocked_matchers(
    *, email_result=None, phone_result=None, legal_name_result=None
) -> _MockedRepo:
    repo = LeadRepository(db=MagicMock())
    match_by_email = MagicMock(return_value=email_result or [])
    match_by_phone = MagicMock(return_value=phone_result or [])
    match_by_legal_name = MagicMock(return_value=legal_name_result or [])
    repo._match_by_email = match_by_email  # type: ignore[method-assign]
    repo._match_by_phone = match_by_phone  # type: ignore[method-assign]
    repo._match_by_legal_name = match_by_legal_name  # type: ignore[method-assign]
    return _MockedRepo(repo, match_by_email, match_by_phone, match_by_legal_name)


class TestFindMatchingCustomerCandidatesPriority:
    def test_email_match_short_circuits_phone_and_legal_name(self) -> None:
        customer = MagicMock()
        mocked = _repo_with_mocked_matchers(email_result=[customer])

        result = mocked.repo.find_matching_customer_candidates(
            uuid4(), email="a@b.com", phone="555-1234", legal_name="Acme Inc"
        )

        assert result == [customer]
        mocked.match_by_email.assert_called_once()
        mocked.match_by_phone.assert_not_called()
        mocked.match_by_legal_name.assert_not_called()

    def test_falls_through_to_phone_when_email_has_no_match(self) -> None:
        customer = MagicMock()
        mocked = _repo_with_mocked_matchers(phone_result=[customer])

        result = mocked.repo.find_matching_customer_candidates(
            uuid4(), email="a@b.com", phone="555-1234", legal_name="Acme Inc"
        )

        assert result == [customer]
        mocked.match_by_email.assert_called_once()
        mocked.match_by_phone.assert_called_once()
        mocked.match_by_legal_name.assert_not_called()

    def test_falls_through_to_legal_name_when_email_and_phone_have_no_match(
        self,
    ) -> None:
        customer = MagicMock()
        mocked = _repo_with_mocked_matchers(legal_name_result=[customer])

        result = mocked.repo.find_matching_customer_candidates(
            uuid4(), email="a@b.com", phone="555-1234", legal_name="Acme Inc"
        )

        assert result == [customer]
        mocked.match_by_email.assert_called_once()
        mocked.match_by_phone.assert_called_once()
        mocked.match_by_legal_name.assert_called_once()

    def test_returns_empty_list_when_nothing_matches(self) -> None:
        mocked = _repo_with_mocked_matchers()

        result = mocked.repo.find_matching_customer_candidates(
            uuid4(), email="a@b.com", phone="555-1234", legal_name="Acme Inc"
        )

        assert result == []

    def test_skips_email_tier_when_email_not_provided(self) -> None:
        customer = MagicMock()
        mocked = _repo_with_mocked_matchers(phone_result=[customer])

        result = mocked.repo.find_matching_customer_candidates(
            uuid4(), email=None, phone="555-1234", legal_name="Acme Inc"
        )

        assert result == [customer]
        mocked.match_by_email.assert_not_called()
        mocked.match_by_phone.assert_called_once()
