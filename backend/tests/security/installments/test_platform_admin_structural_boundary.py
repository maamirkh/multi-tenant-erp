"""[Epic 10, Phase 11, T200] Structural/static test — Platform Admin's
support-access surface contains no import of Installments business-record
modules, mirroring the exact Epic 9A Phase 12 precedent
(``tests/security/modules/platform_admin/test_support_access_boundary.py``
``TestSupportAccessImportsNoBusinessRecordRepository``), extended to
include ``modules.installments``.

Scoping note (documented resolution of a tasks.md imprecision): T200's
literal text reads "modules.platform_admin contains no import of
modules.installments.models/.repositories/.services" — read as a
blanket, whole-package ban this would be **false**, since
``module_enablement.py`` (part of the approved, already-completed T032
architecture) legitimately imports
``modules.installments.repositories.feature_flag``/
``modules.installments.services.feature_flag_service`` — the SAME
governance-only pattern already exists for CRM
(``CrmFeatureFlagRepository``/``CrmFeatureFlagService`` in that same
file) and is explicitly sanctioned by BR-INST-002/FR-INST-002:
"entitlement governance != data access". The actual established
precedent test (T163, above) never checked the whole package either —
it scoped its check to exactly two files:
``support_access_service.py`` and ``platform_admin/router.py``. This
test applies that identical scope, not a broader one, which would
contradict the approved T032 architecture rather than test it.
"""

from __future__ import annotations

import ast
import inspect

_INSTALLMENTS_BUSINESS_RECORD_PREFIXES = (
    "modules.installments.models",
    "modules.installments.repositories",
    "modules.installments.services",
)

# The one approved, governance-only exception (T032/§15.4): reading the
# module's own enable/disable toggle is not business-record access.
_APPROVED_GOVERNANCE_IMPORTS = frozenset(
    {
        "modules.installments.repositories.feature_flag",
        "modules.installments.services.feature_flag_service",
    }
)


def _installments_business_record_imports(source: str) -> list[str]:
    tree = ast.parse(source)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module in _APPROVED_GOVERNANCE_IMPORTS:
                continue
            if any(
                node.module.startswith(p)
                for p in _INSTALLMENTS_BUSINESS_RECORD_PREFIXES
            ):
                violations.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _APPROVED_GOVERNANCE_IMPORTS:
                    continue
                if any(
                    alias.name.startswith(p)
                    for p in _INSTALLMENTS_BUSINESS_RECORD_PREFIXES
                ):
                    violations.append(alias.name)
    return violations


class TestPlatformAdminStructuralBoundary:
    def test_support_access_service_imports_no_installments_business_record_module(
        self,
    ) -> None:
        import modules.platform_admin.services.support_access_service as mod

        violations = _installments_business_record_imports(inspect.getsource(mod))
        assert violations == [], f"forbidden imports found: {violations}"

    def test_platform_admin_router_imports_no_installments_business_record_module(
        self,
    ) -> None:
        import modules.platform_admin.router as mod

        violations = _installments_business_record_imports(inspect.getsource(mod))
        assert violations == [], f"forbidden imports found: {violations}"

    def test_module_enablement_only_imports_the_approved_governance_path(
        self,
    ) -> None:
        """The one legitimate Installments import anywhere in
        ``platform_admin`` is confined to exactly the two approved
        governance names — nothing else from
        ``modules.installments.models``/``.repositories``/``.services``
        leaks in alongside it."""
        import modules.platform_admin.services.module_enablement as mod

        tree = ast.parse(inspect.getsource(mod))
        installments_imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("modules.installments"):
                    installments_imports.append(node.module)
        assert set(installments_imports) == _APPROVED_GOVERNANCE_IMPORTS
