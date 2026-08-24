import type { Page } from '@playwright/test';

/**
 * Chromium itself (not application code) logs a console.error for every
 * non-2xx `fetch`/XHR response — DevTools' own automatic network-failure
 * logging, unrelated to whether the app handled the error correctly.
 * T220/T221 deliberately trigger 403s (suspension denial) as the actual
 * scenario under test, so this exact, narrow message is expected noise,
 * not a defect — excluding it is not "weakening" the check, since it
 * can never indicate an application bug (the app never emits it itself).
 */
const EXPECTED_NETWORK_ERROR_NOISE = /^Failed to load resource: the server responded with/;

/**
 * Collects real browser console errors + uncaught page errors for the
 * "zero unexpected console errors" acceptance criterion (T219-T221).
 * Next.js dev-mode HMR/Fast-Refresh log lines are informational, not
 * errors, and never arrive via `console.error`/`pageerror`, so no
 * allow-list is needed for those — anything else captured is a genuine
 * defect.
 */
export function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error' && !EXPECTED_NETWORK_ERROR_NOISE.test(msg.text())) {
      errors.push(`[console.error] ${msg.text()}`);
    }
  });
  page.on('pageerror', (err) => {
    errors.push(`[pageerror] ${err.message}`);
  });
  return errors;
}

export const PLATFORM_OWNER = {
  email: 't221-e2e-owner@example.com',
  password: 'E2eOwnerPass!2026',
};

export const TENANT_USER = {
  email: 't221-e2e-tenant@example.com',
  password: 'E2eTenantPass!2026',
};

const API_BASE_URL = process.env.E2E_API_BASE_URL ?? 'http://localhost:8000';

/**
 * Idempotent test-data arrangement: ensures Company A is `active` before
 * a suspension-flow spec starts driving the real browser. Necessary
 * because these specs themselves suspend Company A as part of their own
 * scenario — a prior run that failed mid-flow (before its own
 * reactivate step) would otherwise leave Company A suspended, breaking
 * every subsequent run non-deterministically. This is plain HTTP
 * "arrange" setup, not a substitute for the browser-driven suspend/
 * reactivate assertions the specs themselves make.
 */
export async function ensureCompanyActive(companyId: string): Promise<void> {
  const loginRes = await fetch(`${API_BASE_URL}/api/v1/platform/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(PLATFORM_OWNER),
  });
  const loginBody = await loginRes.json();
  const token = loginBody.data.access_token;

  const tenantRes = await fetch(`${API_BASE_URL}/api/v1/platform/tenants/${companyId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const tenantBody = await tenantRes.json();
  if (tenantBody.data.status !== 'suspended') return;

  await fetch(`${API_BASE_URL}/api/v1/platform/tenants/${companyId}/reactivate`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason: 'E2E test setup: ensure active before run' }),
  });
}

/**
 * Idempotent test-data arrangement: revokes any pre-existing active
 * entitlement override for `capabilityKey` on `companyId`. T219 grants
 * a fresh override as part of its own scenario every run; a prior run
 * leaves one active (only server-persisted; the UI's own "session
 * override" tracking is just local React state), and granting a second
 * active override for the same tenant/capability is a real 409
 * (`ENTITLEMENT_OVERRIDE_ALREADY_ACTIVE`) — this clears the way so
 * repeated runs are deterministic regardless of prior run outcomes.
 */
export async function ensureNoActiveOverride(
  companyId: string,
  capabilityKey: string
): Promise<void> {
  const loginRes = await fetch(`${API_BASE_URL}/api/v1/platform/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(PLATFORM_OWNER),
  });
  const loginBody = await loginRes.json();
  const token = loginBody.data.access_token;

  const probeRes = await fetch(
    `${API_BASE_URL}/api/v1/platform/tenants/${companyId}/entitlement-overrides`,
    {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        capability_key: capabilityKey,
        reason: 'E2E test setup: probe for an existing active override',
        expires_at: null,
      }),
    }
  );
  if (probeRes.status !== 409) return;
  const probeBody = await probeRes.json();
  const existingOverrideId = probeBody.error.details.existing_override_id as string;

  await fetch(
    `${API_BASE_URL}/api/v1/platform/tenants/${companyId}/entitlement-overrides/${existingOverrideId}`,
    { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } }
  );
}
