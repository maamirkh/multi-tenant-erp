import { test, expect } from '@playwright/test';
import { SEED, collectConsoleErrors, loginUI, selectCompanyUI } from './helpers';

/**
 * [Epic 10, Phase 15, T253] Default -> cure: a DEFAULTED contract
 * (cure_enabled policy on) is cured back to ACTIVE through the real
 * browser Cure action. Real browser + real backend.
 */
test('DEFAULTED contract is cured back to ACTIVE', async ({ page }) => {
  const errors = collectConsoleErrors(page);
  await loginUI(page, SEED.admin.email, SEED.admin.password);
  await selectCompanyUI(page, SEED.company_main.id);

  await page.goto(`/contracts/${SEED.contracts.defaulted_cure}`);
  await expect(page.getByText('DEFAULTED')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole('button', { name: 'Cure' })).toBeVisible({ timeout: 15_000 });

  await page.getByRole('button', { name: 'Cure' }).click();
  await expect(page.getByText('ACTIVE')).toBeVisible({ timeout: 20_000 });

  expect(errors, errors.join('\n')).toEqual([]);
});
