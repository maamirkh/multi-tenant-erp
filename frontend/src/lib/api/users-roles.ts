/**
 * Users & Roles API — typed fetch functions wrapping the shared ApiClient.
 *
 * Covers all member lifecycle endpoints per contracts/members-api.yaml.
 * Role endpoints (T102) will be added in Phase 12.
 *
 * Spec reference: Epic 4, Phase 11 (T087).
 */

import { apiClient } from '@/lib/api/client';
import type { PaginatedData } from '@/lib/api/types';
import type {
  AddMemberInput,
  ArchiveMemberInput,
  AvatarUploadResult,
  CreateRoleInput,
  MemberDetail,
  MemberListItem,
  MemberListParams,
  MemberResponse,
  PermissionGroup,
  RoleDetail,
  RoleListItem,
  SuspendMemberInput,
  UpdateMemberInput,
  UpdatePreferencesInput,
  UpdateProfileInput,
  UpdateRoleInput,
  UserPreferences,
  UserProfile,
} from '@/types/users-roles';

// ── Member endpoints ──────────────────────────────────────────────────────────

/** GET /companies/{company_id}/members — paginated member list. */
export async function listMembers(
  companyId: string,
  params: MemberListParams = {}
): Promise<PaginatedData<MemberListItem>> {
  const query = new URLSearchParams();
  if (params.status !== undefined) query.set('status', params.status);
  if (params.role_id !== undefined) query.set('role_id', params.role_id);
  if (params.department !== undefined) query.set('department', params.department);
  if (params.search !== undefined) query.set('search', params.search);
  if (params.page !== undefined) query.set('page', String(params.page));
  if (params.page_size !== undefined) query.set('page_size', String(params.page_size));
  if (params.sort_by !== undefined) query.set('sort_by', params.sort_by);
  if (params.sort_order !== undefined) query.set('sort_order', params.sort_order);

  const qs = query.toString();
  const path = `/api/v1/companies/${companyId}/members${qs ? `?${qs}` : ''}`;
  const res = await apiClient.get<PaginatedData<MemberListItem>>(path);
  return res.data;
}

/** GET /companies/{company_id}/members/{member_id} — full member detail. */
export async function getMember(
  companyId: string,
  memberId: string
): Promise<MemberDetail> {
  const res = await apiClient.get<MemberDetail>(
    `/api/v1/companies/${companyId}/members/${memberId}`
  );
  return res.data;
}

/** POST /companies/{company_id}/members — add a new member. */
export async function addMember(
  companyId: string,
  data: AddMemberInput
): Promise<MemberResponse> {
  const res = await apiClient.post<MemberResponse>(
    `/api/v1/companies/${companyId}/members`,
    data
  );
  return res.data;
}

/** PATCH /companies/{company_id}/members/{member_id} — update member info. */
export async function updateMember(
  companyId: string,
  memberId: string,
  data: UpdateMemberInput
): Promise<MemberDetail> {
  const res = await apiClient.patch<MemberDetail>(
    `/api/v1/companies/${companyId}/members/${memberId}`,
    data
  );
  return res.data;
}

/** POST /companies/{company_id}/members/{member_id}/deactivate */
export async function deactivateMember(
  companyId: string,
  memberId: string
): Promise<MemberDetail> {
  const res = await apiClient.post<MemberDetail>(
    `/api/v1/companies/${companyId}/members/${memberId}/deactivate`,
    {}
  );
  return res.data;
}

/** POST /companies/{company_id}/members/{member_id}/suspend */
export async function suspendMember(
  companyId: string,
  memberId: string,
  data: SuspendMemberInput
): Promise<MemberDetail> {
  const res = await apiClient.post<MemberDetail>(
    `/api/v1/companies/${companyId}/members/${memberId}/suspend`,
    data
  );
  return res.data;
}

/** POST /companies/{company_id}/members/{member_id}/lock */
export async function lockMember(
  companyId: string,
  memberId: string
): Promise<MemberDetail> {
  const res = await apiClient.post<MemberDetail>(
    `/api/v1/companies/${companyId}/members/${memberId}/lock`,
    {}
  );
  return res.data;
}

/** POST /companies/{company_id}/members/{member_id}/reactivate */
export async function reactivateMember(
  companyId: string,
  memberId: string
): Promise<MemberDetail> {
  const res = await apiClient.post<MemberDetail>(
    `/api/v1/companies/${companyId}/members/${memberId}/reactivate`,
    {}
  );
  return res.data;
}

/** POST /companies/{company_id}/members/{member_id}/archive */
export async function archiveMember(
  companyId: string,
  memberId: string,
  data: ArchiveMemberInput
): Promise<MemberDetail> {
  const res = await apiClient.post<MemberDetail>(
    `/api/v1/companies/${companyId}/members/${memberId}/archive`,
    data
  );
  return res.data;
}

/** POST /companies/{company_id}/members/{member_id}/restore */
export async function restoreMember(
  companyId: string,
  memberId: string
): Promise<MemberDetail> {
  const res = await apiClient.post<MemberDetail>(
    `/api/v1/companies/${companyId}/members/${memberId}/restore`,
    {}
  );
  return res.data;
}

// ── Role endpoints (T102) ─────────────────────────────────────────────────────

/** GET /companies/{company_id}/roles — list all roles with member counts. */
export async function listRoles(companyId: string): Promise<RoleListItem[]> {
  const res = await apiClient.get<RoleListItem[]>(
    `/api/v1/companies/${companyId}/roles`
  );
  return res.data;
}

/** GET /companies/{company_id}/roles/{role_id} — full role detail with permissions. */
export async function getRole(
  companyId: string,
  roleId: string
): Promise<RoleDetail> {
  const res = await apiClient.get<RoleDetail>(
    `/api/v1/companies/${companyId}/roles/${roleId}`
  );
  return res.data;
}

/** POST /companies/{company_id}/roles — create a custom role. */
export async function createRole(
  companyId: string,
  data: CreateRoleInput
): Promise<RoleDetail> {
  const res = await apiClient.post<RoleDetail>(
    `/api/v1/companies/${companyId}/roles`,
    data
  );
  return res.data;
}

/** PATCH /companies/{company_id}/roles/{role_id} — update a custom role. */
export async function updateRole(
  companyId: string,
  roleId: string,
  data: UpdateRoleInput
): Promise<RoleDetail> {
  const res = await apiClient.patch<RoleDetail>(
    `/api/v1/companies/${companyId}/roles/${roleId}`,
    data
  );
  return res.data;
}

/** DELETE /companies/{company_id}/roles/{role_id} — delete a custom role (204). */
export async function deleteRole(
  companyId: string,
  roleId: string
): Promise<void> {
  await apiClient.delete(`/api/v1/companies/${companyId}/roles/${roleId}`);
}

// ── Permissions endpoint (T102) ───────────────────────────────────────────────

/** GET /api/v1/permissions — list all permissions grouped by module. */
export async function listPermissions(): Promise<PermissionGroup[]> {
  const res = await apiClient.get<PermissionGroup[]>('/api/v1/permissions');
  return res.data;
}

// ── Profile endpoints (T114) ──────────────────────────────────────────────────

/** GET /api/v1/profile — current user's profile. */
export async function getProfile(): Promise<UserProfile> {
  const res = await apiClient.get<UserProfile>('/api/v1/profile');
  return res.data;
}

/** PATCH /api/v1/profile — update display name and/or phone. */
export async function updateProfile(data: UpdateProfileInput): Promise<UserProfile> {
  const res = await apiClient.patch<UserProfile>('/api/v1/profile', data);
  return res.data;
}

/** POST /api/v1/profile/avatar — upload avatar image (multipart). */
export async function uploadAvatar(file: File): Promise<AvatarUploadResult> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await apiClient.postMultipart<AvatarUploadResult>(
    '/api/v1/profile/avatar',
    formData
  );
  return res.data;
}

/** DELETE /api/v1/profile/avatar — remove current avatar (204 No Content). */
export async function deleteAvatar(): Promise<void> {
  await apiClient.delete('/api/v1/profile/avatar');
}

// ── Preferences endpoints (T114) ──────────────────────────────────────────────

/** GET /api/v1/preferences — current user's preferences (creates defaults if none). */
export async function getPreferences(): Promise<UserPreferences> {
  const res = await apiClient.get<UserPreferences>('/api/v1/preferences');
  return res.data;
}

/** PUT /api/v1/preferences — update user preferences. */
export async function updatePreferences(data: UpdatePreferencesInput): Promise<UserPreferences> {
  const res = await apiClient.put<UserPreferences>('/api/v1/preferences', data);
  return res.data;
}

// ── Ownership transfer endpoint (T122) ────────────────────────────────────────

/** POST /companies/{company_id}/transfer-ownership — transfer ownership to an active member. */
export async function transferOwnership(
  companyId: string,
  targetMemberId: string
): Promise<void> {
  await apiClient.post(
    `/api/v1/companies/${companyId}/transfer-ownership`,
    { target_member_id: targetMemberId }
  );
}
