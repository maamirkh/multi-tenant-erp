"""Platform RBAC constants — single source of truth for the permission
catalogue and candidate role bundles (spec.md §15.1/§15.2, plan.md §8).

Both are defined as **data**, not enum members — new permission codes or
role bundles are addable without a code change (FR-9A-140,
Constitution §46's configuration-over-hardcoding philosophy, applied at
the Platform layer). They seed `platform_permissions`/`platform_roles`
rows starting Phase 5 (bootstrap/RBAC); this module does not itself write
to the database.
"""

from __future__ import annotations

# ── Permission catalogue (spec.md §15.1) ────────────────────────────────────
# Every literal code spec.md §15.1's "Permission Areas" table enumerates,
# across all 15 areas. Cross-checked against every `x-permission` value in
# contracts/platform-admin-v1.yaml — the contract's 21 currently-wired codes
# are a strict subset of this 29-code catalogue; the remaining 8 (tenant
# export/bulk_suspend, configuration.*, notifications.*, export.generate)
# are future-ready per spec.md §15.1 but not yet exposed by an HTTP route.
PLATFORM_PERMISSION_CODES: frozenset[str] = frozenset(
    {
        # Dashboard
        "platform.dashboard.view",
        # Tenant inspection
        "platform.tenants.read",
        "platform.tenants.export",
        # Tenant lifecycle
        "platform.tenants.suspend",
        "platform.tenants.reactivate",
        "platform.tenants.bulk_suspend",
        # Plans
        "platform.plans.read",
        "platform.plans.manage",
        # Subscriptions
        "platform.subscriptions.read",
        "platform.subscriptions.manage",
        # Entitlements
        "platform.entitlements.read",
        "platform.entitlements.override",
        # Quotas
        "platform.quotas.read",
        "platform.quotas.override",
        # Platform Administrators
        "platform.admins.read",
        "platform.admins.manage",
        # Platform RBAC
        "platform.rbac.read",
        "platform.rbac.manage",
        # Support access
        "platform.support_access.initiate",
        "platform.support_access.read",
        # Audit logs
        "platform.audit.read",
        # Operational monitoring
        "platform.monitoring.read",
        # Platform configuration
        "platform.configuration.read",
        "platform.configuration.manage",
        # Notifications
        "platform.notifications.read",
        "platform.notifications.manage",
        # AI usage/cost
        "platform.ai_usage.read",
        "platform.ai_credits.adjust",
        # Export/reporting
        "platform.export.generate",
    }
)


# ── Candidate role bundles (spec.md §15.2) ──────────────────────────────────
# "Candidates to be confirmed during Plan/product review, not mandatory
# hardcoded roles" (spec.md §15.2) — plain data (code, name, permission
# codes), never enum members, so Phase 5's RBAC seeding can add/drop/rename
# bundles without touching this catalogue's shape.
CANDIDATE_PLATFORM_ROLE_BUNDLES: tuple[dict[str, object], ...] = (
    {
        "code": "platform_owner",
        "name": "Platform Owner / Super Admin",
        # "All permissions, including platform.admins.manage and
        # platform.rbac.manage (bootstrap authority)" — spec.md §15.2.
        "permission_codes": frozenset(PLATFORM_PERMISSION_CODES),
    },
    {
        "code": "platform_operations_admin",
        "name": "Platform Operations Admin",
        # "Tenant, plan, subscription, entitlement, quota, configuration,
        # monitoring permissions — excludes platform.admins.manage,
        # platform.rbac.manage, platform.ai_credits.adjust" — spec.md §15.2.
        "permission_codes": frozenset(
            {
                "platform.tenants.read",
                "platform.tenants.export",
                "platform.tenants.suspend",
                "platform.tenants.reactivate",
                "platform.tenants.bulk_suspend",
                "platform.plans.read",
                "platform.plans.manage",
                "platform.subscriptions.read",
                "platform.subscriptions.manage",
                "platform.entitlements.read",
                "platform.entitlements.override",
                "platform.quotas.read",
                "platform.quotas.override",
                "platform.configuration.read",
                "platform.configuration.manage",
                "platform.monitoring.read",
            }
        ),
    },
    {
        "code": "support_admin",
        "name": "Support Admin",
        # "platform.tenants.read, platform.support_access.initiate,
        # platform.support_access.read, platform.audit.read (scoped to
        # support-access history)" — spec.md §15.2.
        "permission_codes": frozenset(
            {
                "platform.tenants.read",
                "platform.support_access.initiate",
                "platform.support_access.read",
                "platform.audit.read",
            }
        ),
    },
    {
        "code": "billing_subscription_admin",
        "name": "Billing/Subscription Admin",
        # "platform.plans.*, platform.subscriptions.*, platform.entitlements.*,
        # platform.quotas.*, platform.ai_credits.adjust" — spec.md §15.2.
        "permission_codes": frozenset(
            {
                "platform.plans.read",
                "platform.plans.manage",
                "platform.subscriptions.read",
                "platform.subscriptions.manage",
                "platform.entitlements.read",
                "platform.entitlements.override",
                "platform.quotas.read",
                "platform.quotas.override",
                "platform.ai_credits.adjust",
            }
        ),
    },
    {
        "code": "security_audit_admin",
        "name": "Security/Audit Admin",
        # "platform.audit.read, platform.monitoring.read, platform.admins.read,
        # platform.rbac.read, platform.support_access.read" — spec.md §15.2.
        "permission_codes": frozenset(
            {
                "platform.audit.read",
                "platform.monitoring.read",
                "platform.admins.read",
                "platform.rbac.read",
                "platform.support_access.read",
            }
        ),
    },
    {
        "code": "read_only_platform_analyst",
        "name": "Read-Only Platform Analyst",
        # "*.read across all domains; no write permissions" — spec.md §15.2.
        # Every catalogue code whose action is read-only (`.read`/`.view`);
        # `platform.export.generate` is deliberately excluded even though it
        # is read-adjacent, since generating an export is a mutation-like
        # action, not a pure read.
        "permission_codes": frozenset(
            code
            for code in PLATFORM_PERMISSION_CODES
            if code.endswith(".read") or code.endswith(".view")
        ),
    },
)
