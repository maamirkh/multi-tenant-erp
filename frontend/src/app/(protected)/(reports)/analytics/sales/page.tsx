"use client";

import { DomainReportsShell } from "@/components/reports/DomainReportsShell";
import { sectionForSegment } from "@/components/reports/domains";

/** `/analytics/sales` — domain section shell (Epic 11, T239). */
export default function SalesAnalyticsPage() {
  const section = sectionForSegment("sales");
  if (!section) throw new Error("Unknown reports section: sales");
  return <DomainReportsShell section={section} />;
}
