"""T106 (FR-RPT-094) — with CRM disabled, every ``crm.*`` key is
not-entitled **unconditionally** — no servicing-continuity carve-out,
unlike Installments (T110/T111's ``InstallmentsServicingContinuityGate``,
which deliberately keeps servicing existing contracts alive for
disabled-entitlement tenants). CRM's own pre-existing
``require_crm_enabled`` gate has no such allowlist: it denies purely on
``CrmFeatureFlagService.is_enabled()``, regardless of whether the company
already has CRM data (leads/opportunities/activities)."""

from __future__ import annotations

import inspect
import uuid

import pytest
from sqlalchemy.orm import Session

from modules.crm.dependencies import require_crm_enabled
from modules.crm.exceptions import CrmFeatureDisabledError
from modules.crm.models.lead import Lead

# Matches ``catalog_crm.py``'s 4 registered keys. Not derived from
# ``REPORT_REGISTRY`` here deliberately — importing any ``catalog_*``
# module registers its entries into the shared, process-lifetime
# ``_REGISTRY`` singleton (``modules.reports.registry.definitions``),
# which would leak into every other test in the same pytest session
# (notably ``test_registry_consistency.py``'s Phase-0 "empty registry"
# assertion). Catalog imports are deliberately deferred to Gate 2 (T125),
# which owns full-registry population for the whole test session.
_CRM_REPORT_KEYS = {"crm.pipeline", "crm.leads", "crm.activities", "crm.dashboard"}


def test_require_crm_enabled_denies_with_no_flag_override(db_session: Session) -> None:
    """Defaults to disabled when no override row exists (feature_flag_service
    docstring's own documented default) — every ``crm.*`` key is therefore
    unreachable without an explicit enable, for every key in the registry."""
    company_id = uuid.uuid4()
    for _key in _CRM_REPORT_KEYS:
        with pytest.raises(CrmFeatureDisabledError):
            require_crm_enabled(company_id, db_session)


def test_require_crm_enabled_denies_even_with_existing_crm_data(
    db_session: Session,
) -> None:
    """The gate denies unconditionally — presence of existing CRM data
    (unlike Installments' contract-continuity carve-out) does not grant
    any continued access."""
    company_id = uuid.uuid4()
    db_session.add(
        Lead(
            company_id=company_id,
            first_name="A",
            last_name="Test",
            email="a-test@example.com",
            status="NEW",
        )
    )
    db_session.commit()

    with pytest.raises(CrmFeatureDisabledError):
        require_crm_enabled(company_id, db_session)


def test_no_servicing_continuity_concept_exists_in_crm_gate() -> None:
    """Structural guard: CRM's feature-gate code has no allowlist/continuity
    concept — that machinery is exclusively Installments' (T110)."""
    import modules.crm.dependencies as crm_deps_mod
    import modules.crm.services.feature_flag_service as crm_flag_mod

    for module in (crm_deps_mod, crm_flag_mod):
        source = inspect.getsource(module).lower()
        assert "continuity" not in source
        assert "allowlist" not in source
