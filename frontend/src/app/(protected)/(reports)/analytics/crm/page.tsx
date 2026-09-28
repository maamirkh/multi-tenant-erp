"use client";

import { DomainReportsShell } from "@/components/reports/DomainReportsShell";
import { sectionForSegment } from "@/components/reports/domains";

/** `/analytics/crm` — domain section shell (Epic 11, T239). */
export default function CrmAnalyticsPage() {
  const section = sectionForSegment("crm");
  if (!section) throw new Error("Unknown reports section: crm");
  return <DomainReportsShell section={section} />;
}
