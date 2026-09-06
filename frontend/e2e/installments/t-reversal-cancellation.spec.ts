import { test, expect } from '@playwright/test';
import { SEED, collectConsoleErrors, loginUI, selectCompanyUI } from './helpers';

/**
 * [Epic 10, Phase 15, T255] Reversal + cancellation, real browser + real
 * backend:
 * - a recorded collection can be reversed, and the reversal shows in
 *   the Payments section;
 * - a PENDING_APPROVAL contract can be cancelled (reason required).
 */
test('collection reversal succeeds and shows in Payments', async ({ page }) => {
  const errors = collectConsoleErrors(page);
  await loginUI(page, SEED.admin.email, SEED.admin.password);
  await selectCompanyUI(page, SEED.company_main.id);

  await page.goto(`/contracts/${SEED.contracts.active_reversal}`);
  await expect(page.getByRole('button', { name: 'Reverse' })).toBeVisible({ timeout: 15_000 });

  await page.getByRole('button', { name: 'Reverse' }).click();
  await page.getByPlaceholder('Reason (required)').fill('E2E reversal check');
  await page.getByRole('button', { name: 'Confirm Reverse' }).click();
  await expect(page.getByText(/Reversal —/)).toBeVisible({ timeout: 15_000 });

  expect(errors, errors.join('\n')).toEqual([]);
});

test('cancellation of a PENDING_APPROVAL contract succeeds', async ({ page }) => {
  const errors = collectConsoleErrors(page);
  await loginUI(page, SEED.admin.email, SEED.admin.password);
  await selectCompanyUI(page, SEED.company_main.id);

  await page.goto(`/contracts/${SEED.contracts.pending_cancel}`);
  await expect(page.getByRole('button', { name: 'Cancel' })).toBeVisible({ timeout: 15_000 });

  await page.getByRole('button', { name: 'Cancel' }).click();
  await page.getByPlaceholder('Reason (required)').fill('E2E cancellation check');
  await page.getByRole('button', { name: 'Confirm Cancel' }).click();
  await expect(page.getByRole('heading', { name: /CANCELLED/ })).toBeVisible({
    timeout: 20_000,
  });

  expect(errors, errors.join('\n')).toEqual([]);
});
