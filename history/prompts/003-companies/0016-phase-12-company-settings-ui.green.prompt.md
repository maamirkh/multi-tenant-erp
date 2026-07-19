---
id: "0016"
title: Phase 12 Company Settings UI
stage: green
date: 2026-07-16
surface: agent
model: claude-sonnet-4-6
feature: 003-companies
branch: 003-companies
user: shehla83
command: /sp.implement Phase 12 Company Settings UI
labels: ["phase-12","frontend","typescript","react","next.js","companies","settings","ui","components"]
links:
  spec: specs/003-companies/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/components/companies/CompanySettingsTabs.tsx
  - frontend/src/components/companies/CompanyProfileForm.tsx
  - frontend/src/components/companies/CompanyAddressForm.tsx
  - frontend/src/components/companies/CompanyRegionalSettingsForm.tsx
  - frontend/src/components/companies/CompanyLogoUpload.tsx
  - frontend/src/components/companies/CompanyBrandingForm.tsx
  - frontend/src/components/companies/CompanyPreferencesForm.tsx
  - frontend/src/components/companies/CompanyAuditLogTable.tsx
  - frontend/src/app/(protected)/(companies)/companies/[id]/settings/page.tsx
  - frontend/src/app/(protected)/(companies)/companies/[id]/settings/profile/page.tsx
  - frontend/src/app/(protected)/(companies)/companies/[id]/settings/regional/page.tsx
  - frontend/src/app/(protected)/(companies)/companies/[id]/settings/branding/page.tsx
  - frontend/src/app/(protected)/(companies)/companies/[id]/settings/preferences/page.tsx
  - frontend/src/app/(protected)/(companies)/companies/[id]/audit-log/page.tsx
  - frontend/src/__tests__/companies/CompanySettingsTabs.test.tsx
tests:
  - frontend/src/__tests__/companies/CompanySettingsTabs.test.tsx (7 tests — all pass)
  - Full suite: 95/95 tests pass (18 suites)
---

## Prompt

/sp.implement — Epic 3 Companies, Phase 12: Company Settings UI (T086–T096)

## Response snapshot

Implemented the full company settings UI for the Companies module:

**T086** — `CompanySettingsTabs.tsx`: horizontal tab nav with Profile, Regional, Branding, Preferences tabs; uses `usePathname()` to highlight active tab; `aria-selected` and `aria-current` for accessibility; keyboard navigation via native link focus.

**T087** — `CompanyProfileForm.tsx`: RHF + Zod form with 11 fields (legal_name, trade_name, email, phone × 2, website, tax_number, registration_number, business_category, business_type, incorporation_date); maps API `details[]` error array to field-level errors via `setError()`; `business_type` uses `setValueAs` to handle empty string → `undefined`; E.164 phone validation via `.refine`.

**T088** — `CompanyAddressForm.tsx`: address create/edit with `<datalist>` for searchable country input (60 ISO 3166 countries); 4 address types; `is_primary` checkbox; used in dialog from profile page.

**T089** — `CompanyRegionalSettingsForm.tsx`: currency (42 ISO 4217 codes via `<datalist>`), timezone (IANA, 50+ values), language (BCP 47, 40 locales), fiscal year start month; inline currency-change warning with confirmation checkbox; `setValueAs` for fiscal month (empty → `null`, else `parseInt`).

**T090** — `CompanyLogoUpload.tsx`: drag-and-drop zone; client-side validates type (PNG/JPG/SVG/WebP) and size (< 5 MB); `URL.createObjectURL` preview on selection; calls `useUploadLogo()` mutation; shows pending spinner; updates preview URL on success; displays error message on rejection.

**T091** — `CompanyBrandingForm.tsx`: wraps `CompanyLogoUpload`; primary + secondary hex color inputs with live color swatch preview; tagline input (max 255) with character counter; live preview panel with logo, color swatches, tagline, and company name; calls `useUpdateCompany()`.

**T092** — `CompanyPreferencesForm.tsx`: date format selector (6 options), decimal separator, thousands separator, invoice prefix, PO prefix; submits via `useCompanySettings()` mutation; serializes to `{ settings: { ... } }`.

**T093** — 5 settings page files:
- `settings/page.tsx`: server component that redirects to `/settings/profile`
- `settings/profile/page.tsx`: `CompanySettingsTabs` + `CompanyProfileForm` + inline address list with Add/Edit/Delete (dialogs rendered inline)
- `settings/regional/page.tsx`: `CompanySettingsTabs` + `CompanyRegionalSettingsForm`
- `settings/branding/page.tsx`: `CompanySettingsTabs` + `CompanyBrandingForm`
- `settings/preferences/page.tsx`: `CompanySettingsTabs` + `CompanyPreferencesForm`

**T094** — `audit-log/page.tsx`: date range inputs, action dropdown (11 action types), pagination state; calls `useCompanyAuditLog(id, filters)`; passes entries to `CompanyAuditLogTable`.

**T095** — `CompanyAuditLogTable.tsx`: table with timestamp, actor, action (monospace badge), details (collapsible JSON viewer for before/after state); loading skeleton; empty state; prev/next pagination controls.

**T096** — `CompanySettingsTabs.test.tsx`: 7 tests covering active tab by pathname, inactive tab has `aria-selected=false`, correct `href` for all 4 tabs, no tab active when on non-settings route.

**Bugs fixed:**
- Pages used `result.data.data` — `useCompany()` returns `CompanyDetail` directly as `.data`, not wrapped in `StandardResponse`. Fixed to `const { data: company } = useCompany(id)`.
- `exactOptionalPropertyTypes` mismatch in `CompanyAddressForm`: Zod-inferred type has `string | undefined` for optional fields but `CreateAddressInput` interface uses exact optional types. Fixed via a cast function `handleSubmitCast`.
- `messages[0]` can be `undefined` on empty array: fixed with `messages[0] ?? 'Validation error'` in `CompanyProfileForm`.

**Quality gate:**
- `npx tsc --noEmit` → 0 errors ✓
- `npx eslint` on all new files → 0 errors (1 warning: RHF `watch()` memoization, known issue) ✓
- `npx jest` → 95/95 tests pass (18 suites) ✓

## Outcome

- ✅ Impact: Phase 12 complete — full Company Settings UI ready (profile, regional, branding, preferences, audit log)
- 🧪 Tests: 95/95 pass (7 new CompanySettingsTabs tests + 88 pre-existing)
- 📁 Files: 15 files created, 2 modified (CompanyAddressForm.tsx, CompanyProfileForm.tsx)
- 🔁 Next prompts: Phase 13 (Integration Testing — T097–T103)
- 🧠 Reflection: `useCompany()` returns `CompanyDetail` directly as TanStack Query `.data`, not wrapped in `StandardResponse` — always destructure `{ data: company }` directly. `exactOptionalPropertyTypes: true` requires cast wrappers when Zod-inferred types (which include `| undefined`) are passed to interfaces with optional-but-not-undefined properties.

## Evaluation notes (flywheel)

- Failure modes observed: `.data.data` access on TanStack Query result (returns T directly, not wrapped); `exactOptionalPropertyTypes` clash between Zod inference and TypeScript interface optional semantics; `messages[0]` undefined on empty array with strict undefined checks
- Graders run and results (PASS/FAIL): tsc PASS, eslint PASS (1 warning), jest 95/95 PASS
- Prompt variant (if applicable): null
- Next experiment: null
