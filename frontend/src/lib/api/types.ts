/**
 * API type definitions — TypeScript equivalents of backend Pydantic schemas.
 *
 * These types mirror the response envelopes defined in:
 *   backend/core/schemas/response.py
 *   backend/core/schemas/pagination.py
 *
 * Keep these in sync with the backend contract.
 */

/** Request-scoped metadata included in every API response. */
export interface ResponseMeta {
  /** The X-Request-ID that was assigned to this request. */
  request_id: string;
  /** ISO 8601 timestamp of the response. */
  timestamp: string;
}

/**
 * Standard single-item API response envelope.
 *
 * @template T — the type of the `data` payload
 */
export interface StandardResponse<T> {
  data: T;
  message: string;
  meta: ResponseMeta;
}

/** Structured error detail returned by the backend. */
export interface ErrorDetail {
  /** Machine-readable error code (e.g. "NOT_FOUND", "VALIDATION_ERROR"). */
  code: string;
  /** Human-readable error message. */
  message: string;
  /** Field-level or structured error details. */
  details: Record<string, unknown>;
}

/** Top-level error envelope returned for non-2xx responses. */
export interface ApiError {
  error: ErrorDetail;
}

/**
 * Paginated collection within the data field.
 *
 * @template T — the type of each item in the collection
 */
export interface PaginatedData<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/**
 * Standard paginated API response envelope.
 *
 * @template T — the type of each item in the collection
 */
export interface PaginatedResponse<T> {
  data: PaginatedData<T>;
  message: string;
  meta: ResponseMeta;
}
