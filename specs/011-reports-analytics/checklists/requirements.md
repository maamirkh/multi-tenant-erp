# Specification Quality Checklist: Epic 11 — Reports & Analytics

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-11
**Last revalidated**: 2026-09-11 (targeted correction pass; final micro-correction pass)
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — *Note: per the mandatory repository-inspection instructions for this Epic, the spec names existing repository constructs (e.g., `FinancialStatementService`, `PostingEngine`, `AccountingIntegrationGateway`, `PlatformEntitlementService`, `CapabilitySeedService`, `DefaultAlwaysEnabledModuleProvider`, `StandardResponse`/`PaginatedResponse`, `DueStateCalculator`) only to define integration/reuse boundaries with already-completed epics. This matches the established precedent in `specs/010-installments/spec.md` and `specs/009a-platform-admin/spec.md`. No database schema, endpoint shape, or technology choice is prescribed for Epic 11's own new work.*
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — zero markers in spec.md (verified via grep at initial creation and after both correction passes).
- [x] Requirements are testable and unambiguous — all 149 `FR-RPT-XXX` requirements (143 original + 5 from the targeted correction pass + 1 from this final micro-correction pass: FR-RPT-116) use MUST/MUST NOT phrasing with concrete, checkable conditions, grounded in cited repository evidence rather than invented behavior.
- [x] Success criteria are measurable (§47, SC-001–SC-008)
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined (§46, Scenarios A–O — 15 scenarios after this pass, up from 12)
- [x] Edge cases are identified (§45 — 16 edge cases; two rewritten for consistency in this pass)
- [x] Scope is clearly bounded (§3 Non-Goals — 10 items, §51 Out of Scope — 13 items)
- [x] Dependencies and assumptions identified (§5 — 11 assumptions: A1–A10 original, A11 added during the targeted correction pass; A3 and A6 substantively rewritten)

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria (cross-referenced to §46 Acceptance Scenarios and inline citations throughout §12–§44)
- [x] User scenarios cover primary flows (§11, US-1–US-8, prioritized P1–P3)
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Deliverable Coverage (Epic-11-specific, per the governing `/sp.specify` prompt)

- [x] Source-of-Truth Matrix present and repository-corrected (§7) — **corrected during this pass**: the Inventory valuation row no longer flatly declares "Inventory-owned, not Accounting-owned"; it now states authority is genuinely unresolved/incomplete (ADR-0004, Status: Proposed, never Accepted), citing Inventory's operational WAC figure and Accounting's unpopulated seeded GL inventory accounts side by side (Assumption A11).
- [x] Report Catalog present with no "TBD" rows (§9) — every row has authoritative source, permission, entitlement, branch behavior, filters, measures, drill-down, export, and Now/Deferred status; the Inventory Valuation row is renamed "Operational Stock Valuation (WAC)" with an explicit unreconciled-with-Accounting disclaimer.
- [x] KPI / Metric Catalog present (§10) — 16 metrics, each with exactly one authoritative definition; the Sales-vs-Accounting "margin" naming conflict remains resolved (distinct names), and the Inventory Value metric is renamed "Operational Inventory Value (WAC)" (`metric.inventory.value_operational`) to prevent it being mistaken for a reconciled accounting balance.
- [x] Permission Matrix present (§33) grounded in the existing dot-notation RBAC convention, with an explicitly-labeled illustrative (non-enforced) role mapping — unchanged by this pass, re-validated as still accurate.
- [x] Entitlement Matrix present (§34) — **substantively corrected during this pass**: replaced the hedged "core module — verify in `/sp.plan`" language for Sales/Purchase/Inventory/Accounting with a definitive, evidence-backed statement that all six source modules are genuinely gated `grain=module` Capabilities, differing only in default-resolved state, not in whether a gate exists (Assumption A6, FR-RPT-254/255).
- [x] Security Matrix present (§36) covering tenant/branch/permission/entitlement/record-access/export per capability — unchanged by this pass, re-validated as still accurate.
- [x] Traceability — all requirements use stable `FR-RPT-NNN` identifiers; every requirement ID from the original pass was preserved (none renumbered), with new IDs appended within each section's existing numeric block (§28 of the correction-pass instructions).

## Correction-Pass-Specific Validation (2026-09-11)

- [x] **Branch authorization** — re-verified as no Branch entity/ACL exists; §25 now opens with the exact required statement ("Branch is NOT currently an authorization boundary in DevSphere ERP"); Assumption A3 strengthened; no wording anywhere in spec.md implies branch-level security exists (re-audited via full-text search for "branch access/ACL/authorized branch/branch permission/branch-scoped authorization" — all existing occurrences already correctly hedge this as future-only; confirmed no false claims after this pass).
- [x] **Branch Performance Summary** — confirmed still locked as Deferred (§9, FR-RPT-012); not shipped as "Now."
- [x] **Inventory valuation authority** — re-verified via full ADR-0004 text, `coa_templates.py`, `stock_service.py`, and the `TestInventoryAdjustmentGLGap` test's own docstring. Conclusion changed from "Inventory authoritative" to **"authority unresolved/incomplete"** (Outcome C) — corrected throughout §7, §9, §10, §16 (FR-RPT-071 rewritten, FR-RPT-074 added), §51, §52, and Assumption A11.
- [x] **Always-on modules vs. entitlements** — re-verified against `capability_seed_service.py`, `module_enablement.py`, and `api/v1/router.py` router-mount code for all six modules. Conclusion: all six are genuinely gated; none is structurally ungated. §34 entitlement matrix rewritten with a `Domain Default State` column; FR-RPT-254/255 added; former OQ-2 resolved and removed from the open-questions list.
- [x] **`reports.*` capability relationships** — reviewed; no redundant/contradictory double-gating found. The existing design (domain permission + domain entitlement + report-specific `.view`/`.export` permission + `reports` module entitlement) already matches the requested principle ("a report never grants access to a domain the tenant/user couldn't otherwise reach"); no change needed beyond FR-RPT-254's clarification that the check must remain live/dynamic, not hardcoded.
- [x] **Export row limit** — reframed (FR-RPT-214) from a fixed "50,000-row requirement" to a bounded-but-configurable invariant, with 50,000 demoted to a clearly-labeled non-binding planning candidate; format-specific (CSV vs. XLSX) differences explicitly permitted.
- [x] **Customer 360** — explicit "composite read model / analytical projection" framing added (§20.1) with a source-mapping table; compound authorization re-confirmed (FR-RPT-111); new partial-availability requirements added distinguishing "omitted (not entitled/permitted)" from "unavailable (not configured/no data)" from "confirmed zero" (FR-RPT-114/115).
- [x] **No scope expansion** — confirmed: no new report families were added; the only new catalog-adjacent content is the Customer 360 source-mapping table (clarifying an existing "Now" entry, not adding one) and FR-RPT-074 (a deferred-future-state placeholder, itself Out of Scope).
- [x] **Clean type baseline** — re-confirmed no proposed architecture depends on untyped dictionaries, arbitrary JSON query DSLs, or unchecked runtime report definitions (§49 unchanged).

## Final Micro-Correction-Pass Validation (2026-09-11)

- [x] **Installments entitlement / servicing-continuity contradiction** — resolved. FR-RPT-104 rewritten to explicitly split Case A (disabled, no obligations → normal denial) from Case B (disabled, obligations exist → read-only servicing-continuity). FR-RPT-252 (the generic disabled-domain rule) now explicitly states Installments as its one documented, narrowly-scoped exception, and explicitly states CRM has no such exception. §34's intro gained a dedicated "generic rule and its one documented exception" callout box. The entitlement matrix's Installments row, the Executive Dashboard's Installments widget rule (FR-RPT-041), the edge-case list (§45), and the acceptance scenarios (Scenario H = Case B, new Scenario M = Case A) all now tell the identical story — verified by a full-text contradiction search across "disabled Installments," "module not entitled," "FR-RPT-104," and "FR-RPT-251/252."
- [x] **Customer 360 entitlement wording** — resolved. Both the report-catalog row (§9) and the entitlement-matrix row (§34) rewritten from ambiguous "`reports` + `sales` + `accounting`; `+installments` if entitled" (which read as an AND-gate across every constituent domain) to explicit "section-level compound authorization, not all-or-nothing" wording, cross-referencing §20.2's existing FR-RPT-111/114/115 partial-composition behavior, which required no change (already correct).
- [x] **Customer 360 minimum useful response** — new FR-RPT-116 added: if every constituent section is unavailable, return the identity-only shell if the user is independently authorized to view the customer master record, otherwise deny with the platform's standard IDOR-safe "not found" response — never a distinguishable empty shell that leaks a customer's existence. New Scenario O added.
- [x] **Branch Performance open question** — OQ-3 converted from "recommended decision" to an explicit strikethrough **RESOLVED — DEFERRED** entry (matching OQ-2's resolved-entry style), with its promotion prerequisite (real populated `branch_id` data for at least one representative tenant, FR-RPT-012) restated as the sole condition for revisiting it.
- [x] **Reports capability default** — OQ-4 reviewed against the instruction to lock it now if evidence clearly supports one answer. Repository evidence cannot fully determine this (no `reports` Capability exists yet to inspect), so it remains an explicit, non-blocking `/sp.plan`-level recommendation (disabled-by-default) rather than being locked — this is a deliberate choice, not an oversight, and is now stated as such in §53.
- [x] **Contradiction audit** (§8 of the correction-pass instructions) — performed via full-text search for every listed term ("disabled Installments," "module not entitled," "every domain entitlement," "Customer 360 entitlement," "sales + accounting," "branch performance," "OQ-3," "FR-RPT-104," "FR-RPT-251," "FR-RPT-252"); all occurrences now agree.
- [x] **No scope expansion** — confirmed: this pass added zero new report families; all new content (FR-RPT-116, Scenarios M/N/O, the §34 exception callout) clarifies existing "Now" entries or resolves a stated contradiction, nothing else.

## Notes

- This specification now totals 54 sections (864 lines, up from 821 at original creation) across two correction passes — no sections were added or removed; all growth is within existing sections plus 6 new requirement IDs total (FR-RPT-074/114/115/254/255 from the targeted correction pass, FR-RPT-116 from this final micro-correction pass), all appended within their sections' existing numeric blocks, with zero renumbering of any existing requirement.
- The three most significant corrections across both passes — inventory valuation authority (Outcome C: unresolved/incomplete), the entitlement default-state finding (all six modules genuinely gated; none structurally exempt), and the Installments servicing-continuity exception (now explicitly reconciled with the generic disabled-domain rule rather than silently contradicting it) — were each re-verified against primary repository evidence or resolved through explicit rule-reconciliation, not left as an implicit tension for `/sp.plan` to discover.
- Ready directly for `/sp.plan` — no `/sp.clarify` needed. OQ-1 and OQ-4 remain recorded as recommended, non-blocking planning decisions with stated rationale; OQ-2 and OQ-3 are both fully resolved (OQ-2 from repository evidence, OQ-3 by explicit lock in the final micro-correction pass).
