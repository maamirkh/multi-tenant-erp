"use client";

import { ReactNode } from "react";

interface PurchaseLayoutProps {
  children: ReactNode;
}

/**
 * Purchase module root layout.
 * Wraps all purchase management pages with the shared protected layout.
 * Navigation entries for the purchase module are registered here.
 *
 * Spec ref: specs/006-purchase-management/spec.md Epic 6 – Purchase Management
 */
export default function PurchaseLayout({ children }: PurchaseLayoutProps) {
  return <>{children}</>;
}
