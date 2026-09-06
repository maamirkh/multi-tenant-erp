/**
 * Inventory module root layout.
 *
 * Wraps all inventory pages with the module-level layout shell.
 * Additional providers (inventory context, breadcrumb context) are
 * added in later phases as sub-domains are implemented.
 *
 * Spec ref: specs/005-inventory-management/spec.md (Epic 5 Phase 0)
 */

import type { ReactNode } from 'react';

interface InventoryLayoutProps {
  children: ReactNode;
}

export default function InventoryLayout({ children }: InventoryLayoutProps) {
  return <>{children}</>;
}
