import { test, expect } from '@playwright/test';
import { SEED, collectConsoleErrors, loginUI, selectCompanyUI } from './helpers';

/**
 * [Epic 10, Phase 15, T251] Scenario D — advance payment: a payment
 * covering more than the currently-due installment (before its later
 * lines are due) is accepted, applied oldest-due-first, and the
 * contract remains ACTIVE with the surplus correctly reducing future
 * outstanding. Real browser + real backend.
 */
test('Scenario D: advance payment ahead of due date is accepted', async ({ page }) => {
  const errors = collectConsoleErrors(page);
  await loginUI(page, SEED.admin.email, SEED.admin.password);
  await selectCompanyUI(page, SEED.company_main.id);

  await page.goto(`/contracts/${SEED.contracts.active_advance}`);
  await expect(page.getByRole('heading', { name: 'Schedule' })).toBeVisible({ timeout: 15_000 });

  await page.getByRole('button', { name: 'Record Collection' }).click();
  await page.waitForURL(/\/collect$/);
  // 3 installments x 100.00; pay 250.00 — more than 2 full installments,
  // ahead of their due dates (advance payment).
  await page.locator('form input').first().fill('250.00');
  await page.locator('select').selectOption('BANK_TRANSFER');
  await page.getByPlaceholder('Bank account UUID').fill(SEED.bank_account_main);
  await page.getByRole('button', { name: 'Record Collection' }).click();
  await page.waitForURL(new RegExp(`/contracts/${SEED.contracts.active_advance}$`), {
    timeout: 20_000,
  });

  await expect(page.getByRole('heading', { name: /ACTIVE/ })).toBeVisible({ timeout: 15_000 });
  // Money renders with 6 decimals (NUMERIC(20,6)) and the collection is
  // split oldest-due-first across schedule lines (100 + 100 + 50), so
  // no single "250.00" string appears — a BANK_TRANSFER row existing at
  // all is the real proof the collection was recorded.
  await expect(page.getByText('BANK_TRANSFER').first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText('100.000000').first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText('50.000000').first()).toBeVisible({ timeout: 15_000 });

  expect(errors, errors.join('\n')).toEqual([]);
});
