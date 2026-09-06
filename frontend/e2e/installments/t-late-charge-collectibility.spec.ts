import { test, expect } from '@playwright/test';
import { SEED, collectConsoleErrors, loginUI, selectCompanyUI } from './helpers';

/**
 * [Epic 10, Phase 15, T252] Late charge + subsequent payment
 * collectibility: a contract with an already-applied late charge
 * (seeded) accepts an ordinary collection large enough to satisfy both
 * the overdue schedule line AND the late charge, through the normal
 * collection UI with no special-case path. Real browser + real backend.
 */
test('late charge is collectible via an ordinary subsequent payment', async ({ page }) => {
  const errors = collectConsoleErrors(page);
  await loginUI(page, SEED.admin.email, SEED.admin.password);
  await selectCompanyUI(page, SEED.company_main.id);

  await page.goto(`/contracts/${SEED.contracts.active_latecharge}`);
  await expect(page.getByRole('heading', { name: 'Delinquency' })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/overdue/i).first()).toBeVisible({ timeout: 15_000 });

  await page.getByRole('button', { name: 'Record Collection' }).click();
  await page.waitForURL(/\/collect$/);
  // 2 x 100.00 installments; first overdue. Pay 125.00 (100 schedule +
  // 25 late charge) — the ordinary collection path, no special UI.
  await page.locator('form input').first().fill('125.00');
  await page.locator('select').selectOption('BANK_TRANSFER');
  await page.getByPlaceholder('Bank account UUID').fill(SEED.bank_account_main);
  await page.getByRole('button', { name: 'Record Collection' }).click();
  await page.waitForURL(new RegExp(`/contracts/${SEED.contracts.active_latecharge}$`), {
    timeout: 20_000,
  });

  await expect(page.getByRole('heading', { name: /ACTIVE/ })).toBeVisible({ timeout: 15_000 });
  // The 125.00 payment is allocated oldest-due-first as two separate
  // rows: 100.000000 (the overdue schedule line) and 25.000000 (the
  // late charge) — money renders with 6 decimals (NUMERIC(20,6)).
  await expect(page.getByText('100.000000').first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText('25.000000').first()).toBeVisible({ timeout: 15_000 });

  expect(errors, errors.join('\n')).toEqual([]);
});
