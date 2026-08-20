"""Platform Administration module — Epic 9A, SaaS control plane.

Operates the DevSphere ERP SaaS platform itself (tenants, plans,
subscriptions, entitlements, quotas, platform administrators, support
access) — structurally distinct from tenant/company administration.

A `PlatformAdministrator` is a separate first-class Platform principal;
Platform authority is never derived from tenant `CompanyMember` roles
(BR-9A-001). Directory shape matches `modules/accounting/` (plan.md §4).
"""
