"use client";

import { DomainReportsHub } from "@/components/reports/DomainReportsHub";
import { sectionForSegment } from "@/components/reports/domains";

/** `/analytics/installments` — Installments report hub (Epic 11, Phase 8). */
export default function InstallmentsAnalyticsPage() {
  const section = sectionForSegment("installments");
  if (!section) throw new Error("Unknown reports section: installments");
  return <DomainReportsHub section={section} />;
}
