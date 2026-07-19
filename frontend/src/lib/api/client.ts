/**
 * API Client — typed fetch wrapper for the DevSphere ERP backend.
 *
 * All requests prepend the base URL from NEXT_PUBLIC_API_URL and include
 * a Content-Type: application/json header. Non-2xx responses are parsed
 * and thrown as typed ApiError instances.
 *
 * Usage:
 *   import { apiClient } from '@/lib/api/client';
 *   const res = await apiClient.get<HealthData>('/api/v1/health');
 */

import { acquireRefreshLock } from '@/lib/auth/client';
import { clearTokens, getAccessToken } from '@/lib/auth/tokenStorage';
import type { ApiError, StandardResponse } from './types';

/** Runtime error raised when the API returns a non-2xx status code. */
export class ApiClientError extends Error {
  public readonly status: number;
  public readonly error: ApiError;

  constructor(status: number, error: ApiError) {
    super(error.error.message);
    this.name = 'ApiClientError';
    this.status = status;
    this.error = error;
  }
}

/** Base URL for all API requests. Falls back to localhost for development. */
const DEFAULT_BASE_URL = 'http://localhost:8000';

export class ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl =
      baseUrl ??
      (typeof process !== 'undefined'
        ? (process.env['NEXT_PUBLIC_API_URL'] ?? DEFAULT_BASE_URL)
        : DEFAULT_BASE_URL);
  }

  private buildUrl(path: string): string {
    const normalised = path.startsWith('/') ? path : `/${path}`;
    return `${this.baseUrl}${normalised}`;
  }

  private buildHeaders(): HeadersInit {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    // Request interceptor: attach Bearer token from in-memory storage.
    const accessToken = getAccessToken();
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }
    return headers;
  }

  private async parseError(response: Response): Promise<ApiError> {
    try {
      return (await response.json()) as ApiError;
    } catch {
      return {
        error: {
          code: 'NETWORK_ERROR',
          message: `HTTP ${response.status}: ${response.statusText}`,
          details: {},
        },
      };
    }
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown
  ): Promise<StandardResponse<T>> {
    const init: RequestInit = {
      method,
      headers: this.buildHeaders(),
    };

    if (body !== undefined) {
      init.body = JSON.stringify(body);
    }

    const response = await fetch(this.buildUrl(path), init);

    // Response interceptor: on 401 TOKEN_EXPIRED, refresh and retry once.
    if (response.status === 401) {
      const apiError = await this.parseError(response);
      if (apiError.error?.code === 'TOKEN_EXPIRED') {
        try {
          await acquireRefreshLock();
          // Retry the original request with the new access token.
          const retryInit: RequestInit = {
            method,
            headers: this.buildHeaders(),
          };
          if (body !== undefined) {
            retryInit.body = JSON.stringify(body);
          }
          const retryResponse = await fetch(this.buildUrl(path), retryInit);
          if (!retryResponse.ok) {
            throw new ApiClientError(retryResponse.status, await this.parseError(retryResponse));
          }
          return retryResponse.json() as Promise<StandardResponse<T>>;
        } catch (refreshErr) {
          // Refresh failed — tokens already cleared by acquireRefreshLock.
          if (refreshErr instanceof ApiClientError) throw refreshErr;
          clearTokens();
          if (typeof window !== 'undefined') {
            window.dispatchEvent(new Event('session-expired'));
          }
          throw new ApiClientError(401, apiError);
        }
      }
      throw new ApiClientError(401, apiError);
    }

    if (!response.ok) {
      throw new ApiClientError(response.status, await this.parseError(response));
    }

    // 204 No Content — no body to parse.
    if (response.status === 204) {
      return {} as StandardResponse<T>;
    }

    return response.json() as Promise<StandardResponse<T>>;
  }

  /** HTTP GET — fetch a resource. */
  async get<T>(path: string): Promise<StandardResponse<T>> {
    return this.request<T>('GET', path);
  }

  /** HTTP POST — create a resource. */
  async post<T>(path: string, body: unknown): Promise<StandardResponse<T>> {
    return this.request<T>('POST', path, body);
  }

  /** HTTP PATCH — partially update a resource. */
  async patch<T>(path: string, body: unknown): Promise<StandardResponse<T>> {
    return this.request<T>('PATCH', path, body);
  }

  /** HTTP PUT — replace a resource. */
  async put<T>(path: string, body: unknown): Promise<StandardResponse<T>> {
    return this.request<T>('PUT', path, body);
  }

  /** HTTP DELETE — remove a resource without a request body. */
  async delete<T>(path: string): Promise<StandardResponse<T>> {
    return this.request<T>('DELETE', path);
  }

  /** HTTP DELETE — remove a resource with a JSON request body. */
  async deleteWithBody<T>(path: string, body: unknown): Promise<StandardResponse<T>> {
    return this.request<T>('DELETE', path, body);
  }

  /** HTTP POST — send a multipart/form-data request (e.g. file upload). */
  async postMultipart<T>(path: string, formData: FormData): Promise<StandardResponse<T>> {
    const headers: Record<string, string> = {};
    const accessToken = getAccessToken();
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }
    const response = await fetch(this.buildUrl(path), {
      method: 'POST',
      headers,
      body: formData,
    });
    if (!response.ok) {
      throw new ApiClientError(response.status, await this.parseError(response));
    }
    return response.json() as Promise<StandardResponse<T>>;
  }
}

/** Singleton API client instance used throughout the application. */
export const apiClient = new ApiClient();
