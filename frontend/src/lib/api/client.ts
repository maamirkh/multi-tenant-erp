/**
 * API Client — typed fetch wrapper for the DevSphere ERP backend.
 *
 * All requests prepend the base URL from NEXT_PUBLIC_API_URL and include
 * a Content-Type: application/json header. Non-2xx responses are parsed
 * and thrown as typed ApiError instances.
 *
 * [T178, ADR-11] Structurally prevents token crossover: `ApiClient` holds
 * no auth state of its own — it delegates every token read/refresh/
 * failure decision to an injected `AuthStrategy`. Each domain (tenant,
 * platform) supplies its own strategy backed by its own storage module,
 * so two `ApiClient` instances constructed with different strategies can
 * never read or clear each other's tokens.
 *
 * Usage:
 *   import { apiClient } from '@/lib/api/client';
 *   const res = await apiClient.get<HealthData>('/api/v1/health');
 */

import { tenantAuthStrategy } from '@/lib/auth/tenantAuthStrategy';
import type { ApiError, StandardResponse } from './types';

/**
 * The auth contract an `ApiClient` instance delegates to. Each domain
 * (tenant, Platform) implements this against its own token storage and
 * refresh lock — `ApiClient` itself never imports a storage module
 * directly, which is what makes crossover structurally impossible
 * rather than merely convention.
 */
export interface AuthStrategy {
  /** Return the current access token for this domain, or null if unset. */
  getToken(): string | null;
  /**
   * Attempt to refresh this domain's tokens (via that domain's own
   * single-flight lock). Resolves once new tokens are stored; rejects
   * on failure — callers must not assume `getToken()` changed unless
   * this resolves.
   */
  refresh(): Promise<void>;
  /**
   * Called when refresh has failed and the session cannot be recovered.
   * Responsible for clearing this domain's own tokens and notifying
   * this domain's own listeners (never the other domain's).
   */
  onAuthFailure(): void;
}

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
  private readonly auth: AuthStrategy;

  constructor(auth: AuthStrategy, baseUrl?: string) {
    this.auth = auth;
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
    // Request interceptor: attach Bearer token via the injected strategy.
    const accessToken = this.auth.getToken();
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
    body?: unknown,
    extraHeaders?: Record<string, string>
  ): Promise<StandardResponse<T>> {
    const init: RequestInit = {
      method,
      headers: { ...this.buildHeaders(), ...extraHeaders },
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
          await this.auth.refresh();
          // Retry the original request with the new access token.
          const retryInit: RequestInit = {
            method,
            headers: { ...this.buildHeaders(), ...extraHeaders },
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
          // Refresh failed — the strategy's own refresh() already cleared
          // its tokens (mirroring the tenant lock's existing behaviour);
          // onAuthFailure() is this domain's own notification hook.
          if (refreshErr instanceof ApiClientError) throw refreshErr;
          this.auth.onAuthFailure();
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

  /**
   * HTTP POST with extra request headers (e.g. `Idempotency-Key` for
   * protected commands — Installments' activation/collection/reversal/
   * settlement/reschedule/cancel/default/writeoff endpoints, plan.md §20).
   * No existing module needed this before Installments; kept as a
   * separate method rather than changing `post()`'s signature so every
   * existing call site is untouched.
   */
  async postWithHeaders<T>(
    path: string,
    body: unknown,
    extraHeaders: Record<string, string>
  ): Promise<StandardResponse<T>> {
    return this.request<T>('POST', path, body, extraHeaders);
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
    const accessToken = this.auth.getToken();
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

/**
 * Singleton API client instance used throughout the application —
 * backed by the tenant `AuthStrategy` (T179). Every existing domain file
 * (`accounting.ts`, `crm.ts`, `sales.ts`, etc.) continues importing this
 * same export unmodified; behaviour is byte-identical to before T178.
 */
export const apiClient = new ApiClient(tenantAuthStrategy);
