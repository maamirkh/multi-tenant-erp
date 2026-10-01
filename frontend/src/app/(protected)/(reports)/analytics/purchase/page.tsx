"use client";

import { DomainReportsHub } from "@/components/reports/DomainReportsHub";
import { sectionForSegment } from "@/components/reports/domains";

/** `/analytics/purchase` — Purchase report hub (Epic 11, Phase 8). */
export default function PurchaseAnalyticsPage() {
  const section = sectionForSegment("purchase");
  if (!section) throw new Error("Unknown reports section: purchase");
  return <DomainReportsHub section={section} />;
}
