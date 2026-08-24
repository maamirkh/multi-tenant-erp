import { test, expect } from '@playwright/test';
import {
  collectConsoleErrors,
  ensureCompanyActive,
  ensureNoActiveOverride,
  PLATFORM_OWNER,
} from './helpers';

/**
 * T219 — Platform Admin happy path, real browser.
 * Acceptance (tasks.md): bootstrap owner -> login -> dashboard -> tenant
 * list -> tenant detail -> plan/subscription -> entitlement action ->
 * audit shows the action. Zero unexpected browser console errors.
 *
 * "bootstrap owner" is independently proven on real Postgres by T215
 * (this spec logs in as an already-provisioned owner, since re-running
 * the one-time bootstrap CLI is not a browser action). Every other step
 * is driven by real clicks/form-fills against the live stack.
 */

const TENANT_A_NAME = 'T221 E2E Company A';
const TENANT_A_SLUG = 't221-e2e-company-a';
const TENANT_A_ID = '8a0b2ef8-c64d-412d-ab92-222aa816fc58';
const PLAN_LABEL = 'T217 Allow Plan (t217-allow)';

test('platform admin happy path: login -> dashboard -> tenant -> plan -> entitlement -> audit', async ({
  page,
}) => {
  const consoleErrors = collectConsoleErrors(page);

  // T220/T221 (run in the same suite) suspend Company A as part of
  // their own scenario; if this test runs after one of them without
  // reaching its own reactivate/cleanup step, Company A could still be
  // suspended here. Ensure a clean starting state regardless of run
  // order — plain HTTP "arrange" setup, not a substitute for anything
  // this test itself asserts.
  await ensureCompanyActive(TENANT_A_ID);
  await ensureNoActiveOverride(TENANT_A_ID, 'crm');

  // --- Login ---
  await page.goto('/platform-admin/login');
  await page.locator('#platform_login_email').fill(PLATFORM_OWNER.email);
  await page.locator('#platform_login_password').fill(PLATFORM_OWNER.password);
  await page.getByRole('button', { name: 'Sign in' }).click();

  // --- Dashboard ---
  await expect(page).toHaveURL(/\/platform-admin\/dashboard/);
  await expect(page.getByText('DevSphere Platform Administration')).toBeVisible();

  // --- Tenant list ---
  await page.getByRole('link', { name: 'Tenants' }).click();
  await expect(page).toHaveURL(/\/platform-admin\/tenants$/);
  await page.getByPlaceholder('Search by name or slug…').fill(TENANT_A_SLUG);
  const tenantLink = page.getByRole('link', { name: TENANT_A_NAME });
  await expect(tenantLink).toBeVisible();
  const tenantHref = await tenantLink.getAttribute('href');
  const tenantId = tenantHref?.split('/').pop();
  if (!tenantId) throw new Error('Could not resolve Company A id from tenant list link href');

  // --- Tenant detail ---
  await tenantLink.click();
  await expect(page).toHaveURL(new RegExp(`/platform-admin/tenants/${tenantId}$`));
  await expect(page.getByRole('heading', { name: TENANT_A_NAME })).toBeVisible();
  await expect(page.getByText('active', { exact: true }).first()).toBeVisible();

  // --- Plan / subscription assignment ---
  await page.getByRole('link', { name: 'Subscriptions' }).click();
  await expect(page).toHaveURL(/\/platform-admin\/subscriptions$/);
  await page.locator('#subscription_plan').selectOption({ label: PLAN_LABEL });
  const today = new Date().toISOString().slice(0, 10);
  await page.locator('#subscription_effective_date').fill(today);
  await page.locator('#subscription_reason').fill('T219 E2E happy-path assignment');
  await page.getByRole('button', { name: 'Assign' }).click();
  await expect(page.getByText(/Plan .* active since/)).toBeVisible({ timeout: 15_000 });

  // --- Entitlement action (override grant) ---
  await page.getByRole('link', { name: 'Entitlements' }).click();
  await expect(page).toHaveURL(/\/platform-admin\/entitlements$/);
  const crmRow = page.locator('tr', { has: page.getByText('crm', { exact: true }) });
  await expect(crmRow).toBeVisible();
  await crmRow.getByRole('button', { name: 'Grant Override' }).click();
  const overrideDialog = page.getByRole('dialog');
  await overrideDialog.locator('#override_reason').fill('T219 E2E entitlement override action');
  await overrideDialog.getByRole('button', { name: 'Grant', exact: true }).click();
  await expect(crmRow.getByText('Permanent override')).toBeVisible({ timeout: 15_000 });

  // --- Audit shows the action ---
  await page.getByRole('link', { name: 'Audit' }).click();
  await expect(page).toHaveURL(/\/platform-admin\/audit$/);
  await page.getByPlaceholder('Company ID').fill(tenantId);
  await expect(page.getByText('subscription.assign_or_change').first()).toBeVisible({
    timeout: 15_000,
  });
  await page.getByPlaceholder('Action').fill('entitlement_override.grant');
  await expect(page.getByText('entitlement_override.grant').first()).toBeVisible({
    timeout: 15_000,
  });

  expect(consoleErrors, `Unexpected browser console errors:\n${consoleErrors.join('\n')}`).toEqual(
    []
  );
});
