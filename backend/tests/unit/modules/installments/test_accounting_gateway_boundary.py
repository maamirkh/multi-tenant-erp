"""Structural/import-lint boundary check for AccountingIntegrationGateway.

Covers tasks.md T046: confirms ``accounting_gateway.py`` contains no
``from modules.accounting.models`` / ``from modules.accounting.repositories``
import — the single controlled Installments -> Accounting module
boundary crosses only through Accounting's own service layer. Mirrors
the Platform-Admin/CRM structural-boundary test convention
(``tests/integration/repositories/crm/test_cross_module_integration.py``'s
``test_no_sales_module_ships_a_raw_orm_import_in_conversion_service``).

This test is re-run unmodified after Phase 6 extends the same class with
money-mutating staged/finalize methods (plan.md §12.3.4) — it must keep
passing then too.
"""

from __future__ import annotations

import inspect

import modules.installments.services.accounting_gateway as mod


class TestAccountingIntegrationGatewayImportBoundary:
    def test_no_accounting_models_import(self) -> None:
        source = inspect.getsource(mod)
        assert "from modules.accounting.models" not in source

    def test_no_accounting_repositories_import(self) -> None:
        source = inspect.getsource(mod)
        assert "from modules.accounting.repositories" not in source

    def test_imports_accounting_services_only(self) -> None:
        """[Phase 6, T107] Loosened from an exact single-line import
        match to two substring checks so this test survives Phase 6's
        multi-name import from the same module (isort/black legitimately
        wraps ``ar_service``'s import across several names now that
        ``StagedAdjustment``/``StagedWriteOff`` joined
        ``AccountsReceivableService``) without weakening the check's
        actual intent: that the AR service is imported from Accounting's
        service layer, never its models/repositories."""
        source = inspect.getsource(mod)
        assert "from modules.accounting.services.ar_service import" in source
        assert "AccountsReceivableService" in source
