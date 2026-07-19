/**
 * T086 — CompanySettingsTabs.
 *
 * Horizontal tab bar with four settings tabs: Profile, Regional, Branding,
 * Preferences. Uses usePathname() to highlight the active tab. Accessible
 * tab navigation with keyboard support (native link focus management).
 *
 * Spec ref: Epic 3, Phase 12 (T086).
 */

'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';

const TABS = [
  { label: 'Profile', segment: 'profile' },
  { label: 'Regional', segment: 'regional' },
  { label: 'Branding', segment: 'branding' },
  { label: 'Preferences', segment: 'preferences' },
] as const;

interface CompanySettingsTabsProps {
  companyId: string;
}

export function CompanySettingsTabs({ companyId }: CompanySettingsTabsProps) {
  const pathname = usePathname();

  return (
    <nav
      role="tablist"
      aria-label="Company settings sections"
      className="flex border-b border-border"
    >
      {TABS.map(({ label, segment }) => {
        const href = `/companies/${companyId}/settings/${segment}`;
        const isActive = pathname.includes(`/settings/${segment}`);

        return (
          <Link
            key={segment}
            href={href}
            role="tab"
            aria-selected={isActive}
            aria-current={isActive ? 'page' : undefined}
            className={cn(
              'px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
              isActive
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
            )}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
