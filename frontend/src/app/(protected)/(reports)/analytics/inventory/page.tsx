"use client";

import { DomainReportsShell } from "@/components/reports/DomainReportsShell";
import { sectionForSegment } from "@/components/reports/domains";

/** `/analytics/inventory` — domain section shell (Epic 11, T239). */
export default function InventoryAnalyticsPage() {
  const section = sectionForSegment("inventory");
  if (!section) throw new Error("Unknown reports section: inventory");
  return <DomainReportsShell section={section} />;
}
