"use client";

import { DomainReportsShell } from "@/components/reports/DomainReportsShell";
import { sectionForSegment } from "@/components/reports/domains";

/** `/analytics/installments` — domain section shell (Epic 11, T239). */
export default function InstallmentsAnalyticsPage() {
  const section = sectionForSegment("installments");
  if (!section) throw new Error("Unknown reports section: installments");
  return <DomainReportsShell section={section} />;
}
