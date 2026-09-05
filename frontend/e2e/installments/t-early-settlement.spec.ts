import { test, expect } from '@playwright/test';
import { SEED, collectConsoleErrors, loginUI, selectCompanyUI } from './helpers';

/**
 * [Epic 10, Phase 15, T246] Scenario F — early settlement: generate a
 * quote, execute it, contract reaches COMPLETED. Real browser + real
 * backend.
 */
test('Scenario F: early settlement completes the contract', async ({ page }) => {
  const errors = collectConsoleErrors(page);
  await loginUI(page, SEED.admin.email, SEED.admin.password);
  await selectCompanyUI(page, SEED.company_main.id);

  await page.goto(`/contracts/${SEED.contracts.active_settle}/settlement`);
  await page.getByRole('button', { name: 'Generate Settlement Quote' }).click();
  await expect(page.getByText('Settlement amount')).toBeVisible({ timeout: 15_000 });

  await page.locator('select').selectOption('BANK_TRANSFER');
  await page.getByPlaceholder('Bank account UUID').fill(SEED.bank_account_main);
  await page.getByRole('button', { name: 'Execute Settlement' }).click();
  await page.waitForURL(new RegExp(`/contracts/${SEED.contracts.active_settle}$`), {
    timeout: 20_000,
  });

  // Two elements render "COMPLETED" (the status badge in the h1, and a
  // later Audit History entry) — the heading-scoped badge is the
  // authoritative contract status.
  await expect(page.getByRole('heading', { name: /COMPLETED/ })).toBeVisible({
    timeout: 15_000,
  });

  expect(errors, errors.join('\n')).toEqual([]);
});
