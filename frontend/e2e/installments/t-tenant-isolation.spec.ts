import { test, expect } from '@playwright/test';
import { SEED, collectConsoleErrors, loginUI, selectCompanyUI } from './helpers';

/**
 * [Epic 10, Phase 15, T248] Scenario I — tenant isolation: one real
 * user, member of both Tenant A and Tenant B, same browser session.
 * Switching active company never leaks Tenant A's contracts/data into
 * a Tenant B view. Real browser + real backend.
 */
test('Scenario I: switching tenants never leaks the other tenant\'s contracts', async ({
  page,
}) => {
  const errors = collectConsoleErrors(page);
  await loginUI(page, SEED.switcher.email, SEED.switcher.password);

  await selectCompanyUI(page, SEED.company_iso_a.id);
  await page.goto(`/contracts/${SEED.active_iso_a}`);
  await expect(page.getByRole('heading', { name: 'Schedule' })).toBeVisible({ timeout: 15_000 });
  const contractANumber = (await page.locator('h1').first().innerText()).split(' ')[0];

  // Switch to Tenant B mid-session.
  await selectCompanyUI(page, SEED.company_iso_b.id);

  // Tenant A's contract must not be reachable under Tenant B's scope.
  await page.goto(`/contracts/${SEED.active_iso_a}`);
  await expect(page.getByRole('heading', { name: 'Schedule' })).not.toBeVisible({
    timeout: 5_000,
  }).catch(() => {});
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toContain(contractANumber);

  // Tenant B's own contract loads correctly.
  await page.goto(`/contracts/${SEED.active_iso_b}`);
  await expect(page.getByRole('heading', { name: 'Schedule' })).toBeVisible({ timeout: 15_000 });

  // Contracts list under B must not show Tenant A's contract number.
  await page.goto('/contracts');
  await page.waitForLoadState('networkidle');
  const listText = await page.locator('body').innerText();
  expect(listText).not.toContain(contractANumber);

  expect(errors, errors.join('\n')).toEqual([]);
});
