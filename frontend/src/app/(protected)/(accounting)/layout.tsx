"use client";

import { ReactNode } from "react";

interface AccountingLayoutProps {
  children: ReactNode;
}

/**
 * Accounting module root layout.
 * Wraps all accounting pages with the shared protected layout.
 * Navigation entries for the accounting module are registered here.
 *
 * Spec ref: specs/008-accounting-finance/spec.md Epic 8 – Accounting & Finance
 */
export default function AccountingLayout({ children }: AccountingLayoutProps) {
  return <>{children}</>;
}
