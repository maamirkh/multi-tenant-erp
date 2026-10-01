"use client";

import { DomainReportsHub } from "@/components/reports/DomainReportsHub";
import { sectionForSegment } from "@/components/reports/domains";

/** `/analytics/finance` — Finance report hub (Epic 11, Phase 8). */
export default function FinanceAnalyticsPage() {
  const section = sectionForSegment("finance");
  if (!section) throw new Error("Unknown reports section: finance");
  return <DomainReportsHub section={section} />;
}
