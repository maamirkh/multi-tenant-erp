/**
 * Zod validation schemas for the Installments module.
 *
 * Mirrors backend Pydantic schemas:
 *   backend/modules/installments/schemas/contract.py
 *   backend/modules/installments/schemas/schedule.py
 *   backend/modules/installments/schemas/collection.py
 *   backend/modules/installments/schemas/lifecycle.py
 *
 * Spec ref: specs/010-installments/tasks.md T215.
 */

import { z } from 'zod';

const decimalString = z
  .string()
  .min(1, 'Required')
  .regex(/^\d+(\.\d+)?$/, 'Enter a valid amount');

// ── Quote / Draft Contract ───────────────────────────────────────────────────

export const InstallmentQuoteRequestSchema = z.object({
  sales_invoice_id: z.string().uuid('Select an invoice'),
  down_payment_amount: decimalString,
  installment_count: z.coerce.number().int().gt(0, 'Must be at least 1'),
  frequency: z.string().min(1, 'Frequency is required'),
  first_due_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter date as YYYY-MM-DD'),
  markup_amount: decimalString.optional().or(z.literal('')),
  branch_id: z.string().uuid().optional().or(z.literal('')),
});

export type InstallmentQuoteRequestFormData = z.infer<typeof InstallmentQuoteRequestSchema>;

export const InstallmentContractCreateSchema = z.object({
  sales_invoice_id: z.string().uuid('Select an invoice'),
  down_payment_amount: decimalString,
  installment_count: z.coerce.number().int().gt(0, 'Must be at least 1'),
  frequency: z.string().min(1, 'Frequency is required'),
  first_due_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter date as YYYY-MM-DD'),
  maturity_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter date as YYYY-MM-DD'),
  markup_amount: decimalString.optional().or(z.literal('')),
  plan_template_id: z.string().uuid().optional().or(z.literal('')),
  branch_id: z.string().uuid().optional().or(z.literal('')),
  contract_date: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter date as YYYY-MM-DD')
    .optional()
    .or(z.literal('')),
});

export type InstallmentContractCreateFormData = z.infer<typeof InstallmentContractCreateSchema>;

// ── Collection ────────────────────────────────────────────────────────────────

export const InstallmentCollectionCreateSchema = z
  .object({
    amount: decimalString,
    payment_method: z.string().min(1, 'Payment method is required'),
    bank_account_id: z.string().uuid().optional().or(z.literal('')),
    cash_account_id: z.string().uuid().optional().or(z.literal('')),
  })
  .refine((data) => Boolean(data.bank_account_id) !== Boolean(data.cash_account_id), {
    message: 'Select exactly one of bank account or cash account',
    path: ['bank_account_id'],
  });

export type InstallmentCollectionCreateFormData = z.infer<
  typeof InstallmentCollectionCreateSchema
>;

export const InstallmentCollectionReverseSchema = z.object({
  reason: z.string().min(1, 'Reason is required'),
});

export type InstallmentCollectionReverseFormData = z.infer<
  typeof InstallmentCollectionReverseSchema
>;

// ── Reschedule ────────────────────────────────────────────────────────────────

export const InstallmentRescheduleSchema = z.object({
  first_due_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter date as YYYY-MM-DD'),
  reason: z.string().min(1, 'Reason is required'),
  requested_by: z.string().uuid('Select the requester'),
});

export type InstallmentRescheduleFormData = z.infer<typeof InstallmentRescheduleSchema>;

// ── Plan Template ─────────────────────────────────────────────────────────────

export const InstallmentPlanTemplateSchema = z.object({
  name: z.string().min(1, 'Name is required').max(150, 'Max 150 characters'),
  description: z.string().max(2000).optional().or(z.literal('')),
  frequency: z.string().min(1, 'Frequency is required'),
  installment_count: z.coerce.number().int().gt(0, 'Must be at least 1'),
  down_payment_type: z.enum(['FIXED', 'PERCENTAGE']),
  down_payment_value: decimalString,
  grace_period_days: z.coerce.number().int().min(0).optional(),
  requires_approval: z.boolean().optional(),
});

export type InstallmentPlanTemplateFormData = z.infer<typeof InstallmentPlanTemplateSchema>;

// ── Configuration ─────────────────────────────────────────────────────────────

export const InstallmentConfigurationSchema = z.object({
  branch_id: z.string().uuid().optional().or(z.literal('')),
  allowed_frequencies: z.array(z.string()).min(1, 'Select at least one frequency'),
  min_term: z.coerce.number().int().gt(0, 'Must be at least 1'),
  max_term: z.coerce.number().int().gt(0, 'Must be at least 1'),
  min_down_payment_pct: decimalString.optional().or(z.literal('')),
  min_down_payment_amount: decimalString.optional().or(z.literal('')),
  max_financed_amount: decimalString.optional().or(z.literal('')),
  rounding_policy: z.string().min(1),
  grace_period_days: z.coerce.number().int().min(0),
  approval_threshold_amount: decimalString.optional().or(z.literal('')),
  backdating_allowed: z.boolean(),
  backdating_max_days: z.coerce.number().int().min(0).optional(),
  writeoff_requires_permission: z.boolean(),
  cure_enabled: z.boolean(),
});

export type InstallmentConfigurationFormData = z.infer<typeof InstallmentConfigurationSchema>;
