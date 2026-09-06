/**
 * `acquireRefreshLock()` race-condition regression test.
 *
 * Reproduces a real bug found while E2E-testing Epic 10 Phase 15: visiting
 * /login while already authenticated as User A silently kicks off a
 * background refresh of A's session (AuthContext's own hydration effect).
 * If a NEW login (User B) completes before that background refresh
 * resolves, the refresh's `.then()` used to call storeTokens() unconditionally
 * — clobbering B's freshly-stored tokens with A's stale (if freshly rotated)
 * ones, silently reverting the browser to A's session. `acquireRefreshLock()`
 * now stamps an epoch at call-start and discards its own result (store or
 * clear) if a newer storeTokens()/clearTokens() call already superseded it.
 */

import { acquireRefreshLock } from '@/lib/auth/client';
import { clearTokens, getAccessToken, getRefreshToken, storeTokens } from '@/lib/auth/tokenStorage';

describe('acquireRefreshLock — stale-refresh race guard', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    clearTokens();
    localStorage.clear();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('does not clobber a newer login that completes while an older refresh is still in flight', async () => {
    storeTokens('user-a-access', 'user-a-refresh');

    let resolveFetch!: (value: unknown) => void;
    global.fetch = jest.fn().mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      })
    ) as unknown as typeof fetch;

    // Simulates AuthContext's hydrate() effect starting a refresh for the
    // currently-stored (User A) session on mount.
    const staleRefresh = acquireRefreshLock();

    // A brand-new login for User B completes before the stale refresh above
    // resolves — exactly the real-world race (form submit finishes while a
    // silent background hydration refresh is still pending).
    storeTokens('user-b-access', 'user-b-refresh');

    // The stale refresh for User A finally resolves.
    resolveFetch({
      ok: true,
      json: async () => ({
        data: {
          access_token: 'user-a-access-ROTATED',
          refresh_token: 'user-a-refresh-ROTATED',
          expires_in: 900,
        },
      }),
    });
    await staleRefresh;

    // User B's tokens must still be in effect — not overwritten by A's
    // late-arriving, now-stale rotation.
    expect(getAccessToken()).toBe('user-b-access');
    expect(getRefreshToken()).toBe('user-b-refresh');
  });

  it('does not clear a newer session if a superseded refresh fails', async () => {
    storeTokens('user-a-access', 'user-a-refresh');

    let rejectFetch!: (reason: unknown) => void;
    global.fetch = jest.fn().mockReturnValue(
      new Promise((_resolve, reject) => {
        rejectFetch = reject;
      })
    ) as unknown as typeof fetch;

    const staleRefresh = acquireRefreshLock();
    storeTokens('user-b-access', 'user-b-refresh');

    rejectFetch(new Error('network error'));
    await expect(staleRefresh).rejects.toThrow();

    // User B's session must survive A's stale, now-failed refresh attempt.
    expect(getAccessToken()).toBe('user-b-access');
    expect(getRefreshToken()).toBe('user-b-refresh');
  });

  it('still persists a refresh result when no newer login intervenes (normal path)', async () => {
    storeTokens('user-a-access', 'user-a-refresh');

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          access_token: 'user-a-access-ROTATED',
          refresh_token: 'user-a-refresh-ROTATED',
          expires_in: 900,
        },
      }),
    }) as unknown as typeof fetch;

    await acquireRefreshLock();

    expect(getAccessToken()).toBe('user-a-access-ROTATED');
    expect(getRefreshToken()).toBe('user-a-refresh-ROTATED');
  });
});
