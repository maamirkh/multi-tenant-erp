/**
 * Authentication API functions.
 *
 * All functions call the existing `apiClient` singleton. Return types match
 * the backend Pydantic schemas in `modules/auth/schemas/`.
 */

import type { LoginResponse, RefreshResponse, UserProfileResponse } from '@/types/auth';
import { apiClient } from './client';

/** POST /api/v1/auth/login — authenticate and receive tokens. */
export async function loginApi(
  email: string,
  password: string,
  rememberMe: boolean
): Promise<LoginResponse> {
  const res = await apiClient.post<LoginResponse>('/api/v1/auth/login', {
    email,
    password,
    remember_me: rememberMe,
  });
  return res.data;
}

/** POST /api/v1/auth/logout — revoke the current session server-side. */
export async function logoutApi(): Promise<void> {
  await apiClient.post<Record<string, string>>('/api/v1/auth/logout', {});
}

/** POST /api/v1/auth/refresh — rotate refresh token and receive new tokens. */
export async function refreshApi(refreshToken: string): Promise<RefreshResponse> {
  const res = await apiClient.post<RefreshResponse>('/api/v1/auth/refresh', {
    refresh_token: refreshToken,
  });
  return res.data;
}

/**
 * POST /api/v1/auth/forgot-password — request a password reset email.
 * Always returns successfully (anti-enumeration).
 */
export async function forgotPasswordApi(email: string): Promise<void> {
  await apiClient.post<Record<string, string>>('/api/v1/auth/forgot-password', { email });
}

/** POST /api/v1/auth/reset-password — set a new password using a reset token. */
export async function resetPasswordApi(token: string, newPassword: string): Promise<void> {
  await apiClient.post<Record<string, string>>('/api/v1/auth/reset-password', {
    token,
    new_password: newPassword,
    confirm_password: newPassword,
  });
}

/** POST /api/v1/auth/change-password — change password for an authenticated user. */
export async function changePasswordApi(
  currentPassword: string,
  newPassword: string
): Promise<void> {
  await apiClient.post<Record<string, string>>('/api/v1/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
    confirm_password: newPassword,
  });
}

/** GET /api/v1/auth/me — fetch the authenticated user's profile. */
export async function getMeApi(): Promise<UserProfileResponse> {
  const res = await apiClient.get<UserProfileResponse>('/api/v1/auth/me');
  return res.data;
}

/** POST /api/v1/auth/verify-email — consume an email verification token. */
export async function verifyEmailApi(token: string): Promise<void> {
  await apiClient.post<Record<string, string>>('/api/v1/auth/verify-email', { token });
}
