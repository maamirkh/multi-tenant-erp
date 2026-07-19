/**
 * Unit tests for tokenStorage.
 *
 * Phase 10 Checkpoint:
 *   tokenStorage.storeTokens("a","b") stores "b" in localStorage["erp_refresh_token"]
 *   and keeps "a" in memory only (not in localStorage).
 */

import { clearTokens, getAccessToken, getRefreshToken, storeTokens } from '../tokenStorage';

describe('tokenStorage', () => {
  beforeEach(() => {
    localStorage.clear();
    clearTokens();
  });

  it('storeTokens stores access token in memory only — not in localStorage', () => {
    storeTokens('access-abc', 'refresh-xyz');
    expect(getAccessToken()).toBe('access-abc');
    // Access token must NOT be in localStorage.
    expect(localStorage.getItem('access-abc')).toBeNull();
    // Confirm no other key holds the access token.
    expect(localStorage.length).toBe(1); // only the refresh key
  });

  it('storeTokens stores refresh token in localStorage under erp_refresh_token', () => {
    storeTokens('a', 'b');
    expect(localStorage.getItem('erp_refresh_token')).toBe('b');
  });

  it('getAccessToken returns null before any token is stored', () => {
    expect(getAccessToken()).toBeNull();
  });

  it('getRefreshToken returns null when localStorage is empty', () => {
    expect(getRefreshToken()).toBeNull();
  });

  it('getRefreshToken returns the stored refresh token', () => {
    storeTokens('access', 'my-refresh-token');
    expect(getRefreshToken()).toBe('my-refresh-token');
  });

  it('clearTokens removes access token from memory', () => {
    storeTokens('access', 'refresh');
    clearTokens();
    expect(getAccessToken()).toBeNull();
  });

  it('clearTokens removes refresh token from localStorage', () => {
    storeTokens('access', 'refresh');
    clearTokens();
    expect(getRefreshToken()).toBeNull();
    expect(localStorage.getItem('erp_refresh_token')).toBeNull();
  });

  it('overwriting tokens replaces both values', () => {
    storeTokens('old-access', 'old-refresh');
    storeTokens('new-access', 'new-refresh');
    expect(getAccessToken()).toBe('new-access');
    expect(getRefreshToken()).toBe('new-refresh');
  });
});
