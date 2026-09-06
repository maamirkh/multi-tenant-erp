import { test, expect, type Page } from '@playwright/test';
import { collectConsoleErrors, ensureCompanyActive, PLATFORM_OWNER, TENANT_USER } from './helpers';

/**
 * T221 — Multi-tenant and support-access flows, real browser.
 *
 * Acceptance (tasks.md): user in A and B -> suspend A -> A denied, B
 * fully functional; support grant -> administrative context visible,
 * business records unavailable -> revoke -> access ends. Zero
 * unexpected console errors.
 *
 * Companies A and B were both created for this E2E run, owned by the
 * same tenant user, via the real POST /companies + activate API (see
 * history/prompts/.../0032-*.prompt.md for full setup evidence).
 */
const COMPANY_A_ID = '8a0b2ef8-c64d-412d-ab92-222aa816fc58';
const COMPANY_A_NAME = 'T221 E2E Company A';
const COMPANY_B_ID = '0f118c82-7669-40c4-a63e-47cc6c545d0c';
const COMPANY_B_NAME = 'T221 E2E Company B';

const COMPANY_IDS_BY_NAME: Record<string, string> = {
  [COMPANY_A_NAME]: COMPANY_A_ID,
  [COMPANY_B_NAME]: COMPANY_B_ID,
};

async function tenantOpenCompany(page: Page, companyName: string): Promise<void> {
  await page.getByRole('link', { name: 'My Companies' }).click();
  await expect(page).toHaveURL(/\/companies$/);
  await page.getByRole('link', { name: `View details for ${companyName}` }).click();
  await expect(page).toHaveURL(new RegExp(`/companies/${COMPANY_IDS_BY_NAME[companyName]}$`));
}

test('multi-tenant isolation + support-access boundary, real browser', async ({ browser }) => {
  const adminContext = await browser.newContext();
  const tenantContext = await browser.newContext();
  const adminPage = await adminContext.newPage();
  const tenantPage = await tenantContext.newPage();
  const adminErrors = collectConsoleErrors(adminPage);
  const tenantErrors = collectConsoleErrors(tenantPage);

  await ensureCompanyActive(COMPANY_A_ID);

  // --- Tenant logs in, confirms access to both A and B ---
  await tenantPage.goto('/login');
  await tenantPage.locator('#login-email').fill(TENANT_USER.email);
  await tenantPage.locator('#login-password').fill(TENANT_USER.password);
  await tenantPage.getByRole('button', { name: 'Sign in' }).click();
  await expect(tenantPage).toHaveURL(/\/dashboard/);

  await tenantOpenCompany(tenantPage, COMPANY_A_NAME);
  await expect(tenantPage.getByLabel('Status: Active')).toBeVisible();
  await tenantOpenCompany(tenantPage, COMPANY_B_NAME);
  await expect(tenantPage.getByLabel('Status: Active')).toBeVisible();

  // --- Platform admin logs in and suspends Company A only ---
  await adminPage.goto('/platform-admin/login');
  await adminPage.locator('#platform_login_email').fill(PLATFORM_OWNER.email);
  await adminPage.locator('#platform_login_password').fill(PLATFORM_OWNER.password);
  await adminPage.getByRole('button', { name: 'Sign in' }).click();
  await expect(adminPage).toHaveURL(/\/platform-admin\/dashboard/);

  await adminPage.goto(`/platform-admin/tenants/${COMPANY_A_ID}`);
  await expect(adminPage.getByRole('heading', { name: COMPANY_A_NAME })).toBeVisible();
  await adminPage.getByRole('button', { name: 'Suspend' }).click();
  const suspendDialog = adminPage.getByRole('dialog');
  await suspendDialog.locator('#platform_action_reason').fill('T221 E2E multi-tenant isolation check');
  await suspendDialog.getByRole('button', { name: 'Suspend' }).click();
  await expect(adminPage.getByText('suspended', { exact: true }).first()).toBeVisible({
    timeout: 30_000,
  });

  // --- Tenant: A is denied, B remains fully functional, same session ---
  await tenantOpenCompany(tenantPage, COMPANY_A_NAME);
  await expect(tenantPage.getByText(/suspended/i)).toBeVisible({ timeout: 30_000 });
  await tenantOpenCompany(tenantPage, COMPANY_B_NAME);
  await expect(tenantPage.getByLabel('Status: Active')).toBeVisible({ timeout: 30_000 });

  // --- Support access: administrative context visible ---
  await adminPage.goto(`/platform-admin/tenants/${COMPANY_A_ID}`); // sets selectedTenant = A
  await expect(adminPage.getByRole('heading', { name: COMPANY_A_NAME })).toBeVisible();
  await adminPage.getByRole('link', { name: 'Support Access' }).click();
  await expect(adminPage).toHaveURL(/\/platform-admin\/support-access$/);
  await expect(adminPage.getByText(`For ${COMPANY_A_NAME}`)).toBeVisible();
  await adminPage.locator('#support_access_reason').fill('T221 E2E support boundary check');
  await adminPage.getByRole('button', { name: 'Initiate Grant' }).click();
  await expect(adminPage.getByText('PRIVILEGED SUPPORT ACCESS ACTIVE')).toBeVisible({
    timeout: 30_000,
  });

  // --- Business records unavailable: no such route exists anywhere in
  // the Platform Admin app, even while a grant is active. Real Next.js
  // routing, not a static assertion. Checked from a second page in the
  // same admin browser context (sharing cookies/localStorage, so still
  // the same authenticated session) rather than navigating `adminPage`
  // itself away — the support-access grant's "active" banner is
  // deliberately session-local React state, not server-persisted (see
  // the page's own docstring), so a `goto()` on `adminPage` would lose
  // it before the Terminate step below. ---
  const adminCheckPage = await adminContext.newPage();
  const adminCheckErrors = collectConsoleErrors(adminCheckPage);
  await adminCheckPage.goto(`/platform-admin/tenants/${COMPANY_A_ID}/inventory`);
  await expect(adminCheckPage.getByText(/not found|404/i)).toBeVisible({ timeout: 30_000 });
  await adminCheckPage.goto(`/platform-admin/tenants/${COMPANY_A_ID}/sales`);
  await expect(adminCheckPage.getByText(/not found|404/i)).toBeVisible({ timeout: 30_000 });
  await adminCheckPage.close();

  // --- Revoke: access ends --- (`adminPage` never navigated away, so
  // the grant banner from the Initiate Grant step above is still live)
  await expect(adminPage.getByText('PRIVILEGED SUPPORT ACCESS ACTIVE')).toBeVisible();
  await adminPage.getByRole('button', { name: 'Terminate' }).click();
  const terminateDialog = adminPage.getByRole('dialog');
  await terminateDialog.getByRole('button', { name: 'Terminate' }).click();
  await expect(adminPage.getByText('PRIVILEGED SUPPORT ACCESS ACTIVE')).not.toBeVisible({
    timeout: 30_000,
  });

  expect(
    [...adminErrors, ...tenantErrors, ...adminCheckErrors],
    `Unexpected browser console errors:\n${[...adminErrors, ...tenantErrors, ...adminCheckErrors].join('\n')}`
  ).toEqual([]);

  await adminContext.close();
  await tenantContext.close();
});
