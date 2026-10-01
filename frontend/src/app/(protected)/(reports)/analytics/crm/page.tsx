"use client";

import { DomainReportsHub } from "@/components/reports/DomainReportsHub";
import { sectionForSegment } from "@/components/reports/domains";

/** `/analytics/crm` — Crm report hub (Epic 11, Phase 8). */
export default function CrmAnalyticsPage() {
  const section = sectionForSegment("crm");
  if (!section) throw new Error("Unknown reports section: crm");
  return <DomainReportsHub section={section} />;
}
