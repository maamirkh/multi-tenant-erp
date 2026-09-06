import { test, expect } from '@playwright/test';
import { PLATFORM_OWNER, SEED, collectConsoleErrors } from './helpers';

/**
 * [Epic 10, Phase 15, T249] Scenario L — Platform Admin / support-access
 * boundary: Platform Admin can govern entitlement, and even under an
 * active support-access grant for a tenant that HAS a real Installments
 * contract, no route anywhere in the Platform Admin app exposes tenant
 * Installments business records (BR-INST-002). Mirrors
 * t221-multi-tenant-support-access.spec.ts's exact proven
 * initiate-grant -> verify-404 pattern.
 */
test('Scenario L: active support-access grant cannot reach tenant Installments records', async ({
  browser,
}) => {
  const adminContext = await browser.newContext();
  const adminPage = await adminContext.newPage();
  const adminErrors = collectConsoleErrors(adminPage);

  await adminPage.goto('/platform-admin/login');
  await adminPage.locator('#platform_login_email').fill(PLATFORM_OWNER.email);
  await adminPage.locator('#platform_login_password').fill(PLATFORM_OWNER.password);
  await adminPage.getByRole('button', { name: 'Sign in' }).click();
  await expect(adminPage).toHaveURL(/\/platform-admin\/dashboard/, { timeout: 30_000 });

  await adminPage.goto(`/platform-admin/tenants/${SEED.company_l.id}`); // sets selectedTenant
  await expect(adminPage.getByRole('heading', { name: SEED.company_l.name })).toBeVisible({
    timeout: 15_000,
  });
  await adminPage.getByRole('link', { name: 'Support Access' }).click();
  await expect(adminPage).toHaveURL(/\/platform-admin\/support-access$/);
  await adminPage.locator('#support_access_reason').fill('T249 E2E Installments boundary check');
  await adminPage.getByRole('button', { name: 'Initiate Grant' }).click();
  await expect(adminPage.getByText('PRIVILEGED SUPPORT ACCESS ACTIVE')).toBeVisible({
    timeout: 30_000,
  });

  // No route anywhere in Platform Admin exposes tenant Installments
  // business records — structural boundary, real Next.js routing, not
  // a static assertion. Checked from a second page in the same admin
  // context so the active-grant banner (session-local React state) on
  // adminPage is not lost by navigating it away.
  const checkPage = await adminContext.newPage();
  const checkErrors = collectConsoleErrors(checkPage);
  await checkPage.goto(`/platform-admin/tenants/${SEED.company_l.id}/installments`);
  await expect(checkPage.getByText(/not found|404/i)).toBeVisible({ timeout: 30_000 });
  await checkPage.goto(
    `/platform-admin/tenants/${SEED.company_l.id}/installments/contracts/${SEED.active_l}`
  );
  await expect(checkPage.getByText(/not found|404/i)).toBeVisible({ timeout: 30_000 });
  await checkPage.close();

  // Revoke.
  await expect(adminPage.getByText('PRIVILEGED SUPPORT ACCESS ACTIVE')).toBeVisible();
  await adminPage.getByRole('button', { name: 'Terminate' }).click();
  const terminateDialog = adminPage.getByRole('dialog');
  await terminateDialog.getByRole('button', { name: 'Terminate' }).click();
  await expect(adminPage.getByText('PRIVILEGED SUPPORT ACCESS ACTIVE')).not.toBeVisible({
    timeout: 30_000,
  });

  expect(adminErrors, adminErrors.join('\n')).toEqual([]);
  expect(checkErrors, checkErrors.join('\n')).toEqual([]);
  await adminContext.close();
});
