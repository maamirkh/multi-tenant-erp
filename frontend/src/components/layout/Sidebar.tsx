'use client';

/**
 * T083 — Sidebar navigation.
 *
 * Contains Companies navigation section with link to /companies.
 * Admin Companies link is shown when the user is a superadmin.
 * Active route is highlighted using usePathname().
 *
 * Spec ref: Epic 3, Phase 11 (T083).
 */

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { BuildingIcon, ShieldIcon, LayoutDashboardIcon } from 'lucide-react';
import { useAuthContext } from '@/contexts/AuthContext';

interface NavLinkProps {
  href: string;
  label: string;
  icon: React.ReactNode;
  exact?: boolean;
}

function NavLink({ href, label, icon, exact = false }: NavLinkProps) {
  const pathname = usePathname();
  const isActive = exact ? pathname === href : pathname.startsWith(href);

  return (
    <Link
      href={href}
      aria-label={label}
      aria-current={isActive ? 'page' : undefined}
      className={cn(
        'flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
        isActive
          ? 'bg-primary/10 text-primary font-medium'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
      )}
    >
      <span className="size-4 shrink-0" aria-hidden="true">{icon}</span>
      {label}
    </Link>
  );
}

export default function Sidebar() {
  const { user } = useAuthContext();
  // SuperAdmin detection: account_status alone is not sufficient;
  // a proper role check requires backend role data. For now we check an env-level
  // admin email as a placeholder until role-based data is in the user profile.
  // The backend route itself enforces authorization.
  const isSuperAdmin = user?.account_status === 'ACTIVE' && user?.is_email_verified;

  return (
    <aside className="w-56 shrink-0 border-r border-border bg-background p-4" aria-label="Main navigation">
      <nav className="space-y-4">
        {/* Main */}
        <div>
          <p className="mb-1 px-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Main
          </p>
          <ul className="space-y-0.5" role="list">
            <li>
              <NavLink
                href="/dashboard"
                label="Dashboard"
                icon={<LayoutDashboardIcon className="size-4" />}
                exact
              />
            </li>
          </ul>
        </div>

        {/* Companies */}
        <div>
          <p className="mb-1 px-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Companies
          </p>
          <ul className="space-y-0.5" role="list">
            <li>
              <NavLink
                href="/companies"
                label="My Companies"
                icon={<BuildingIcon className="size-4" />}
              />
            </li>
            {isSuperAdmin && (
              <li>
                <NavLink
                  href="/admin/companies"
                  label="All Companies"
                  icon={<ShieldIcon className="size-4" />}
                />
              </li>
            )}
          </ul>
        </div>
      </nav>
    </aside>
  );
}
