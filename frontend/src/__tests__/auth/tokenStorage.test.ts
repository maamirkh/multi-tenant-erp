/**
 * T123 — tokenStorage tests.
 *
 * Tests: storeTokens keeps access token OUT of localStorage;
 * storeTokens puts refresh token IN localStorage;
 * clearTokens removes from both;
 * getAccessToken returns the in-memory value.
 */

import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  storeTokens,
} from '@/lib/auth/tokenStorage';

const REFRESH_KEY = 'erp_refresh_token';

describe('T123 — tokenStorage', () => {
  beforeEach(() => {
    clearTokens();
    localStorage.clear();
  });

  it('storeTokens keeps access token OUT of localStorage', () => {
    storeTokens('my-access', 'my-refresh');
    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('erp_access_token')).toBeNull();
  });

  it('storeTokens puts refresh token IN localStorage', () => {
    storeTokens('my-access', 'my-refresh');
    expect(localStorage.getItem(REFRESH_KEY)).toBe('my-refresh');
  });

  it('clearTokens removes refresh token from localStorage', () => {
    storeTokens('my-access', 'my-refresh');
    clearTokens();
    expect(localStorage.getItem(REFRESH_KEY)).toBeNull();
  });

  it('clearTokens removes access token from memory', () => {
    storeTokens('my-access', 'my-refresh');
    clearTokens();
    expect(getAccessToken()).toBeNull();
  });

  it('getAccessToken returns in-memory value after storeTokens', () => {
    storeTokens('tok-abc', 'ref-xyz');
    expect(getAccessToken()).toBe('tok-abc');
  });

  it('getRefreshToken returns value from localStorage', () => {
    storeTokens('tok-abc', 'ref-xyz');
    expect(getRefreshToken()).toBe('ref-xyz');
  });
});
