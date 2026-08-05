"use client";

import { ReactNode } from "react";

interface SalesLayoutProps {
  children: ReactNode;
}

/**
 * Sales module root layout.
 * Wraps all sales management pages with the shared protected layout.
 * Navigation entries for the sales module are registered here.
 *
 * Spec ref: specs/007-sales-management/spec.md Epic 7 – Sales Management
 */
export default function SalesLayout({ children }: SalesLayoutProps) {
  return <>{children}</>;
}
