"use client";

import { DomainReportsHub } from "@/components/reports/DomainReportsHub";
import { sectionForSegment } from "@/components/reports/domains";

/** `/analytics/inventory` — Inventory report hub (Epic 11, Phase 8). */
export default function InventoryAnalyticsPage() {
  const section = sectionForSegment("inventory");
  if (!section) throw new Error("Unknown reports section: inventory");
  return <DomainReportsHub section={section} />;
}
