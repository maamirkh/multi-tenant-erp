import { test, expect } from '@playwright/test';
import { SEED, collectConsoleErrors, loginUI, selectCompanyUI } from './helpers';

/**
 * [Epic 10, Phase 15, T244] Scenario B — partial collection: recording
 * less than a full installment leaves the contract ACTIVE with a
 * correctly-reduced outstanding balance, real browser + real backend.
 */
test('Scenario B: partial collection leaves contract ACTIVE', async ({ page }) => {
  const errors = collectConsoleErrors(page);
  await loginUI(page, SEED.admin.email, SEED.admin.password);
  await selectCompanyUI(page, SEED.company_main.id);

  await page.goto(`/contracts/${SEED.contracts.active_partial}`);
  await expect(page.getByRole('heading', { name: 'Schedule' })).toBeVisible({ timeout: 15_000 });

  await page.getByRole('button', { name: 'Record Collection' }).click();
  await page.waitForURL(/\/collect$/);
  await page.locator('form input').first().fill('40.00'); // partial: less than one 100.00 installment
  await page.locator('select').selectOption('BANK_TRANSFER');
  await page.getByPlaceholder('Bank account UUID').fill(SEED.bank_account_main);
  await page.getByRole('button', { name: 'Record Collection' }).click();
  await page.waitForURL(new RegExp(`/contracts/${SEED.contracts.active_partial}$`), {
    timeout: 20_000,
  });

  await expect(page.getByText('ACTIVE')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText('40.00').first()).toBeVisible({ timeout: 15_000 });

  expect(errors, errors.join('\n')).toEqual([]);
});
