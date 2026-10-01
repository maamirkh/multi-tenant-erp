import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { collectConsoleErrors } from './helpers';

/**
 * Epic 11 T283 — Reports & Analytics end-to-end smoke test, one happy path
 * through the real browser against a real backend/Postgres:
 * Overview → domain page → drill-down → export → save view → reload it.
 *
 * Fixture data comes from a throwaway-database seed run (see the phase's
 * PHR): one tenant with Reports enabled, every `reports.*` permission, and
 * two Sales invoices dated today. `REPORTS_E2E_SEED_PATH` points at its JSON.
 */
const SEED = JSON.parse(readFileSync(process.env.REPORTS_E2E_SEED_PATH!, 'utf-8')) as {
  email: string;
  password: string;
  company_id: string;
  today: string;
};

const VIEW_NAME = `Smoke view ${Date.now()}`;

test('Reports smoke: overview → domain page → drill-down → export → saved view', async ({
  page,
}) => {
  const consoleErrors = collectConsoleErrors(page);

  // Log in and pick the seeded company.
  await page.goto('/login');
  await page.locator('#login-email').fill(SEED.email);
  await page.locator('#login-password').fill(SEED.password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('**/dashboard', { timeout: 60_000 });
  await page.evaluate((id) => {
    window.localStorage.setItem('erp_active_company_id', id);
    window.dispatchEvent(new Event('erp-active-company-changed'));
  }, SEED.company_id);

  // 1. Overview — the Executive Dashboard with real figures.
  await page.goto('/analytics');
  const netSales = page.getByTestId('dashboard-widget-net_sales');
  await expect(netSales).toHaveAttribute('data-state', 'present');
  await expect(netSales).toContainText('1,500.50');

  // 2. Domain page — the Sales hub lists its reports from discovery.
  await page.getByTestId('reports-nav').getByRole('link', { name: 'Sales' }).click();
  await page.waitForURL('**/analytics/sales');
  const salesNav = page.getByRole('navigation', { name: 'Sales reports' });
  await expect(salesNav.getByRole('button', { name: 'Sales Summary' })).toBeVisible();

  // 3. Drill-down — from the Gross sales figure to its contributing report.
  await page.getByTestId('reports-nav').getByRole('link', { name: 'Overview' }).click();
  await page.waitForURL(/\/analytics$/);
  await page.getByTestId('dashboard-drilldown-gross_sales').click();
  await page.waitForURL('**/analytics/sales.summary');
  await expect(page.getByRole('heading', { level: 1, name: 'Sales Summary' })).toBeVisible();
  const table = page.getByRole('table');
  await expect(table.getByRole('row').filter({ hasText: '1,500.50' })).toHaveCount(1);

  // Narrow the period so the saved view has a filter worth restoring.
  await page.getByLabel('From', { exact: true }).fill(SEED.today);
  await page.getByLabel('To', { exact: true }).fill(SEED.today);
  await page.getByRole('button', { name: 'Apply' }).click();
  await expect(table.getByRole('row').filter({ hasText: '1,500.50' })).toHaveCount(1);

  // 4. Export — a real CSV of exactly this filter scope.
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('group', { name: 'Export report' }).getByRole('button', { name: /CSV/ }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.csv$/);
  const csv = readFileSync((await download.path())!, 'utf-8');
  expect(csv).toContain('1500.5');
  expect(csv.trim().split(/\r?\n/).length).toBeGreaterThanOrEqual(2);

  // 5. Save view.
  await page.getByLabel('View name', { exact: true }).fill(VIEW_NAME);
  await page.getByRole('button', { name: 'Save as new' }).click();
  const viewSelect = page.getByRole('combobox', { name: 'Saved view', exact: true });
  await expect(viewSelect).toContainText(VIEW_NAME);

  // 6. Reload it — a fresh page load restores the saved filters.
  await page.reload();
  await expect(page.getByLabel('From', { exact: true })).toHaveValue('');
  await expect(viewSelect).toContainText(VIEW_NAME);
  await viewSelect.selectOption({ label: VIEW_NAME });
  await expect(page.getByLabel('From', { exact: true })).toHaveValue(SEED.today);
  await expect(page.getByLabel('To', { exact: true })).toHaveValue(SEED.today);
  await expect(table.getByRole('row').filter({ hasText: '1,500.50' })).toHaveCount(1);

  expect(consoleErrors).toEqual([]);
});
