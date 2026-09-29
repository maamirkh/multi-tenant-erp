# Epic 11 — Reports & Analytics: Release Sign-off (T292)

**Date:** 2026-09-29 · **Branch:** `011-reports-analytics` · **Draft PR:** #9 (CI only, not merged)

Every gate below is recorded in full, with its evidence, on its own line in
`tasks.md`. This page collects them in one place.

## Gate evidence

| Gate | Task | Scope | Evidence summary |
|---|---|---|---|
| Gate 0 — Foundation | T034 | T001–T033 | `mypy`/`ruff` clean; foundation tests green; `ADAPTER_REGISTRY` importable |
| Gate 1 — Saved Views (persistence) | T046 | T035–T045A | Real-Postgres CRUD round-trip; soft delete; ownership security test T045A green |
| Sub-Gate 2A — Accounting | T064 | T047–T063 | T057–T060 green; T048 backward-compat regression green |
| Sub-Gate 2B — Sales | T074 | T065–T073 | T070–T072 green |
| Sub-Gate 2C — Purchase | T086 | T075–T085 | T076, T081, T082, T084 green |
| Sub-Gate 2D — Inventory | T099 | T087–T098 | T088, T094–T096 green |
| Sub-Gate 2E — CRM | T107 | T100–T106 | T104–T106 green |
| Sub-Gate 2F — Installments | T121 | T108–T120 | T111, T115–T117 green |
| Gate 2 — Domain Adapters | T125 | T122–T124 | Registry: 43 Now `ADAPTER` + 3 Deferred |
| Gate 3 — Execution API | T144 | T126–T143 | 11 tests green; no route bypasses the registry |
| Gate 4 — Executive Dashboard | T159 | T145–T158 | 8 tests + real-Postgres Case B; registry 44 Now |
| Gate 5 — Customer 360 | T177 | T160–T176 | 10 tests (2 real-Postgres); registry final: 45 Now + 3 Deferred |
| Gate 6 — Exports & Audit | T216 | T178–T215 | 110 passed; audit durability (T206) and GL limit+1 (T208) re-confirmed |
| Gate 7 — Frontend Foundation | T241 | T217–T240 | Jest + jest-axe green; build green |
| Gate 8 — Domain Report Pages | T252 | T242–T251 | Pages green; browser check T251 |
| Gate 9 — Composite UI | T260 | T253–T259 | Dashboard + Customer 360 UI green; browser check T259 |
| Gate 10 — Hardening | T276 | T261–T275 | GitHub CI run 36567160552: full backend suite, coverage ≥ 80%, auth ≥ 90% |
| **Final Gate — Release Readiness** | **T293** | **T277–T292** | See below |

## Final verification (Phase 11)

| Check | Task | Result |
|---|---|---|
| `ruff check .` + `ruff format --check .` | T277 | PASS — clean, 1494 files |
| `mypy .` | T278 | PASS — 0 issues in 1494 files |
| Full backend regression + coverage (`--cov-fail-under=80`, auth ≥ 90%) | T279 | PASS — GitHub CI run 36567160552 on commit `5b7c289` (real PostgreSQL 16). Backend code is unchanged since that commit (Phase 11 adds only a `.md` file under `backend/`). |
| bandit (`-ll`) + pip-audit | T280 | PASS — no **new** findings. bandit: 1 HIGH (B324 MD5 in `modules/inventory/router.py`) already on `main`. pip-audit: anyio 4.14.1, cryptography 49.0.0, pip 26.1.2 — `poetry.lock` is unchanged since `main`. |
| Full migration chain on an empty database | T281 | PASS — 78 revisions `001` → `078` (head) in 16 s |
| Frontend `lint` / `test:ci` / `build` | T282 | PASS — lint 0 errors (55 warnings, same as before Epic 11, none in Epic 11 files); Jest 48 suites / 285 tests; production build green |
| Playwright smoke `e2e/reports-smoke.spec.ts` | T283 | PASS — 2 consecutive runs (Overview → Sales hub → drill-down → CSV export → saved view → reload) |
| `docker build --target production` | T284 | PASS — backend and frontend images; frontend needed a pre-existing Dockerfile fix (below) |
| Consolidated security regression | T285 | PASS — 106 passed, 0 failed |
| Module docs | T286 | `backend/modules/reports/docs/README.md` |
| `CLAUDE.md` update | T287 | Done (manual; the script output was wrong, see below) |
| ADRs | T288 | User consented: ADR-0005, ADR-0006 created |
| Git hygiene | T290 | No secrets, no added TODO/FIXME, no skipped or `.only` tests |

## Defects found and fixed in Phase 11

1. **Dashboard drill-down links were never rendered** (FR-RPT-180, Phase 9 gap exposed by T283). The API returned `drill_down` per widget but the UI ignored it. Fixed in `DashboardWidgets.tsx` + `drillDownHref()` in `domains.ts`, which maps the backend's `/reports/<key>` to the UI's `/analytics/<key>`. The E2E run then found the new link overlapped the next card; fixed by making each widget a flex column. Jest test added.
2. **Frontend production Docker build failed before Epic 11** (reproduced at `0fc6e5d`): `NODE_ENV=production` made `npm ci` skip devDependencies, so `@tailwindcss/postcss` was missing. Fixed with `npm ci --ignore-scripts --include=dev` in the builder stage only (user-approved). The final image still contains only `.next/standalone`.
3. **`update-agent-context.sh` produced a wrong `CLAUDE.md`** (duplicated the 011 line, removed the 009a line, and kept planning-time text). Reverted, and the 011 entries were updated by hand.

## Files outside the Expected File Map

All are recorded at their tasks in `tasks.md`:

- `.github/workflows/backend.yml` — migrate the CI database; Argon2 time cost for CI (Phase 10, user-approved)
- `frontend/Dockerfile` — item 2 above (Phase 11, user-approved)
- `backend/modules/installments/models/schedule.py`, `migrations/versions/078_…` — T268 Customer 360 index
- `backend/modules/installments/repositories/{contract,schedule,audit,allocation_reference}.py`, `backend/modules/accounting/repositories/{banking,cash}.py`, Sales/Purchase/Inventory report services — T270 deterministic `ORDER BY` tiebreakers
- `backend/modules/sales/repositories/customer.py` — T269 batched customer-name seam
- `frontend/src/components/layout/ReportsNavSection.tsx` — T236 sidebar section (new file next to `Sidebar.tsx`)
- `CLAUDE.md` — T287

The branch also carries 5 pre-Epic-11 commits that are not yet on `main` (MyPy stabilization and CI, up to `0fc6e5d`).

## Open items (non-blocking, product decisions)

1. **FR-RPT-152 multi-currency:** Sales, Purchase aggregates, Inventory valuation and CRM sum across currencies (`backend/modules/reports/docs/multi_currency_findings.md`).
2. **CI Security Scans job** is broken since before Epic 11: bandit and pip-audit are not in `poetry.lock`, and the pip-audit flags are invalid. Run locally for T280.
3. **Pre-existing dependency advisories:** anyio → 4.14.2, cryptography → 50.0.0, pip → 26.2.
4. **Record-level drill-down in report tables** (row → invoice/contract page) is not rendered in the UI; the metadata is in the API.
5. **Installments `due_overdue`** takes ~4.5 s per page at 10K contracts.
6. **Installments pagination timing test** can be flaky on CI runners (wall-clock based).
