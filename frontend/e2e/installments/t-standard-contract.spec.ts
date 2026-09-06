import { test, expect } from '@playwright/test';
import { SEED, collectConsoleErrors, loginUI, selectCompanyUI } from './helpers';

/**
 * [Epic 10, Phase 15, T243] Scenario A — standard installment contract:
 * quote -> submit -> approve (different user, maker-checker) -> activate
 * -> collect to completion. Real browser, real backend, real Postgres.
 */
test('Scenario A: standard contract — quote -> submit -> approve -> activate -> collect to completion', async ({
  page,
}) => {
  const errors = collectConsoleErrors(page);

  // Creator: quote + create draft.
  await loginUI(page, SEED.creator.email, SEED.creator.password);
  await selectCompanyUI(page, SEED.company_main.id);

  await page.goto('/contracts/new');
  await page.getByPlaceholder('Invoice UUID').fill(SEED.contracts.fresh_invoice_a);
  const firstDue = new Date();
  firstDue.setDate(firstDue.getDate() + 7);
  const maturity = new Date();
  maturity.setDate(maturity.getDate() + 90);
  await page.locator('input[type="date"]').nth(0).fill(firstDue.toISOString().slice(0, 10));
  await page.locator('input[type="date"]').nth(1).fill(maturity.toISOString().slice(0, 10));
  await page.getByRole('button', { name: 'Get Quote' }).click();
  await expect(page.getByText('Quote Preview')).toBeVisible({ timeout: 15_000 });

  await page.getByRole('button', { name: 'Create Draft Contract' }).click();
  await page.waitForURL(/\/contracts\/[0-9a-f-]{36}$/, { timeout: 15_000 });
  const contractUrl = page.url();
  const contractId = contractUrl.split('/').pop()!;

  // Creator: submit for approval. company_main's InstallmentConfiguration
  // has a low approval_threshold_amount (seeded specifically so submit()
  // routes through PENDING_APPROVAL — FR-INST-101 — rather than its
  // no-threshold auto-approve fast path, which this scenario's
  // maker-checker step requires).
  await expect(page.getByRole('button', { name: 'Submit' })).toBeVisible({ timeout: 15_000 });
  await page.getByRole('button', { name: 'Submit' }).click();
  await expect(page.getByRole('heading', { name: /PENDING APPROVAL/ })).toBeVisible({
    timeout: 15_000,
  });

  // Approver (DIFFERENT user — maker-checker): approve.
  await loginUI(page, SEED.approver.email, SEED.approver.password);
  await selectCompanyUI(page, SEED.company_main.id);
  await page.goto(`/contracts/${contractId}`);
  await expect(page.getByRole('button', { name: 'Approve' })).toBeVisible({ timeout: 15_000 });
  await page.getByRole('button', { name: 'Approve' }).click();
  // "APPROVED" is both the status badge text and a later Audit History
  // action name — the heading-scoped badge is authoritative.
  await expect(page.getByRole('heading', { name: /APPROVED/ })).toBeVisible({ timeout: 15_000 });

  // Approver also activates (has installments.contract.activate).
  await expect(page.getByRole('button', { name: 'Activate' })).toBeVisible({ timeout: 15_000 });
  await page.getByRole('button', { name: 'Activate' }).click();
  await expect(page.getByRole('heading', { name: /ACTIVE/ })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole('heading', { name: 'Schedule' })).toBeVisible();

  // Collector: a THIRD user. The approver's role is deliberately narrow
  // (approve + activate only, mirroring realistic separation of duties)
  // and does not carry installments.collection.create — collecting is a
  // distinct servicing responsibility.
  await loginUI(page, SEED.admin.email, SEED.admin.password);
  await selectCompanyUI(page, SEED.company_main.id);
  await page.goto(`/contracts/${contractId}`);
  await expect(page.getByRole('heading', { name: /ACTIVE/ })).toBeVisible({ timeout: 15_000 });

  // Collect to completion: 3 installments x 200 = 600 total.
  for (let i = 0; i < 3; i++) {
    await page.getByRole('button', { name: 'Record Collection' }).click();
    await page.waitForURL(/\/collect$/);
    await page.locator('form input').first().fill('200.00');
    await page.locator('select').selectOption('BANK_TRANSFER');
    await page.getByPlaceholder('Bank account UUID').fill(SEED.bank_account_main);
    await page.getByRole('button', { name: 'Record Collection' }).click();
    await page.waitForURL(new RegExp(`/contracts/${contractId}$`), { timeout: 20_000 });
  }

  await expect(page.getByRole('heading', { name: /COMPLETED/ })).toBeVisible({ timeout: 15_000 });

  expect(errors, errors.join('\n')).toEqual([]);
});
