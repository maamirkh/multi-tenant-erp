"use client";

import { DomainReportsShell } from "@/components/reports/DomainReportsShell";
import { sectionForSegment } from "@/components/reports/domains";

/** `/analytics/purchase` — domain section shell (Epic 11, T239). */
export default function PurchaseAnalyticsPage() {
  const section = sectionForSegment("purchase");
  if (!section) throw new Error("Unknown reports section: purchase");
  return <DomainReportsShell section={section} />;
}
