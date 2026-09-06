"""Unit tests for FeatureFlagService (Phase 0 — T019).

Tests cover:
  - is_enabled() with no override → returns system default
  - is_enabled() with override → returns override value
  - is_enabled() with unknown key → returns False
  - enable() creates / updates override
  - disable() creates / updates override
  - get_all() returns merged flag list
  - _validate_key() raises ValueError for unknown key
  - Tenant isolation (different companies see different states)
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from modules.inventory.constants import (
    INVENTORY_FEATURE_FLAGS,
    INVENTORY_FLAG_BY_KEY,
)
from modules.inventory.models.feature_flag import InventoryFeatureFlag
from modules.inventory.repositories.feature_flag_repository import FeatureFlagRepository
from modules.inventory.services.feature_flag_service import FeatureFlagService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_service(flag_repo: FeatureFlagRepository | None = None) -> FeatureFlagService:
    """Create a FeatureFlagService with a mock or provided repository."""
    if flag_repo is None:
        flag_repo = MagicMock(spec=FeatureFlagRepository)
    db = MagicMock()
    return FeatureFlagService(db=db, flag_repo=flag_repo)


def _make_override(
    flag_key: str, is_enabled: bool, company_id: uuid.UUID | None = None
) -> InventoryFeatureFlag:
    """Create a mock InventoryFeatureFlag ORM instance."""
    override = MagicMock(spec=InventoryFeatureFlag)
    override.flag_key = flag_key
    override.is_enabled = is_enabled
    override.company_id = company_id or uuid.uuid4()
    return override


# ---------------------------------------------------------------------------
# is_enabled — system defaults
# ---------------------------------------------------------------------------


class TestIsEnabledSystemDefaults:
    def test_enabled_by_default_flag_returns_true_when_no_override(self) -> None:
        enabled_key = next(f.key for f in INVENTORY_FEATURE_FLAGS if f.default_enabled)
        repo = MagicMock(spec=FeatureFlagRepository)
        repo.get_by_key.return_value = None
        svc = _make_service(repo)
        assert svc.is_enabled(uuid.uuid4(), enabled_key) is True

    def test_disabled_by_default_flag_returns_false_when_no_override(self) -> None:
        disabled_key = next(
            f.key for f in INVENTORY_FEATURE_FLAGS if not f.default_enabled
        )
        repo = MagicMock(spec=FeatureFlagRepository)
        repo.get_by_key.return_value = None
        svc = _make_service(repo)
        assert svc.is_enabled(uuid.uuid4(), disabled_key) is False

    def test_unknown_key_returns_false(self) -> None:
        repo = MagicMock(spec=FeatureFlagRepository)
        repo.get_by_key.return_value = None
        svc = _make_service(repo)
        assert svc.is_enabled(uuid.uuid4(), "inventory.unknown_feature_xyz") is False


# ---------------------------------------------------------------------------
# is_enabled — company overrides
# ---------------------------------------------------------------------------


class TestIsEnabledWithOverrides:
    def test_override_true_overrides_disabled_default(self) -> None:
        disabled_key = next(
            f.key for f in INVENTORY_FEATURE_FLAGS if not f.default_enabled
        )
        repo = MagicMock(spec=FeatureFlagRepository)
        repo.get_by_key.return_value = _make_override(disabled_key, is_enabled=True)
        svc = _make_service(repo)
        assert svc.is_enabled(uuid.uuid4(), disabled_key) is True

    def test_override_false_overrides_enabled_default(self) -> None:
        enabled_key = next(f.key for f in INVENTORY_FEATURE_FLAGS if f.default_enabled)
        repo = MagicMock(spec=FeatureFlagRepository)
        repo.get_by_key.return_value = _make_override(enabled_key, is_enabled=False)
        svc = _make_service(repo)
        assert svc.is_enabled(uuid.uuid4(), enabled_key) is False

    def test_company_id_passed_to_repository(self) -> None:
        company_id = uuid.uuid4()
        flag_key = INVENTORY_FEATURE_FLAGS[0].key
        repo = MagicMock(spec=FeatureFlagRepository)
        repo.get_by_key.return_value = None
        svc = _make_service(repo)
        svc.is_enabled(company_id, flag_key)
        repo.get_by_key.assert_called_once_with(
            company_id=company_id, flag_key=flag_key
        )


# ---------------------------------------------------------------------------
# enable / disable
# ---------------------------------------------------------------------------


class TestEnableDisable:
    def test_enable_calls_upsert_with_true(self) -> None:
        flag_key = INVENTORY_FEATURE_FLAGS[0].key
        company_id = uuid.uuid4()
        actor_id = uuid.uuid4()
        repo = MagicMock(spec=FeatureFlagRepository)
        svc = _make_service(repo)
        svc.enable(company_id=company_id, flag_key=flag_key, actor_id=actor_id)
        repo.upsert.assert_called_once_with(
            company_id=company_id,
            flag_key=flag_key,
            is_enabled=True,
            created_by=actor_id,
            description=None,
        )

    def test_disable_calls_upsert_with_false(self) -> None:
        flag_key = INVENTORY_FEATURE_FLAGS[0].key
        company_id = uuid.uuid4()
        repo = MagicMock(spec=FeatureFlagRepository)
        svc = _make_service(repo)
        svc.disable(company_id=company_id, flag_key=flag_key)
        repo.upsert.assert_called_once_with(
            company_id=company_id,
            flag_key=flag_key,
            is_enabled=False,
            created_by=None,
            description=None,
        )

    def test_enable_with_description_passes_it_to_upsert(self) -> None:
        flag_key = INVENTORY_FEATURE_FLAGS[0].key
        repo = MagicMock(spec=FeatureFlagRepository)
        svc = _make_service(repo)
        svc.enable(
            company_id=uuid.uuid4(),
            flag_key=flag_key,
            description="Enabled for beta testing",
        )
        call_kwargs = repo.upsert.call_args.kwargs
        assert call_kwargs["description"] == "Enabled for beta testing"

    def test_enable_unknown_key_raises_value_error(self) -> None:
        repo = MagicMock(spec=FeatureFlagRepository)
        svc = _make_service(repo)
        with pytest.raises(ValueError, match="Unknown inventory feature flag key"):
            svc.enable(uuid.uuid4(), "inventory.nonexistent_key")

    def test_disable_unknown_key_raises_value_error(self) -> None:
        repo = MagicMock(spec=FeatureFlagRepository)
        svc = _make_service(repo)
        with pytest.raises(ValueError, match="Unknown inventory feature flag key"):
            svc.disable(uuid.uuid4(), "inventory.nonexistent_key")


# ---------------------------------------------------------------------------
# get_all
# ---------------------------------------------------------------------------


class TestGetAll:
    def test_returns_all_known_flags(self) -> None:
        repo = MagicMock(spec=FeatureFlagRepository)
        repo.get_all_for_company.return_value = []
        svc = _make_service(repo)
        result = svc.get_all(uuid.uuid4())
        assert len(result) == len(INVENTORY_FEATURE_FLAGS)

    def test_override_is_reflected_in_result(self) -> None:
        disabled_key = next(
            f.key for f in INVENTORY_FEATURE_FLAGS if not f.default_enabled
        )
        override = _make_override(disabled_key, is_enabled=True)
        repo = MagicMock(spec=FeatureFlagRepository)
        repo.get_all_for_company.return_value = [override]
        svc = _make_service(repo)
        result = svc.get_all(uuid.uuid4())
        flag_result = next(r for r in result if r["flag_key"] == disabled_key)
        assert flag_result["is_enabled"] is True
        assert flag_result["is_overridden"] is True

    def test_non_overridden_flag_shows_system_default(self) -> None:
        enabled_key = next(f.key for f in INVENTORY_FEATURE_FLAGS if f.default_enabled)
        repo = MagicMock(spec=FeatureFlagRepository)
        repo.get_all_for_company.return_value = []
        svc = _make_service(repo)
        result = svc.get_all(uuid.uuid4())
        flag_result = next(r for r in result if r["flag_key"] == enabled_key)
        assert flag_result["is_enabled"] is True
        assert flag_result["is_overridden"] is False

    def test_result_contains_required_keys(self) -> None:
        repo = MagicMock(spec=FeatureFlagRepository)
        repo.get_all_for_company.return_value = []
        svc = _make_service(repo)
        result = svc.get_all(uuid.uuid4())
        assert result  # non-empty
        for item in result:
            assert "flag_key" in item
            assert "label" in item
            assert "description" in item
            assert "is_enabled" in item
            assert "is_overridden" in item
            assert "default_enabled" in item


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    def test_different_companies_see_different_states(self) -> None:
        flag_key = INVENTORY_FEATURE_FLAGS[0].key
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()

        override_a = _make_override(flag_key, is_enabled=True, company_id=company_a)

        def side_effect(company_id: uuid.UUID, flag_key: str):  # noqa: ANN202
            if company_id == company_a:
                return override_a
            return None

        repo = MagicMock(spec=FeatureFlagRepository)
        repo.get_by_key.side_effect = side_effect

        svc = _make_service(repo)
        assert svc.is_enabled(company_a, flag_key) is True
        # company_b falls back to system default
        definition = INVENTORY_FLAG_BY_KEY[flag_key]
        assert svc.is_enabled(company_b, flag_key) is definition.default_enabled
