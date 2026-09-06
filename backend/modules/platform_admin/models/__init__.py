"""Platform Administration module ORM models.

All models are imported here to ensure the test suite's
``Base.metadata.create_all()`` can resolve every Platform table.

Import order follows dependency order (parent before child tables) —
``PlatformAuditEvent``/``PlatformSession`` reference ``PlatformAdministrator``
via FK, ``PlatformRefreshToken`` references ``PlatformSession``, the
RBAC join tables (``PlatformRolePermission``, ``PlatformAdminRoleAssignment``)
reference ``PlatformPermission``/``PlatformRole``/``PlatformAdministrator``,
and the Phase-8 SaaS control-plane models (``Capability``, ``Plan``,
``PlanCapability``, ``Subscription``, ``QuotaDefinition``, ``PlanQuota``,
``TenantQuotaOverride``) reference each other and ``PlatformAdministrator``.
The Phase-11 override/usage/AI-readiness models (``EntitlementOverride``,
``UsageRecord``, ``AiCreditLedgerEntry``) reference ``Company``,
``PlatformAdministrator``, and (for ``UsageRecord``) ``QuotaDefinition``.
The Phase-12 ``SupportAccessGrant`` references ``Company`` and
``PlatformAdministrator`` (twice — initiator and, nullable, terminator).
"""

from modules.platform_admin.models.ai_credit_ledger import AiCreditLedgerEntry
from modules.platform_admin.models.capability import Capability
from modules.platform_admin.models.entitlement_override import EntitlementOverride
from modules.platform_admin.models.plan import Plan
from modules.platform_admin.models.plan_capability import PlanCapability
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_audit_event import PlatformAuditEvent
from modules.platform_admin.models.platform_rbac import (
    PlatformAdminRoleAssignment,
    PlatformPermission,
    PlatformRole,
    PlatformRolePermission,
)
from modules.platform_admin.models.platform_refresh_token import PlatformRefreshToken
from modules.platform_admin.models.platform_session import PlatformSession
from modules.platform_admin.models.quota import (
    PlanQuota,
    QuotaDefinition,
    TenantQuotaOverride,
)
from modules.platform_admin.models.subscription import Subscription
from modules.platform_admin.models.support_access_grant import SupportAccessGrant
from modules.platform_admin.models.usage_record import UsageRecord

__all__ = [
    "AiCreditLedgerEntry",
    "Capability",
    "EntitlementOverride",
    "Plan",
    "PlanCapability",
    "PlanQuota",
    "PlatformAdminRoleAssignment",
    "PlatformAdministrator",
    "PlatformAuditEvent",
    "PlatformPermission",
    "PlatformRefreshToken",
    "PlatformRole",
    "PlatformRolePermission",
    "PlatformSession",
    "QuotaDefinition",
    "Subscription",
    "SupportAccessGrant",
    "TenantQuotaOverride",
    "UsageRecord",
]
