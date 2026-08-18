"use client";

import { ReactNode } from "react";

interface CrmLayoutProps {
  children: ReactNode;
}

/**
 * CRM module root layout.
 * Wraps all CRM pages with the shared protected layout.
 *
 * Spec ref: specs/009-crm/spec.md Epic 9 – CRM
 */
export default function CrmLayout({ children }: CrmLayoutProps) {
  return <>{children}</>;
}
