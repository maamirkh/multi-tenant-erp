import { type Page, type APIRequestContext, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { collectConsoleErrors } from '../helpers';

export { collectConsoleErrors };

/**
 * Phase 15 (T243-T260) E2E fixture data — produced by the throwaway
 * backend seed script for this run (see the phase's PHR for full
 * provenance). Real tenants, real users, real Sales invoices/Accounting
 * AR transactions, real Installment contracts at every lifecycle stage
 * the 12 acceptance scenarios need.
 */
export const SEED = JSON.parse(
  readFileSync(process.env.PHASE15_SEED_PATH!, 'utf-8')
) as {
  company_main: { id: string; name: string };
  admin: { email: string; password: string; user_id: string };
  creator: { email: string; password: string; user_id: string };
  approver: { email: string; password: string; user_id: string };
  contracts: {
    fresh_invoice_a: string;
    active_partial: string;
    active_overdue: string;
    active_settle: string;
    active_multi: string;
    active_advance: string;
    active_latecharge: string;
    defaulted_cure: string;
    defaulted_writeoff: string;
    active_reversal: string;
    pending_cancel: string;
  };
  bank_account_main: string;
  company_iso_a: { id: string; name: string };
  company_iso_b: { id: string; name: string };
  switcher: { email: string; password: string; user_id: string };
  active_iso_a: string;
  active_iso_b: string;
  company_k: { id: string; name: string };
  admin_k: { email: string; password: string; user_id: string };
  active_k: string;
  bank_account_k: string;
  company_l: { id: string; name: string };
  active_l: string;
};

export const API_BASE_URL = process.env.E2E_API_BASE_URL ?? 'http://localhost:8000';

export async function apiLogin(
  request: APIRequestContext,
  email: string,
  password: string
): Promise<string> {
  const res = await request.post(`${API_BASE_URL}/api/v1/auth/login`, {
    data: { email, password },
  });
  expect(res.ok(), `login failed for ${email}: ${await res.text()}`).toBeTruthy();
  const body = await res.json();
  return body.data.access_token as string;
}

export async function loginUI(page: Page, email: string, password: string): Promise<void> {
  await page.goto('/login');
  await page.locator('#login-email').fill(email);
  await page.locator('#login-password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('**/dashboard', { timeout: 30_000 });
}

/**
 * `/companies/{id}` (the only page that calls `setActiveCompany`) only
 * authorizes the company OWNER, not a member with a role (pre-existing,
 * Phase-13-verification-documented gap in
 * `modules/companies/dependencies.py`, unrelated to Installments). This
 * reproduces exactly what `CompanyContext.tsx`'s `persistActiveCompanyId`
 * does: set the localStorage key Installments' `getCompanyId()` reads,
 * and dispatch the same `erp-active-company-changed` event
 * `useInstallmentsPermissions` listens for.
 */
export async function selectCompanyUI(page: Page, companyId: string): Promise<void> {
  await page.evaluate((id) => {
    window.localStorage.setItem('erp_active_company_id', id);
    window.dispatchEvent(new Event('erp-active-company-changed'));
  }, companyId);
}

export const PLATFORM_OWNER = {
  email: 't221-e2e-owner@example.com',
  password: 'E2eOwnerPass!2026',
};
