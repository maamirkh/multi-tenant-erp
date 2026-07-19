/**
 * TypeScript types for the Users & Roles module.
 *
 * Mirrors backend Pydantic schemas defined in:
 *   modules/users_roles/schemas/member.py
 *   modules/users_roles/schemas/role.py
 *   modules/users_roles/models/enums.py
 *
 * Keep in sync with backend contract.
 */

import type { Nullable, UUID } from '@/types';
import type { PaginatedData } from '@/lib/api/types';

// ── Enumerations ──────────────────────────────────────────────────────────────

export type MembershipStatus =
  | 'pending_invitation'
  | 'active'
  | 'inactive'
  | 'suspended'
  | 'locked'
  | 'archived';

export type MemberSortBy = 'name' | 'created_at' | 'role_rank' | 'department';
export type SortOrder = 'asc' | 'desc';

// ── Shared sub-types ──────────────────────────────────────────────────────────

/** Minimal role info embedded in member responses. */
export interface RoleSummary {
  id: UUID;
  name: string;
  slug: string;
  rank: number;
}

/** Minimal role record for role selector dropdowns. */
export interface RoleListItem {
  id: UUID;
  name: string;
  slug: string;
  rank: number;
  is_system: boolean;
  is_active: boolean;
  description: Nullable<string>;
  member_count: number;
  created_at: string;
}

// ── Member response types ─────────────────────────────────────────────────────

/** Member record returned by POST /members (add member). */
export interface MemberResponse {
  id: UUID;
  user_id: UUID;
  role: RoleSummary;
  status: MembershipStatus;
  created_at: string;
}

/** Member record in paginated list responses. */
export interface MemberListItem {
  id: UUID;
  user_id: UUID;
  display_name: string;
  email: string;
  avatar_url: Nullable<string>;
  role: RoleSummary;
  status: MembershipStatus;
  department: Nullable<string>;
  job_title: Nullable<string>;
  created_at: string;
}

/** Full member detail — returned by GET /members/{member_id}. */
export interface MemberDetail {
  id: UUID;
  user_id: UUID;
  company_id: UUID;
  display_name: string;
  email: string;
  avatar_url: Nullable<string>;
  role: RoleSummary;
  status: MembershipStatus;
  employee_id: Nullable<string>;
  job_title: Nullable<string>;
  department: Nullable<string>;
  work_phone: Nullable<string>;
  hire_date: Nullable<string>;
  notes: Nullable<string>;
  invited_by: Nullable<UUID>;
  invitation_accepted_at: Nullable<string>;
  created_at: string;
  updated_at: string;
}

// ── Request / Input types ─────────────────────────────────────────────────────

export interface AddMemberInput {
  email: string;
  role_id: UUID;
  employee_id?: string;
  job_title?: string;
  department?: string;
  work_phone?: string;
  hire_date?: string;
  notes?: string;
}

export interface UpdateMemberInput {
  role_id?: UUID;
  employee_id?: string | null;
  job_title?: string | null;
  department?: string | null;
  work_phone?: string | null;
  hire_date?: string | null;
  notes?: string | null;
}

export interface SuspendMemberInput {
  reason: string;
}

export interface ArchiveMemberInput {
  reason: string;
}

// ── Query parameter types ─────────────────────────────────────────────────────

export interface MemberListParams {
  status?: MembershipStatus;
  role_id?: UUID;
  department?: string;
  search?: string;
  page?: number;
  page_size?: number;
  sort_by?: MemberSortBy;
  sort_order?: SortOrder;
}

// ── Role types (Phase 12) ─────────────────────────────────────────────────────

/**
 * Single permission from the global catalogue.
 * Returned by GET /api/v1/permissions (no `id` field — use `code` as key).
 */
export interface PermissionCatalogItem {
  code: string;
  label: string;
  module: string;
  action: string;
  description: Nullable<string>;
}

/** Permission in a role detail response (includes `id`). */
export interface PermissionItem {
  id: string;
  code: string;
  label: string;
  module: string;
  action: string;
  description: Nullable<string>;
}

/** Permissions grouped by module — returned by GET /api/v1/permissions. */
export interface PermissionGroup {
  module: string;
  permissions: PermissionCatalogItem[];
}

/** Full role detail — returned by GET /companies/{company_id}/roles/{role_id}. */
export interface RoleDetail {
  id: UUID;
  company_id: UUID;
  name: string;
  slug: string;
  description: Nullable<string>;
  rank: number;
  is_system: boolean;
  is_active: boolean;
  member_count: number;
  permissions: PermissionItem[];
  created_at: string;
  updated_at: string;
}

/** Request body for POST /companies/{company_id}/roles. */
export interface CreateRoleInput {
  name: string;
  description?: string;
  rank: number;
  permission_codes: string[];
}

/** Request body for PATCH /companies/{company_id}/roles/{role_id}. */
export interface UpdateRoleInput {
  name?: string;
  description?: string | null;
  rank?: number;
  permission_codes?: string[];
}

// ── Profile types (Phase 13) ──────────────────────────────────────────────────

/** Response from GET/PATCH /api/v1/profile. */
export interface UserProfile {
  id: UUID;
  email: string;
  display_name: string;
  phone: Nullable<string>;
  avatar_url: Nullable<string>;
  created_at: string;
  updated_at: string;
}

/** Response from POST /api/v1/profile/avatar. */
export interface AvatarUploadResult {
  avatar_url: string;
}

/** Request body for PATCH /api/v1/profile. */
export interface UpdateProfileInput {
  display_name?: string;
  phone?: string | null;
}

// ── Preference types (Phase 13) ───────────────────────────────────────────────

export type ThemePreference = 'light' | 'dark' | 'system';
export type DateFormatOption = 'YYYY-MM-DD' | 'DD/MM/YYYY' | 'MM/DD/YYYY' | 'DD-MM-YYYY';

/** Response from GET/PUT /api/v1/preferences. */
export interface UserPreferences {
  language: string;
  timezone: string;
  date_format: string;
  number_format: string;
  theme: string;
  notification_preferences: Record<string, unknown>;
}

/** Request body for PUT /api/v1/preferences. */
export interface UpdatePreferencesInput {
  language?: string;
  timezone?: string;
  date_format?: DateFormatOption;
  number_format?: string;
  theme?: ThemePreference;
}

// Re-export paginated type for hooks.
export type { PaginatedData };
