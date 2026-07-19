/**
 * Unit tests for authentication API functions.
 *
 * T092 — verify remember_me flag passes through loginApi to apiClient.
 */

import { loginApi } from '../auth';

// Mock apiClient so no real network calls are made.
jest.mock('../client', () => ({
  apiClient: {
    post: jest.fn(),
    get: jest.fn(),
  },
  ApiClientError: class ApiClientError extends Error {
    status: number;
    error: unknown;
    constructor(status: number, error: unknown) {
      super('ApiClientError');
      this.status = status;
      this.error = error;
    }
  },
}));

import { apiClient } from '../client';

const mockPost = apiClient.post as jest.MockedFunction<typeof apiClient.post>;

describe('loginApi', () => {
  beforeEach(() => {
    mockPost.mockReset();
  });

  it('passes remember_me=false to the backend by default', async () => {
    mockPost.mockResolvedValue({
      data: {
        access_token: 'access',
        refresh_token: 'refresh',
        token_type: 'bearer',
        expires_in: 900,
      },
      message: 'ok',
      meta: { request_id: 'r1', timestamp: '' },
    });

    await loginApi('user@example.com', 'pass', false);

    expect(mockPost).toHaveBeenCalledWith('/api/v1/auth/login', {
      email: 'user@example.com',
      password: 'pass',
      remember_me: false,
    });
  });

  it('T092 — passes remember_me=true to the backend when rememberMe is true', async () => {
    mockPost.mockResolvedValue({
      data: {
        access_token: 'access-long',
        refresh_token: 'refresh-long',
        token_type: 'bearer',
        // 30-day token: 30 * 24 * 60 * 60 = 2592000 seconds
        expires_in: 2592000,
      },
      message: 'ok',
      meta: { request_id: 'r2', timestamp: '' },
    });

    const result = await loginApi('user@example.com', 'pass', true);

    // Verify the flag was forwarded to the backend.
    expect(mockPost).toHaveBeenCalledWith('/api/v1/auth/login', {
      email: 'user@example.com',
      password: 'pass',
      remember_me: true,
    });

    // The response expires_in should reflect the longer lifetime.
    expect(result.expires_in).toBe(2592000);
  });
});
