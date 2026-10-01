# Epic 11 — Reports & Analytics: Phase 0 Research

Consolidated technical decisions from repository re-inspection of `backend/modules/{platform_admin,users_roles,installments,crm,accounting,sales,purchase,inventory}` and `frontend/src`. Each entry resolves one open technical question the spec deliberately left to `/sp.plan` (spec §53 OQ-1/OQ-4, and several implementation-shape questions the spec's governing prompt explicitly deferred). Full supporting detail and file:line citations live in `plan.md` §2.

---

## R1. Report Registry storage mechanism

- **Decision**: Static, code-defined `dict[str, ReportDefinition]` assembled at import time from per-domain `catalog_<domain>.py` modules, not a database table.
- **Rationale**: Confirmed no analogous "registry" pattern exists as a DB table anywhere in the repo; `INITIAL_PERMISSIONS` (`modules/users_roles/constants.py`) is the closest precedent — a code-defined, unioned tuple of typed definitions, seeded into the DB only as a *result*, never edited live. Spec Assumption A7 already mandates this. A DB-backed registry would require its own CRUD/versioning/migration machinery for something the platform team, not tenants, curates — unjustified complexity (Constitution §7 KISS/YAGNI).
- **Alternatives considered**: Database-backed metadata table with an admin UI (rejected — turns a curated catalog into a dynamic one, violating NG1's "no arbitrary query engine" spirit and requiring new CRUD/audit/versioning surface for zero requested benefit); JSON config file loaded at startup (rejected — loses static type-checking, the exact property `mypy . = 0` depends on).

## R2. Domain entitlement enforcement point for Reports

- **Decision**: Domain entitlement (`sales`/`purchase`/`inventory`/`accounting`/`crm`/`installments`) is resolved **inside** `ReportExecutionService`, per request, via `PlatformEntitlementService.resolve_effective_entitlement()` — not via a second router-mount gate per domain.
- **Rationale**: Reports has one router serving report keys spanning six domains dynamically; router-mount gates (the pattern every other module uses, `api/v1/router.py:122-183`) only work when one router == one domain. Installments already proves per-service-method entitlement checking is an accepted repository pattern (`InstallmentAccessPolicy.authorize()`), not a novel one.
- **Alternatives considered**: Six separate report sub-routers, one per domain, each with its own `require_capability_entitled(...)` mount (rejected — defeats the point of one unified execution path and one registry-driven dispatch, reintroducing exactly the per-module inconsistency Epic 11 exists to remove); a single combined "any domain" gate (rejected — cannot express FR-RPT-251's "reports enabled must never imply a domain is enabled").

## R3. `reports` Capability default-resolved state and enablement mechanism

- **Decision**: `reports` is a `grain=module` Capability (mirrors the existing six), registered with its own **explicit master toggle**, defaulting to disabled — a new `ReportsFeatureFlagService` + `ReportsModuleEnablementProvider`, not the four core modules' `DefaultAlwaysEnabledModuleProvider`.
- **Rationale**: Spec FR-RPT-255 recommends disabled-by-default (opt-in add-on capability, matching the CRM/Installments precedent) and leaves the mechanism to `/sp.plan`. `get_module_enablement_provider()` (`platform_admin/services/module_enablement.py:99-110`) **raises `ValueError` for any unregistered capability key** — confirming a provider registration is mandatory, not optional, the moment `reports` is added to the Capability catalogue.
- **Alternatives considered**: `DefaultAlwaysEnabledModuleProvider` for `reports` (rejected — directly contradicts the disabled-by-default product decision; would require a *second* mechanism later to change the default, whereas a dedicated toggle service supports the decision natively today).

## R4. Installments Case A/B distinguishing seam

- **Decision**: A new `InstallmentsServicingContinuityGate` in Reports' own module, combining `PlatformEntitlementService.resolve_effective_entitlement(capability_key="installments")` with a call to Installments' own existing `InstallmentReportingService.get_contract_register(company_id, skip=0, limit=1)`, reading its `total` return value to detect "any contract exists at all."
- **Rationale**: Direct code inspection of `InstallmentAccessPolicy.authorize(operation=READ)` shows it **permits unconditionally, entitled or not** — it cannot by itself distinguish Case A (disabled, no obligations → unavailable) from Case B (disabled, obligations exist → read-only). The distinguishing signal must come from Reports, using a method that is already self-authorizing and requires zero new Installments code.
- **Alternatives considered**: Add a new `has_serviceable_obligations()` method to Installments' repository (viable, slightly cheaper query — rejected only as the *first* choice because it requires a cross-module code change to a different module's internals for a one-line optimization; noted in `plan.md` §40 as a non-blocking future refinement `/sp.tasks` may still choose); duplicate `InstallmentAccessPolicy`'s logic inside Reports (rejected outright — explicitly forbidden by the governing prompt's §14, and would drift the moment Installments' own policy changes).

## R5. Customer 360 result-state representation

- **Decision**: A Pydantic v2 discriminated union per section (`Field(discriminator="state")`) with three variants — `PRESENT` (real data, including a confirmed zero), `OMITTED` (authorization gate failed), `UNAVAILABLE` (authorized, but no data source / not configured) — rather than nullable fields or a flat "empty" collapse.
- **Rationale**: Spec FR-RPT-114 explicitly forbids collapsing these three states into an ambiguous null/empty representation; Pydantic v2's discriminated unions are the typed, `mypy`-checkable mechanism already idiomatic in this codebase's schema conventions (§32 of `plan.md`) — no repository precedent for a tri-state result exists to reuse verbatim, but the mechanism (discriminated union) is a standard, already-supported Pydantic v2 feature, not a new library.
- **Alternatives considered**: Three nullable fields plus a separate `state` enum field per section (rejected — allows structurally invalid combinations, e.g. `state=OMITTED` with `data` populated, that a discriminated union makes unrepresentable); a flat boolean `is_available` + optional data (rejected — cannot distinguish `OMITTED` from `UNAVAILABLE`, which spec explicitly requires distinguishing for §20.2's authorization semantics).

## R6. Saved-view filter storage format

- **Decision**: JSONB column (`filter_config`) whose payload is validated against a versioned Pydantic model (`FilterConfigV1`, `extra="forbid"`) at write time, re-validated against the *report's current* `supported_filters` schema at load time; a companion `schema_version` integer column.
- **Rationale**: No existing JSONB-plus-version-field pattern exists anywhere in the repo to reuse (`plan.md` §2.8 confirms every existing JSONB column is untyped) — this establishes a new, minimal, justified convention rather than free-form JSON (spec FR-RPT-201/023 explicitly forbid storing arbitrary query expressions).
- **Alternatives considered**: A fully normalized relational schema for filter/grouping/sorting/column config (rejected — massive schema surface for what is fundamentally a small, bounded configuration object; JSONB with app-level validation is the proportionate choice, consistent with how `installments.plan_template`'s own bounded-but-flexible policy fields already use JSONB); free-form untyped JSON with no validation (rejected outright — explicitly forbidden by spec FR-RPT-201).

## R7. Pagination contract for the wrapped GL report

- **Decision**: A new, Reports-module-local `CursorPage[T]` schema (`items`, `has_more`, `next_cursor`), used **only** for `accounting.gl` — every other list-shaped report uses the existing `PaginatedResponse[T]`.
- **Rationale**: `ReportService.get_gl_report()` (`modules/accounting/services/report_service.py:64-96`) is the only genuinely cursor-paginated report in the repository (built for 500K+ row scale, explicit in its own docstring) — forcing it into an offset/page-number shape would either break at scale or require a lossy, incorrect translation. The governing prompt explicitly permits a documented per-report exception here rather than a forced universal abstraction.
- **Alternatives considered**: Force GL into `PaginatedResponse[T]` by internally paginating via repeated cursor advances until the requested page is reached (rejected — reintroduces the O(n) "walk from the start" cost cursor pagination exists specifically to avoid, defeating its own purpose at exactly the scale it was built for).

## R8. Export return-shape normalization

- **Decision**: `ReportExportService.export(...) -> tuple[bytes, str, str]` (bytes, filename, content_type) — Reports' own new contract, matching Sales' existing shape exactly (the most complete of the four existing shapes) — with each of the four existing modules' export services left untouched.
- **Rationale**: `plan.md` §2.7 confirms Accounting/Sales/Purchase/Inventory each return a different tuple shape today; introducing a fifth, Reports-owned shape and normalizing at the adapter boundary is cheaper and lower-risk than retrofitting all four existing services to a common interface (which the governing prompt's §57 "no mass refactor" explicitly discourages).
- **Alternatives considered**: Retrofit a shared `ExportResult` return type onto all four existing export services (rejected — out-of-scope refactor of four already-tested, unrelated modules for a benefit only Reports needs); reuse Accounting's `bytes`-only shape (rejected — loses filename/content-type information the router needs to set `Content-Disposition`, which callers currently reconstruct ad hoc).

## R9. CSV formula-injection mitigation scope

- **Decision**: A new, centralized `services/csv_sanitizer.py::sanitize_cell()` applied to every cell Reports' own CSV/XLSX export writes; the four pre-existing export services in Sales/Purchase/Inventory/Accounting are **not** retrofitted.
- **Rationale**: Grep across the repository confirms zero existing formula-injection protection anywhere — this is a genuine, previously undiscovered gap (not previously flagged in any spec). Fixing it centrally in Reports' own new code is in-scope and required (spec FR-RPT-216); retrofitting four unrelated, already-shipped modules is a separate remediation effort outside Epic 11's boundary (governing prompt §58 bug-discovery policy — documented, not silently buried, see `plan.md` §36 Risk Register).
- **Alternatives considered**: Silently ignore the gap in the other four modules (rejected — governing prompt explicitly requires documenting discovered bugs, not burying them); fix it in all five places as part of Epic 11 (rejected — scope creep into four modules with their own owners/test suites, no defect report requesting it, and Epic 11's own spec never asked for it).

## R10. Charting library

- **Decision**: Recharts.
- **Rationale**: SVG-based (accessible, stylable, testable like ordinary DOM), mature/actively maintained (Constitution §26), React-19-compatible composable component API, and the only genuine trend/comparison charting need across ~7 report families — a single sparkline (Accounting's existing hand-rolled inline SVG in `KPICard.tsx`) is not sufficient for Executive Dashboard trend lines and period comparisons.
- **Alternatives considered**: visx (rejected — lower-level, more implementation code per chart than this epic's scope justifies); Chart.js/react-chartjs-2 (rejected — canvas-based, materially weaker native accessibility story); Nivo (rejected — heavier bundle for equivalent chart types); no library, hand-rolled SVG everywhere (rejected — reasonable for one sparkline, not for genuine multi-series trend/comparison charts across the whole reporting surface).

## R11. Frontend data-fetching pattern to standardize on

- **Decision**: Installments' existing pattern — TanStack Query + a `lib/api/<module>.ts` thin wrapper over the shared `apiClient` singleton + a tenant-scoped query-key factory.
- **Rationale**: `plan.md` §2.9 confirms this is the most modern of four inconsistent existing patterns (Accounting/CRM use manual `useEffect`/`fetch`; Purchase/Inventory's KPI pages bypass `lib/api` entirely). Standardizing Reports on the best existing pattern is consistent with governing-prompt §57's "no mass refactor" — it doesn't retrofit the other four, it just doesn't repeat their weaker pattern in new code.
- **Alternatives considered**: Introduce a fifth, entirely new data-fetching convention (rejected — no justification to invent a new pattern when a good one already exists in the same codebase); copy Accounting's manual `useEffect` pattern for consistency with the module Reports wraps most (Accounting) (rejected — that pattern is the one the repo's own evidence shows is weaker, not one to propagate into new code).

---

**Output of this phase**: all technical unknowns the spec deliberately deferred to `/sp.plan` (§53 OQ-1/OQ-4, and the implementation-shape questions above) are now resolved with a decision, rationale, and rejected alternatives. `plan.md` §40 tracks the small number of genuinely non-blocking parameter values (exact export row limits, exact permission-code string for Sales' customer-view check, etc.) that remain intentionally open for `/sp.tasks`/implementation-time confirmation — none of which affect this research's architectural conclusions.
