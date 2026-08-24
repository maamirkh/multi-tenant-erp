import { test, expect, type Page } from '@playwright/test';
import { collectConsoleErrors, ensureCompanyActive, PLATFORM_OWNER, TENANT_USER } from './helpers';

/**
 * T220 — Suspension flow, real browser, two real browser contexts
 * (tenant + platform admin) driving the actual Docker Compose stack.
 *
 * Acceptance (tasks.md): tenant user logged in -> platform admin
 * suspends -> tenant request denied -> reactivate -> old access token
 * denied -> old refresh used -> new access token still denied ->
 * genuine login -> access restored. Zero unexpected console errors.
 *
 * Company A was created for this E2E run via the real POST /companies +
 * POST /companies/{id}/activate API as t221-e2e-tenant@example.com
 * (see history/prompts/.../0032-*.prompt.md for full setup evidence).
 *
 * The "old access token" vs "old refresh, new access token" distinction
 * relies on tokenStorage.ts: the access token lives in an in-memory JS
 * variable only, so an in-page client-side navigation (a real `<Link>`
 * click) reuses it unchanged, while a full `page.reload()` clears it and
 * forces AuthContext's real hydration path to call the actual
 * POST /auth/refresh with the refresh token still in localStorage.
 */
const COMPANY_A_ID = '8a0b2ef8-c64d-412d-ab92-222aa816fc58';
const COMPANY_A_NAME = 'T221 E2E Company A';

async function tenantLogin(page: Page): Promise<void> {
  await page.goto('/login');
  await page.locator('#login-email').fill(TENANT_USER.email);
  await page.locator('#login-password').fill(TENANT_USER.password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

async function tenantOpenCompanyA(page: Page): Promise<void> {
  await page.getByRole('link', { name: 'My Companies' }).click();
  await expect(page).toHaveURL(/\/companies$/);
  await page.getByRole('link', { name: `View details for ${COMPANY_A_NAME}` }).click();
  await expect(page).toHaveURL(new RegExp(`/companies/${COMPANY_A_ID}$`));
}

test('suspension flow: deny -> reactivate -> old-refresh-still-denied -> genuine login restores', async ({
  browser,
}) => {
  const adminContext = await browser.newContext();
  const tenantContext = await browser.newContext();
  const adminPage = await adminContext.newPage();
  const tenantPage = await tenantContext.newPage();
  const adminErrors = collectConsoleErrors(adminPage);
  const tenantErrors = collectConsoleErrors(tenantPage);

  await ensureCompanyActive(COMPANY_A_ID);

  // --- Tenant logs in and confirms access to Company A (client-side nav) ---
  await tenantLogin(tenantPage);
  await tenantOpenCompanyA(tenantPage);
  await expect(tenantPage.getByLabel('Status: Active')).toBeVisible();

  // --- Platform admin suspends Company A ---
  await adminPage.goto('/platform-admin/login');
  await adminPage.locator('#platform_login_email').fill(PLATFORM_OWNER.email);
  await adminPage.locator('#platform_login_password').fill(PLATFORM_OWNER.password);
  await adminPage.getByRole('button', { name: 'Sign in' }).click();
  await expect(adminPage).toHaveURL(/\/platform-admin\/dashboard/);

  await adminPage.goto(`/platform-admin/tenants/${COMPANY_A_ID}`);
  await expect(adminPage.getByRole('heading', { name: COMPANY_A_NAME })).toBeVisible();
  await adminPage.getByRole('button', { name: 'Suspend' }).click();
  const suspendDialog = adminPage.getByRole('dialog');
  await suspendDialog.locator('#platform_action_reason').fill('T220 E2E suspension check');
  await suspendDialog.getByRole('button', { name: 'Suspend' }).click();
  await expect(adminPage.getByText('suspended', { exact: true }).first()).toBeVisible({
    timeout: 30_000,
  });

  // --- "old access token denied": same tab, same in-memory access token,
  // navigated via a real in-page <Link> click (no reload happened) ---
  await tenantOpenCompanyA(tenantPage);
  await expect(tenantPage.getByText(/suspended/i)).toBeVisible({ timeout: 30_000 });

  // --- Platform admin reactivates Company A ---
  await adminPage.reload();
  await adminPage.getByRole('button', { name: 'Reactivate' }).click();
  const reactivateDialog = adminPage.getByRole('dialog');
  await reactivateDialog.locator('#platform_action_reason').fill('T220 E2E reactivation check');
  await reactivateDialog.getByRole('button', { name: 'Reactivate' }).click();
  await expect(adminPage.getByText('active', { exact: true }).first()).toBeVisible({
    timeout: 30_000,
  });

  // --- "old access token denied" (post-reactivation): still the same
  // in-memory token, still denied by the watermark ---
  await tenantOpenCompanyA(tenantPage);
  await expect(tenantPage.getByText(/suspended/i)).toBeVisible({ timeout: 30_000 });

  // --- "old refresh used -> new access token still denied": a real full
  // page reload clears the in-memory access token, forcing the browser's
  // own hydration logic to call POST /auth/refresh with the refresh
  // token already sitting in localStorage from the original login. The
  // resulting new access token is still bound to the same pre-suspension
  // Session, so it is still denied. ---
  await tenantPage.reload();
  await expect(tenantPage).toHaveURL(new RegExp(`/companies/${COMPANY_A_ID}$`));
  await expect(tenantPage.getByText(/suspended/i)).toBeVisible({ timeout: 30_000 });

  // --- Genuine login (new Session) restores access ---
  // Clear the stale refresh token first: the tenant app has no logout
  // button anywhere in its UI (a separate, real gap — AuthContext
  // exposes logout(), nothing renders it), and navigating to /login
  // with the old pre-suspension refresh token still in localStorage
  // otherwise races AuthContext's own silent hydration-refresh (which
  // still succeeds — the old Session is stale relative to Company A's
  // watermark, not revoked) against this explicit form-submit login,
  // non-deterministically clobbering the fresh Session's tokens with
  // the stale ones depending on which resolves last.
  await tenantPage.evaluate(() => localStorage.removeItem('erp_refresh_token'));
  await tenantPage.goto('/login');
  await tenantPage.locator('#login-email').fill(TENANT_USER.email);
  await tenantPage.locator('#login-password').fill(TENANT_USER.password);
  await tenantPage.getByRole('button', { name: 'Sign in' }).click();
  await expect(tenantPage).toHaveURL(/\/dashboard/);
  await tenantOpenCompanyA(tenantPage);
  await expect(tenantPage.getByLabel('Status: Active')).toBeVisible({ timeout: 30_000 });

  expect(
    [...adminErrors, ...tenantErrors],
    `Unexpected browser console errors:\n${[...adminErrors, ...tenantErrors].join('\n')}`
  ).toEqual([]);

  await adminContext.close();
  await tenantContext.close();
});
