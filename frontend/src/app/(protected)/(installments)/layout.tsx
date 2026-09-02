"use client";

import { ReactNode } from "react";

interface InstallmentsLayoutProps {
  children: ReactNode;
}

/**
 * Installments module root layout.
 * Wraps all Installments pages with the shared protected layout.
 * Pass-through placeholder, matching every other module (mirrors
 * `(crm)/layout.tsx` exactly).
 *
 * Spec ref: specs/010-installments/spec.md.
 */
export default function InstallmentsLayout({ children }: InstallmentsLayoutProps) {
  return <>{children}</>;
}
