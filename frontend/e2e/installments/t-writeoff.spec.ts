import { test, expect } from '@playwright/test';
import { SEED, collectConsoleErrors, loginUI, selectCompanyUI } from './helpers';

/**
 * [Epic 10, Phase 15, T254] Write-off: a DEFAULTED contract is written
 * off through the real browser Write Off action (reason required).
 * Real browser + real backend.
 */
test('DEFAULTED contract is written off', async ({ page }) => {
  const errors = collectConsoleErrors(page);
  await loginUI(page, SEED.admin.email, SEED.admin.password);
  await selectCompanyUI(page, SEED.company_main.id);

  await page.goto(`/contracts/${SEED.contracts.defaulted_writeoff}`);
  await expect(page.getByText('DEFAULTED')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole('button', { name: 'Write Off' })).toBeVisible({ timeout: 15_000 });

  await page.getByRole('button', { name: 'Write Off' }).click();
  await page.getByPlaceholder('Reason (required)').fill('E2E write-off — uncollectible');
  await page.getByRole('button', { name: 'Confirm Write Off' }).click();
  await expect(page.getByText('WRITTEN OFF')).toBeVisible({ timeout: 20_000 });

  expect(errors, errors.join('\n')).toEqual([]);
});
