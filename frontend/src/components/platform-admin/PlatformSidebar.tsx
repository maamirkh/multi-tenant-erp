'use client';

/**
 * T189 — Platform navigation, permission-aware.
 *
 * Unlike the tenant `Sidebar`'s acknowledged placeholder check
 * (`components/layout/Sidebar.tsx`), every entry here is hidden/shown
 * based on a real server response via `usePlatformNavPermissions` (see
 * that hook's docstring for exactly how, and its documented limitation
 * for the four tenant-scoped-only sections). This is UX only — the
 * server remains the sole authorization boundary for every route.
 */

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboardIcon,
  BuildingIcon,
  PackageIcon,
  CreditCardIcon,
  ShieldCheckIcon,
  GaugeIcon,
  UsersIcon,
  KeyIcon,
  ScrollTextIcon,
  BarChart3Icon,
  LifeBuoyIcon,
  HeartPulseIcon,
} from 'lucide-react';
import {
  usePlatformNavPermissions,
  type PlatformNavSection,
} from '@/hooks/platform-admin/usePlatformNavPermissions';

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
  /** Section key probed by `usePlatformNavPermissions`, or `null` for
   * the four tenant-scoped-only sections that are always shown. */
  section: PlatformNavSection | null;
}

const NAV_ITEMS: NavItem[] = [
  { href: '/platform-admin/dashboard', label: 'Dashboard', icon: <LayoutDashboardIcon className="size-4" />, section: 'dashboard' },
  { href: '/platform-admin/tenants', label: 'Tenants', icon: <BuildingIcon className="size-4" />, section: 'tenants' },
  { href: '/platform-admin/plans', label: 'Plans', icon: <PackageIcon className="size-4" />, section: 'plans' },
  { href: '/platform-admin/subscriptions', label: 'Subscriptions', icon: <CreditCardIcon className="size-4" />, section: null },
  { href: '/platform-admin/entitlements', label: 'Entitlements', icon: <ShieldCheckIcon className="size-4" />, section: null },
  { href: '/platform-admin/quotas', label: 'Quotas', icon: <GaugeIcon className="size-4" />, section: null },
  { href: '/platform-admin/administrators', label: 'Administrators', icon: <UsersIcon className="size-4" />, section: 'administrators' },
  { href: '/platform-admin/roles', label: 'Roles', icon: <KeyIcon className="size-4" />, section: 'roles' },
  { href: '/platform-admin/audit', label: 'Audit', icon: <ScrollTextIcon className="size-4" />, section: 'audit' },
  { href: '/platform-admin/usage', label: 'Usage', icon: <BarChart3Icon className="size-4" />, section: null },
  { href: '/platform-admin/support-access', label: 'Support Access', icon: <LifeBuoyIcon className="size-4" />, section: 'support-access' },
  { href: '/platform-admin/health', label: 'Health', icon: <HeartPulseIcon className="size-4" />, section: 'health' },
];

function NavLink({ item }: { item: NavItem }): React.JSX.Element {
  const pathname = usePathname();
  const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);

  return (
    <Link
      href={item.href}
      aria-label={item.label}
      aria-current={isActive ? 'page' : undefined}
      className={cn(
        'flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
        isActive
          ? 'bg-primary/10 font-medium text-primary'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
      )}
    >
      <span className="size-4 shrink-0" aria-hidden="true">
        {item.icon}
      </span>
      {item.label}
    </Link>
  );
}

export function PlatformSidebar(): React.JSX.Element {
  const { isLoading, isAllowed } = usePlatformNavPermissions();

  const visibleItems = NAV_ITEMS.filter(
    (item) => isLoading || item.section === null || isAllowed(item.section)
  );

  return (
    <aside
      className="w-56 shrink-0 border-r border-border bg-background p-4"
      aria-label="Platform navigation"
    >
      <nav className="space-y-4">
        <div>
          <p className="mb-1 px-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Platform
          </p>
          <ul className="space-y-0.5" role="list">
            {visibleItems.map((item) => (
              <li key={item.href}>
                <NavLink item={item} />
              </li>
            ))}
          </ul>
        </div>
      </nav>
    </aside>
  );
}

export default PlatformSidebar;
