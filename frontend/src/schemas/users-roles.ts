/**
 * Zod validation schemas for the Users & Roles module.
 *
 * Mirrors backend Pydantic schemas:
 *   modules/users_roles/schemas/member.py
 *   modules/users_roles/schemas/member_status.py
 *
 * Spec reference: Epic 4, Phase 11 (T088).
 */

import { z } from 'zod';

// ── Add Member ────────────────────────────────────────────────────────────────

export const AddMemberSchema = z.object({
  email: z
    .string()
    .min(1, 'Email is required')
    .email('Enter a valid email address'),
  role_id: z
    .string()
    .min(1, 'Role is required')
    .uuid('Invalid role'),
  employee_id: z
    .string()
    .max(50, 'Employee ID must be 50 characters or fewer')
    .optional()
    .or(z.literal('')),
  job_title: z
    .string()
    .max(100, 'Job title must be 100 characters or fewer')
    .optional()
    .or(z.literal('')),
  department: z
    .string()
    .max(100, 'Department must be 100 characters or fewer')
    .optional()
    .or(z.literal('')),
  work_phone: z
    .string()
    .max(20, 'Phone must be 20 characters or fewer')
    .optional()
    .or(z.literal('')),
  hire_date: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter date as YYYY-MM-DD')
    .optional()
    .or(z.literal('')),
  notes: z
    .string()
    .max(2000, 'Notes must be 2000 characters or fewer')
    .optional()
    .or(z.literal('')),
});

export type AddMemberFormData = z.infer<typeof AddMemberSchema>;

// ── Update Member ─────────────────────────────────────────────────────────────

export const UpdateMemberSchema = z.object({
  role_id: z
    .string()
    .uuid('Invalid role')
    .optional()
    .or(z.literal('')),
  employee_id: z
    .string()
    .max(50, 'Employee ID must be 50 characters or fewer')
    .nullable()
    .optional(),
  job_title: z
    .string()
    .max(100, 'Job title must be 100 characters or fewer')
    .nullable()
    .optional(),
  department: z
    .string()
    .max(100, 'Department must be 100 characters or fewer')
    .nullable()
    .optional(),
  work_phone: z
    .string()
    .max(20, 'Phone must be 20 characters or fewer')
    .nullable()
    .optional(),
  hire_date: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter date as YYYY-MM-DD')
    .nullable()
    .optional()
    .or(z.literal('')),
  notes: z
    .string()
    .max(2000, 'Notes must be 2000 characters or fewer')
    .nullable()
    .optional(),
});

export type UpdateMemberFormData = z.infer<typeof UpdateMemberSchema>;

// ── Suspend Member ────────────────────────────────────────────────────────────

export const SuspendSchema = z.object({
  reason: z
    .string()
    .min(1, 'Reason is required')
    .max(500, 'Reason must be 500 characters or fewer'),
});

export type SuspendFormData = z.infer<typeof SuspendSchema>;

// ── Archive Member ────────────────────────────────────────────────────────────

export const ArchiveSchema = z.object({
  reason: z
    .string()
    .min(1, 'Reason is required')
    .max(500, 'Reason must be 500 characters or fewer'),
});

export type ArchiveFormData = z.infer<typeof ArchiveSchema>;

// ── Create Role (Phase 12) ────────────────────────────────────────────────────

export const CreateRoleSchema = z.object({
  name: z
    .string()
    .min(2, 'Name must be at least 2 characters')
    .max(50, 'Name must be 50 characters or fewer'),
  description: z
    .string()
    .max(500, 'Description must be 500 characters or fewer')
    .optional()
    .or(z.literal('')),
  rank: z
    .number({ invalid_type_error: 'Rank must be a number' })
    .int('Rank must be a whole number')
    .min(1, 'Rank must be at least 1')
    .max(99, 'Rank must be 99 or below'),
  permission_codes: z.array(z.string()),
});

export type CreateRoleFormData = z.infer<typeof CreateRoleSchema>;

// ── Update Role (Phase 12) ────────────────────────────────────────────────────

export const UpdateRoleSchema = z.object({
  name: z
    .string()
    .min(2, 'Name must be at least 2 characters')
    .max(50, 'Name must be 50 characters or fewer')
    .optional(),
  description: z
    .string()
    .max(500, 'Description must be 500 characters or fewer')
    .nullable()
    .optional(),
  rank: z
    .number({ invalid_type_error: 'Rank must be a number' })
    .int('Rank must be a whole number')
    .min(1, 'Rank must be at least 1')
    .max(99, 'Rank must be 99 or below')
    .optional(),
  permission_codes: z.array(z.string()).optional(),
});

export type UpdateRoleFormData = z.infer<typeof UpdateRoleSchema>;

// ── Update Profile (Phase 13) ─────────────────────────────────────────────────

export const UpdateProfileSchema = z.object({
  display_name: z
    .string()
    .min(2, 'Display name must be at least 2 characters')
    .max(100, 'Display name must be 100 characters or fewer')
    .optional(),
  phone: z
    .string()
    .max(20, 'Phone must be 20 characters or fewer')
    .nullable()
    .optional()
    .or(z.literal('')),
});

export type UpdateProfileFormData = z.infer<typeof UpdateProfileSchema>;

// ── Update Preferences (Phase 13) ─────────────────────────────────────────────

export const DATE_FORMATS = ['YYYY-MM-DD', 'DD/MM/YYYY', 'MM/DD/YYYY', 'DD-MM-YYYY'] as const;
export const THEMES = ['light', 'dark', 'system'] as const;

export const UpdatePreferencesSchema = z.object({
  language: z
    .string()
    .min(2, 'Language code must be at least 2 characters')
    .max(10, 'Language code must be 10 characters or fewer'),
  timezone: z
    .string()
    .min(1, 'Timezone is required')
    .max(50, 'Timezone must be 50 characters or fewer'),
  date_format: z.enum(DATE_FORMATS, { message: 'Invalid date format' }),
  number_format: z
    .string()
    .min(1, 'Number format is required')
    .max(20, 'Number format must be 20 characters or fewer'),
  theme: z.enum(THEMES, { message: 'Invalid theme' }),
});

export type UpdatePreferencesFormData = z.infer<typeof UpdatePreferencesSchema>;
