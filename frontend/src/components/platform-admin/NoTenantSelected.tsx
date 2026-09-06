import Link from 'next/link';

/**
 * Shared empty-state for the four tenant-scoped-only pages
 * (Subscriptions T195, Entitlements T196, Quotas T197, Usage T201) —
 * each contract operation they read/write requires a `companyId` (no
 * tenant-independent list exists, `contracts/platform-admin-v1.yaml`),
 * so they display for the tenant currently held in
 * `PlatformSelectedTenantContext` (T186) and prompt a selection when
 * none exists yet, rather than guessing or defaulting to any tenant.
 */
export function NoTenantSelected(): React.JSX.Element {
  return (
    <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
      <p>No tenant selected.</p>
      <p className="mt-1">
        <Link href="/platform-admin/tenants" className="text-primary hover:underline">
          Choose a tenant
        </Link>{' '}
        to view this section.
      </p>
    </div>
  );
}
