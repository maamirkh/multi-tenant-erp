import { test, expect } from '@playwright/test';
import { SEED, collectConsoleErrors, loginUI, selectCompanyUI } from './helpers';

/**
 * [Epic 10, Phase 15, T245] Scenario E — overdue read: a contract with
 * a schedule line past its due date is correctly surfaced as overdue,
 * real browser + real backend.
 */
test('Scenario E: overdue installment surfaces in Delinquency section', async ({ page }) => {
  const errors = collectConsoleErrors(page);
  await loginUI(page, SEED.admin.email, SEED.admin.password);
  await selectCompanyUI(page, SEED.company_main.id);

  await page.goto(`/contracts/${SEED.contracts.active_overdue}`);
  await expect(page.getByRole('heading', { name: 'Delinquency' })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/overdue/i).first()).toBeVisible({ timeout: 15_000 });

  expect(errors, errors.join('\n')).toEqual([]);
});
