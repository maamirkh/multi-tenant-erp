/**
 * Authentication TypeScript types.
 *
 * These interfaces mirror the backend Pydantic schemas in:
 *   backend/modules/auth/schemas/auth.py
 *   backend/modules/auth/schemas/user.py
 *
 * Keep in sync with backend contract when schemas change.
 */

import type { UUID } from './index';

/** Response from POST /api/v1/auth/login */
export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  /** Access token lifetime in seconds. */
  expires_in: number;
}

/** Response from POST /api/v1/auth/refresh */
export interface RefreshResponse {
  access_token: string;
  /** Rotated refresh token — old one is revoked. */
  refresh_token: string;
  /** Access token lifetime in seconds. */
  expires_in: number;
}

/** Response from GET /api/v1/auth/me */
export interface UserProfileResponse {
  user_id: UUID;
  email: string;
  display_name: string;
  /** ACTIVE | INACTIVE | LOCKED | DELETED */
  account_status: string;
  is_email_verified: boolean;
  /** ISO 8601 UTC timestamp. */
  created_at: string;
}

/** Auth state managed by AuthContext. */
export interface AuthState {
  user: UserProfileResponse | null;
  isAuthenticated: boolean;
  /** True while session is being hydrated on mount. */
  isLoading: boolean;
}

/** Value exposed by AuthContext. */
export interface AuthContextValue extends AuthState {
  /** Authenticate, store tokens, load profile. Throws on failure. */
  login: (email: string, password: string, rememberMe: boolean) => Promise<void>;
  /** Revoke tokens server-side, clear local state. */
  logout: () => Promise<void>;
}
