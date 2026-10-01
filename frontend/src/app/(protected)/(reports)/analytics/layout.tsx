"use client";

import { ReactNode } from "react";

interface ReportsLayoutProps {
  children: ReactNode;
}

/**
 * Reports & Analytics module root layout (Epic 11, T225).
 * Pass-through placeholder, matching every other module (mirrors
 * `(installments)/layout.tsx` exactly) — the shared protected layout
 * (auth guard, QueryClientProvider, AppLayout) already wraps it.
 *
 * Mounted at `/analytics`, not `/reports`: CRM owns `/reports` and
 * Accounting owns `/reports/*` (see `components/reports/domains.ts`).
 *
 * Spec ref: specs/011-reports-analytics/plan.md §23.
 */
export default function ReportsLayout({ children }: ReportsLayoutProps) {
  return <>{children}</>;
}
