import { test, expect } from '@playwright/test';
import { SEED, collectConsoleErrors, loginUI, selectCompanyUI } from './helpers';

/**
 * [Epic 10, Phase 15, T250] Scenario C — multi-installment collection: a
 * single payment larger than one installment (150.00 against 4 x 50.00
 * lines) satisfies multiple schedule lines oldest-due-first, real
 * browser + real backend.
 */
test('Scenario C: a single collection satisfies multiple installments', async ({ page }) => {
  const errors = collectConsoleErrors(page);
  await loginUI(page, SEED.admin.email, SEED.admin.password);
  await selectCompanyUI(page, SEED.company_main.id);

  await page.goto(`/contracts/${SEED.contracts.active_multi}`);
  await expect(page.getByRole('heading', { name: 'Schedule' })).toBeVisible({ timeout: 15_000 });

  await page.getByRole('button', { name: 'Record Collection' }).click();
  await page.waitForURL(/\/collect$/);
  await page.locator('form input').first().fill('150.00'); // 3 x 50.00 lines
  await page.locator('select').selectOption('BANK_TRANSFER');
  await page.getByPlaceholder('Bank account UUID').fill(SEED.bank_account_main);
  await page.getByRole('button', { name: 'Record Collection' }).click();
  await page.waitForURL(new RegExp(`/contracts/${SEED.contracts.active_multi}$`), {
    timeout: 20_000,
  });

  await expect(page.getByRole('heading', { name: /ACTIVE/ })).toBeVisible({ timeout: 15_000 });
  // 3 of the 4 SCHEDULED lines are now satisfied — the table itself
  // stays SCHEDULED (schedule lines aren't individually marked paid),
  // but the Payments section shows 3 separate 50.000000 allocation
  // rows (oldest-due-first split, money renders with 6 decimals).
  // Scoped to the Payments section specifically — the Schedule table's
  // own 4 lines each also render "50.000000" as their scheduled amount,
  // which would otherwise inflate the match count.
  const paymentsSection = page.locator('section', {
    has: page.getByRole('heading', { name: 'Payments' }),
  });
  const paymentRows = paymentsSection.getByText('50.000000');
  await expect(paymentRows).toHaveCount(3, { timeout: 15_000 });

  expect(errors, errors.join('\n')).toEqual([]);
});
