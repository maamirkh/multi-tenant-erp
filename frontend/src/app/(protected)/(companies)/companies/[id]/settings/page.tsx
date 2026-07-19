/**
 * T093 — /companies/[id]/settings — redirect to profile sub-tab.
 *
 * Server component: redirects immediately to the profile settings page.
 * Spec ref: Epic 3, Phase 12 (T093).
 */

import { redirect } from 'next/navigation';

interface Props {
  params: Promise<{ id: string }>;
}

export default async function CompanySettingsRedirectPage({ params }: Props) {
  const { id } = await params;
  redirect(`/companies/${id}/settings/profile`);
}
