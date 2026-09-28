"use client";

import { DomainReportsShell } from "@/components/reports/DomainReportsShell";
import { sectionForSegment } from "@/components/reports/domains";

/** `/analytics/finance` — domain section shell (Epic 11, T239). */
export default function FinanceAnalyticsPage() {
  const section = sectionForSegment("finance");
  if (!section) throw new Error("Unknown reports section: finance");
  return <DomainReportsShell section={section} />;
}
