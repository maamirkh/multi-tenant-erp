# ADR-0006: Section-Level Compound Authorization for Cross-Module Composite Read Models

> **Scope**: Document decision clusters, not individual technology choices. Group related decisions that work together (e.g., "Frontend Stack" not separate ADRs for framework, styling, deployment).

- **Status:** Accepted
- **Date:** 2026-09-29
- **Feature:** 011-reports-analytics
- **Context:** Epic 11 introduced the platform's first cross-module composite read models. Customer 360 combines Sales, Accounting AR, CRM and Installments data for one customer. The Executive Dashboard combines 10 widgets from six domains. A tenant can be entitled to some of these domains and not others, and a user can hold some domain report permissions and not others. The spec's correction pass rejected an all-or-nothing gate (FR-RPT-111, FR-RPT-041). plan.md §37 flagged the resulting pattern as significant because future cross-module features will need the same rule. Implemented in Phases 4, 5 and 9; verified by the T167–T175 Customer 360 security tests and the T261/T262 entitlement and RBAC matrices.

<!-- Significance checklist (ALL must be true to justify this ADR)
     1) Impact: Long-term consequence for architecture/platform/security?
     2) Alternatives: Multiple viable options considered with tradeoffs?
     3) Scope: Cross-cutting concern (not an isolated detail)?
     If any are false, prefer capturing as a PHR note instead of an ADR. -->

## Decision

Authorize composite read models **per section**, with a **compound** check for every section:

1. **Base gate** for the composite itself: Reports entitlement plus the composite's own permission (`reports.customer_360.view` or `reports.executive.view`). A cross-tenant or unknown `customer_id` is a 404 raised by Sales' own `CustomerService.get_by_id()` (IDOR-safe).
2. **Each section or widget is evaluated independently**: the section's domain must be entitled for the tenant **and** the user must hold that domain's view permission (for example `reports.sales.view`). Holding the composite's permission never grants a domain's data by itself.
3. **Three distinct states**, never collapsed:
   - `present` — authorized and computed (a real zero is shown as zero);
   - `omitted` — an entitlement or permission check failed; the UI renders nothing, and the reported reason favors `not_entitled` over `not_permitted`;
   - `unavailable` — authorized, but a prerequisite is missing (for example no chart of accounts).
4. **Checks run before any cross-module call**, so an unauthorized section never triggers a read from another module.
5. **Each section reads through its source module's own public service**, tenant-scoped by that module. Nothing is cached, persisted or blended across sections.
6. Installments servicing continuity (Case A/B) is applied inside the Installments section, so it composes with the same rule.

## Consequences

### Positive

- Users see exactly what they would see in each module's own report — no privilege escalation through the composite.
- Partially entitled tenants still get a useful Customer 360 and Dashboard instead of a blanket denial.
- `omitted` versus `unavailable` versus a real zero keeps figures honest: missing data is never shown as 0.
- The rule is reusable: a future composite adds a section evaluator with the same entitlement → permission → fetch sequence.

### Negative

- More authorization checks per request (one entitlement and one permission check per section), and more combinations to test. Covered by the full entitlement and RBAC matrices (T261, T262).
- Response schemas are unions per section (`Present…` / `Omitted…` / `Unavailable…`), which is more complex for API consumers than a flat object.
- An omitted section is intentionally silent in the UI, so a user may not know why a section is missing; the reason is only in the API payload.

## Alternatives Considered

**Alternative A — All-or-nothing gate:** require every underlying domain permission and entitlement to open the composite at all. Rejected in the spec correction pass: it denies useful views to most real users and tenants, and pushes admins to over-grant permissions.

**Alternative B — Composite permission only** (`reports.customer_360.view` grants every section). Rejected: it lets a user read domain data they cannot see in that domain's own report — a privilege escalation path.

**Alternative C — Redacted placeholders** (show every section but mask values the user may not see). Rejected: it leaks which domains exist and are used by the tenant, and blurs the difference between "no access", "no data" and "zero".

## References

- Feature Spec: `specs/011-reports-analytics/spec.md` (FR-RPT-041, FR-RPT-111, FR-RPT-271)
- Implementation Plan: `specs/011-reports-analytics/plan.md` (§14, §37)
- Related ADRs: ADR-0005
- Code: `backend/modules/reports/services/customer_360_service.py`, `backend/modules/reports/services/dashboard_service.py`, `frontend/src/components/reports/DashboardWidgets.tsx`, `frontend/src/components/reports/Customer360Sections.tsx`
