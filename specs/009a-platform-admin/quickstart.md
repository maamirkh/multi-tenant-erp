# Quickstart: Epic 9A — Platform Administration / Super Admin

Verification walkthrough for once Epic 9A is implemented (Tasks/implementation phase deliverable — this document is written now, during planning, so implementation has a concrete acceptance walkthrough to build toward). Uses the existing Docker Compose stack (`db`, `api`, `web`, `minio`) — no new service.

## Prerequisites

- `docker compose up -d` (existing project convention)
- `alembic upgrade head` run inside the `api` container (applies migrations 057–061 — **schema only**; no credential provisioning happens in any migration, `plan.md` §7/ADR-8)
- `PLATFORM_OWNER_BOOTSTRAP_EMAIL` / `PLATFORM_OWNER_BOOTSTRAP_PASSWORD_HASH` set in the environment before running the bootstrap command below

## 1. Bootstrap Verification (deployment order matters)

```bash
# Step 1 — schema only
docker exec erp-system-api-1 alembic upgrade head

# Step 2 — explicit, separate, idempotent bootstrap
docker exec erp-system-api-1 python -m modules.platform_admin.bootstrap; echo "exit=$?"
```

Expect on a fresh environment: "Platform Owner created", `exit=0`.

**Negative checks that must be run** (these are the whole point of the corrected design):
- Unset the two env vars and re-run the bootstrap command in an environment with no owner → expect an explicit error naming the missing variables and **`exit` non-zero**. It must *never* print success or exit 0.
- Re-run with an owner already present → expect "Platform Owner already provisioned — no action taken", `exit=0`, and **no** second owner row.

## 1b. Step 3 — verify before exposing Platform Admin

Re-running the bootstrap command is itself the verification: it must report an existing owner. Only after this passes should Platform Admin functionality be exposed (`plan.md` §7 deployment order, §36 Phase G).

## 2. Platform Login (proves session boundary, plan.md §6)

```bash
curl -X POST http://localhost:8000/api/v1/platform/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"<bootstrap email>","password":"<bootstrap password>"}'
```
Expect: a `platform_access`/`platform_refresh` token pair. Decode the access token and confirm `typ: "platform_access"` (not `"access"`).

**Negative check**: attempt the same request with a known **tenant** user's credentials who has no `PlatformAdministrator` row → expect a generic invalid-credentials-shaped rejection, never a hint that the email is a valid tenant user (§6).

## 3. Tenant-Session-Cannot-Reach-Platform (proves BR-9A-002/003)

```bash
# Using a normal tenant access token from the existing login flow:
curl http://localhost:8000/api/v1/platform/dashboard \
  -H "Authorization: Bearer <tenant access token>"
```
Expect: 401/403 — never a successful response, regardless of the tenant user's role (even `owner`).

## 4. Tenant Suspension → Company-Scoped Access Invalidation (proves plan.md §9–§10, ADR-6)

**Setup**: create test user X who is an active member of **both** Company A and Company B.

1. Log in as X; note the access token; confirm requests to **both** `/companies/{A}/inventory/...` and `/companies/{B}/inventory/...` succeed.
2. As the Platform Owner: `POST /api/v1/platform/tenants/{A}/suspend` with `{"reason": "verification"}`.
3. **Immediately**, without waiting for token expiry, retry the Company **A** request with the **same, still-unexpired** access token → expect **rejected**. Repeat against a second business module (e.g. `/companies/{A}/sales/...`) to confirm enforcement is not module-specific.
4. With the **same token**, retry the Company **B** request → expect **still succeeds**. This is the cross-tenant-isolation proof: suspending A must not cost X access to B.
5. Attempt to reach Company A while manipulating `localStorage["erp_active_company_id"]` to B's id → expect still rejected for A-scoped URLs (the path parameter governs, not client state).
6. `POST /api/v1/platform/tenants/{A}/reactivate` with a reason.
7. Retry Company A with the **original pre-suspension access token** → expect **still rejected** (the `access_invalidated_at` watermark; FR-9A-018).
8. **The critical check** — redeem X's **old pre-suspension refresh token** to mint a brand-new access token, then retry Company A with it → expect **still rejected**. A refresh reuses the same `Session`, so authentication time never advances past the watermark. If this step succeeds, the implementation has regressed to comparing `iat` and the refresh bypass is open (plan.md §10.2).
9. Have X perform a **genuine new login** → expect Company A access restored.
10. Verify `Company A.status` is now its **pre-suspension** value. Repeat the whole flow starting from an `inactive` company and confirm it returns to `inactive`, not `active` (plan.md §9.3).

**Multi-device variant** (plan.md §10.3.1): with X logged in on two devices before suspension, after reactivation **both** must be denied for A. Re-logging in on Device 1 must restore A for Device 1 **only** — Device 2 stays denied until it too performs a real login. Both keep Company B access throughout.

## 5. Feature-Toggle Hardening (proves plan.md §14, evidence-scoped to 3 modules)

```bash
# As an ordinary active (non-admin) tenant member, attempt to toggle Inventory's feature flag:
curl -X PUT http://localhost:8000/api/v1/companies/{companyId}/inventory/feature-flags/some_flag \
  -H "Authorization: Bearer <ordinary member token>" \
  -d '{"is_enabled": true}'
```
Expect: 403 (new `inventory.settings.manage` permission required) — repeat for Sales and Purchase. Repeat once more as a tenant `admin`/`owner` role holder → expect success (permission was seeded onto existing admin/owner roles per the rollout plan, §34/Risk mitigation).

**Regression check**: repeat the same probe against Accounting and CRM's existing (already-correct) gates — confirm behavior is unchanged from before this Epic.

## 6. Entitlement Ceiling at Point of Use (proves plan.md §13.1 — the Correction 1 guarantee)

**6a — the downgrade bypass must not exist.** This is the single most important entitlement check.

1. Put a test tenant on a Plan that **allows** `crm`, and ensure its `feature.crm.enabled` toggle is **on**. Confirm `GET /api/v1/companies/{id}/crm/leads` succeeds.
2. As Platform Owner, move that tenant to a Plan whose `PlanCapability.allowed = false` for `crm`. **Do not touch the tenant's feature toggle.**
3. Retry `GET /api/v1/companies/{id}/crm/leads` → expect **403 denied on the very next request**, even though `crm_feature_flags` still says enabled. Confirm the toggle row is genuinely still `true` in the database (the tenant's preference must be preserved, not silently rewritten).
4. Move the tenant back to the allowing Plan → expect access **resumes automatically**, at the tenant's original preserved preference, with no toggle mutation at any point.
5. Repeat steps 1–3 for one non-CRM module (e.g. `inventory`) to confirm the rule is applied uniformly, not CRM-specific.

**6b — toggle cannot exceed the ceiling.** With the tenant on the denying Plan, attempt `POST /crm/enable` as a tenant admin — even though `require_admin_or_above()` passes, expect rejection (FR-9A-185, §14 secondary guard).

**6c — override.** Grant a time-boxed `EntitlementOverride` for `crm` on that tenant → retry → expect success until `expires_at`, then denial again afterwards.

**6d — frontend is not the boundary.** With the tenant on the denying Plan, call the CRM endpoint directly with `curl` (bypassing the UI entirely, which would have hidden the menu item) → expect the same 403. Server-side enforcement is authoritative.

## 7. Support Access Cannot Reach Business Records (proves plan.md §21, BR-9A-021)

1. Initiate a support-access grant for a test tenant with real business data (at least one invoice/sales order).
2. Within the active grant, attempt to fetch that tenant's actual invoice/sales-order records via any support-access-scoped endpoint.
3. Expect: no such endpoint exists / 404 or 403 — there is no code path from the support-access router into any business-record repository.
4. Confirm configuration/entitlements/users/lifecycle/audit views **do** work within the grant.
5. Let the grant expire (or terminate it) → confirm further tenant-context requests under that grant are rejected.

## 8. Canonical Tenant Context + Token Separation (proves plan.md §15, §23.1)

1. In one browser tab, log in as a tenant user and navigate a tenant module — note `localStorage["erp_active_company_id"]`.
2. In a second tab, log in to `/platform-admin/login` and select a **different** tenant to inspect in the Platform Dashboard.
3. Return to the first tab, refresh — confirm `erp_active_company_id` is **unchanged**; the tenant tab's active company was never affected by the Platform tab's tenant selection.
4. **Token separation** (Clarification 6): with both tabs authenticated, inspect the network traffic — every `/api/v1/platform/...` request must carry the **platform** bearer token and every tenant request the **tenant** token, with no crossover in either direction.
5. Force a platform-token expiry and trigger a Platform request → confirm only the **platform** refresh endpoint (`/platform/auth/refresh`) is called, and that the tenant session in the other tab is entirely unaffected (no tenant `session-expired`, no tenant logout).

## 9. Audit Fail-Closed (proves plan.md §20, ADR-5 — the single most important correctness property)

This requires a controlled test-only fault injection (e.g., a test that forces the audit-table insert to violate a constraint) rather than a manual `curl` walkthrough — see `tests/integration/services/platform_admin/test_audit_fail_closed.py` (Tasks-phase deliverable): assert that when the audit write fails, the `CompanyStatus` change (or whichever privileged mutation was under test) is **also** rolled back, never partially applied.

## 10. Live PostgreSQL Migration Cycle

```bash
docker exec erp-system-api-1 alembic upgrade head
docker exec erp-system-api-1 alembic downgrade 056
docker exec erp-system-api-1 alembic upgrade head
```
Expect: clean up → down → up cycle, matching this project's established Epic 8/9 verification methodology (`plan.md` §32). Confirm via `\dt platform_*`, `\dt subscriptions`, `\dt capabilities` etc. that every table from §33's migration list (`057`–`061`) exists after the final `upgrade head`, and none exist after the `downgrade 056`. Also confirm `\d companies` shows `pre_suspension_status` and `access_invalidated_at` after upgrade and neither after downgrade.

**Also verify the migrations create no Platform Owner**: after `upgrade head` alone (without running the bootstrap command), `SELECT count(*) FROM platform_administrators;` must be `0` — proving credential provisioning is genuinely decoupled from schema versioning (ADR-8).
