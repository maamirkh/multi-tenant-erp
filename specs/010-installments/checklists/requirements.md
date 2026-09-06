# Specification Quality Checklist: Epic 10 — Installments

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-24
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — *Note: per the mandatory repository-inspection instructions for this Epic, the spec names existing repository constructs (e.g., `PostingEngine`, `FiscalPeriod`, `ModuleEnablementProvider`, `SupportAccessGrant`) only to define integration boundaries with already-completed epics, not to prescribe Epic 10's own implementation. This matches the established precedent in `specs/009a-platform-admin/spec.md` (which similarly names `CompanyContext`, `erp_active_company_id`, `CompanySuspendedError`). No database schema, endpoint shape, or technology choice is prescribed for Epic 10 itself.*
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — three Open Questions (OQ-1–OQ-3) were raised and are all **permanently resolved** in §34 (OQ-2 and OQ-3 resolved as final product decisions during the 2026-08-24 targeted-correction pass); none are pending or block `/sp.plan`.
- [x] Requirements are testable and unambiguous — all FR-INST-XXX requirements use MUST/MUST NOT phrasing with concrete, checkable conditions.
- [x] Success criteria are measurable (§30, SC-001–SC-007)
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined (§29, Scenarios A–L — 12 scenarios, matching the mandatory minimum)
- [x] Edge cases are identified (§28 — 10 edge cases)
- [x] Scope is clearly bounded (§3 Non-Goals, §31 Out of Scope)
- [x] Dependencies and assumptions identified (§5, §6)

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria (cross-referenced to §29 Acceptance Scenarios and §10 Business Rules/Invariants)
- [x] User scenarios cover primary flows (§8, US-1–US-8, prioritized P1–P3)
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification (see Content Quality note above for the one deliberate, justified exception)

## Notes

- This specification exceeds the required minimum of 30 sections (§48 of the governing prompt) by design, given the breadth of the 51-topic source prompt; all 30 mandatory topics are present and cross-indexed in the Table of Contents.
- All 20 mandatory invariants (§49 of the governing prompt) are encoded as BR-INST-001–BR-INST-022 in [§10](../spec.md#10-business-rules--invariants) (22 rules — the 20 mandated plus 2 repository-specific additions: BR-INST-021 fiscal-period locking, BR-INST-022 currency immutability).
- Repository conflicts discovered and resolved are documented as Assumptions A4 (money precision) and A1/epic-sequence note (Epic 10 vs. stale Epic 11 reference) rather than left as open contradictions.
- **2026-08-24 targeted-correction pass**: three inconsistencies were corrected — (1) entitlement-disabled servicing policy (collection/settlement against existing contracts now explicitly permitted; only new origination is blocked — FR-INST-353–358, BR-INST-014, Scenario K, OQ-2); (2) one-active-contract-per-obligation contradiction removed (FR-INST-042, FR-INST-251, OQ-3, §31); (3) lifecycle consistency — `REJECTED` clarified as a non-persisted approval outcome (FR-INST-102) and `DEFAULTED → ACTIVE` (cure) / `DEFAULTED → COMPLETED` (payoff) added as explicit enumerated transitions (FR-INST-104/105/222). All three corrections re-validated against this checklist; no new failures introduced.
- Ready directly for `/sp.plan` — no `/sp.clarify` needed; both previously-open questions are now permanent product decisions.
