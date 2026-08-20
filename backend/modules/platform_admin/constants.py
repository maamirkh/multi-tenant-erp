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
#
# Extended in Phase 5 (T062) with `label`/`area` per code — the seed
# service needs this metadata to populate `platform_permissions` rows
# (NOT NULL `label`/`area`, migration 057); `PLATFORM_PERMISSION_CODES`
# below is derived FROM this catalogue, not maintained separately, so the
# two structures cannot drift apart.
PLATFORM_PERMISSION_CATALOGUE: tuple[dict[str, str], ...] = (
    {
        "code": "platform.dashboard.view",
        "label": "View Platform Dashboard",
        "area": "Dashboard",
    },
    {
        "code": "platform.tenants.read",
        "label": "View Tenants",
        "area": "Tenant inspection",
    },
    {
        "code": "platform.tenants.export",
        "label": "Export Tenant Data",
        "area": "Tenant inspection",
    },
    {
        "code": "platform.tenants.suspend",
        "label": "Suspend Tenant",
        "area": "Tenant lifecycle",
    },
    {
        "code": "platform.tenants.reactivate",
        "label": "Reactivate Tenant",
        "area": "Tenant lifecycle",
    },
    {
        "code": "platform.tenants.bulk_suspend",
        "label": "Bulk Suspend Tenants",
        "area": "Tenant lifecycle",
    },
    {"code": "platform.plans.read", "label": "View Plans", "area": "Plans"},
    {"code": "platform.plans.manage", "label": "Manage Plans", "area": "Plans"},
    {
        "code": "platform.subscriptions.read",
        "label": "View Subscriptions",
        "area": "Subscriptions",
    },
    {
        "code": "platform.subscriptions.manage",
        "label": "Manage Subscriptions",
        "area": "Subscriptions",
    },
    {
        "code": "platform.entitlements.read",
        "label": "View Entitlements",
        "area": "Entitlements",
    },
    {
        "code": "platform.entitlements.override",
        "label": "Override Entitlements",
        "area": "Entitlements",
    },
    {"code": "platform.quotas.read", "label": "View Quotas", "area": "Quotas"},
    {"code": "platform.quotas.override", "label": "Override Quotas", "area": "Quotas"},
    {
        "code": "platform.admins.read",
        "label": "View Platform Administrators",
        "area": "Platform Administrators",
    },
    {
        "code": "platform.admins.manage",
        "label": "Manage Platform Administrators",
        "area": "Platform Administrators",
    },
    {
        "code": "platform.rbac.read",
        "label": "View Platform Roles",
        "area": "Platform RBAC",
    },
    {
        "code": "platform.rbac.manage",
        "label": "Manage Platform Roles",
        "area": "Platform RBAC",
    },
    {
        "code": "platform.support_access.initiate",
        "label": "Initiate Support Access",
        "area": "Support access",
    },
    {
        "code": "platform.support_access.read",
        "label": "View Support Access History",
        "area": "Support access",
    },
    {
        "code": "platform.audit.read",
        "label": "View Platform Audit Log",
        "area": "Audit logs",
    },
    {
        "code": "platform.monitoring.read",
        "label": "View Operational Health",
        "area": "Operational monitoring",
    },
    {
        "code": "platform.configuration.read",
        "label": "View Platform Configuration",
        "area": "Platform configuration",
    },
    {
        "code": "platform.configuration.manage",
        "label": "Manage Platform Configuration",
        "area": "Platform configuration",
    },
    {
        "code": "platform.notifications.read",
        "label": "View Platform Notifications",
        "area": "Notifications",
    },
    {
        "code": "platform.notifications.manage",
        "label": "Manage Platform Notifications",
        "area": "Notifications",
    },
    {
        "code": "platform.ai_usage.read",
        "label": "View AI Usage",
        "area": "AI usage/cost",
    },
    {
        "code": "platform.ai_credits.adjust",
        "label": "Adjust AI Credits",
        "area": "AI usage/cost",
    },
    {
        "code": "platform.export.generate",
        "label": "Generate Platform Export",
        "area": "Export/reporting",
    },
)

PLATFORM_PERMISSION_CODES: frozenset[str] = frozenset(
    entry["code"] for entry in PLATFORM_PERMISSION_CATALOGUE
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
