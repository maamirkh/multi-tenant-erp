import { test, expect } from '@playwright/test';
import { API_BASE_URL, SEED, apiLogin, collectConsoleErrors, loginUI, selectCompanyUI } from './helpers';

/**
 * [Epic 10, Phase 15, T247] Scenario K — disabled-entitlement servicing
 * continuity: with the tenant's Installments entitlement disabled,
 * origination is blocked but an existing contract remains readable and
 * fully serviceable (collection succeeds). Real browser + real backend
 * — mirrors t220-suspension-flow.spec.ts's arrange-via-HTTP,
 * assert-via-browser pattern.
 */
test('Scenario K: disabled entitlement blocks origination, preserves servicing', async ({
  page,
  request,
}) => {
  const adminToken = await apiLogin(request, SEED.admin_k.email, SEED.admin_k.password);
  const disableRes = await request.post(
    `${API_BASE_URL}/api/v1/companies/${SEED.company_k.id}/installments/disable`,
    { headers: { Authorization: `Bearer ${adminToken}` } }
  );
  expect(disableRes.ok(), await disableRes.text()).toBeTruthy();

  const errors = collectConsoleErrors(page);
  await loginUI(page, SEED.admin_k.email, SEED.admin_k.password);
  await selectCompanyUI(page, SEED.company_k.id);

  // Origination blocked: real quote attempt returns 403 FEATURE_DISABLED.
  await page.goto('/contracts/new');
  await page.getByPlaceholder('Invoice UUID').fill('00000000-0000-0000-0000-000000000000');
  await page.locator('input[type="date"]').nth(0).fill('2026-09-10');
  await page.getByRole('button', { name: 'Get Quote' }).click();
  await expect(page.getByText(/Installments is not enabled for this company/)).toBeVisible({
    timeout: 15_000,
  });

  // Existing contract remains readable.
  await page.goto(`/contracts/${SEED.active_k}`);
  await expect(page.getByRole('heading', { name: 'Schedule' })).toBeVisible({ timeout: 15_000 });

  // Servicing (collection) remains reachable and succeeds.
  await page.getByRole('button', { name: 'Record Collection' }).click();
  await page.waitForURL(/\/collect$/);
  await page.locator('form input').first().fill('50.00');
  await page.locator('select').selectOption('BANK_TRANSFER');
  await page.getByPlaceholder('Bank account UUID').fill(SEED.bank_account_k);
  await page.getByRole('button', { name: 'Record Collection' }).click();
  await page.waitForURL(new RegExp(`/contracts/${SEED.active_k}$`), { timeout: 20_000 });
  await expect(page.getByText('50.00').first()).toBeVisible({ timeout: 15_000 });

  // Re-enable for hygiene (not required by the scenario, but leaves no
  // dangling disabled-entitlement state behind for any later run).
  const reEnableRes = await request.post(
    `${API_BASE_URL}/api/v1/companies/${SEED.company_k.id}/installments/enable`,
    { headers: { Authorization: `Bearer ${adminToken}` } }
  );
  expect(reEnableRes.ok()).toBeTruthy();

  expect(errors, errors.join('\n')).toEqual([]);
});
