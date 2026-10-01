"use client";

import { DomainReportsHub } from "@/components/reports/DomainReportsHub";
import { sectionForSegment } from "@/components/reports/domains";

/** `/analytics/sales` — Sales report hub (Epic 11, Phase 8). */
export default function SalesAnalyticsPage() {
  const section = sectionForSegment("sales");
  if (!section) throw new Error("Unknown reports section: sales");
  return <DomainReportsHub section={section} />;
}
