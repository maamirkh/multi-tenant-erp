/**
 * Installments React Query key factory.
 *
 * Every tenant-scoped key includes the active `companyId` as its second
 * element — not merely the resource id — even for keys where the resource
 * id (e.g. a contract UUID) is already globally unique and could not by
 * itself collide across tenants. Two reasons this still matters:
 *
 *   1. Consistency with `useContracts`'s list key, where a UUID isn't
 *      available to scope by (filters like `{page, page_size}` repeat
 *      across companies) — that key's tenant-scoping fix is what this
 *      factory generalizes.
 *   2. Defense in depth: tenant context is part of this data's
 *      authorization/caching semantics, not just its identity. A future
 *      change to how a key is constructed (e.g. adding a second,
 *      non-UUID filter dimension to a currently ID-only query) should
 *      not have to remember to retrofit tenant scoping — it's already
 *      there.
 *
 * `CompanyProvider` doesn't wrap the Installments route group (see
 * `contexts/CompanyContext.tsx`), so `companyId` here always comes from
 * `getCompanyId()` (`components/installments/apiErrors.ts`), read fresh
 * by each hook — never cached across a company switch.
 */
export const installmentsKeys = {
  contracts: (companyId: string, filters: { page: number; page_size: number }) =>
    ['contracts', companyId, filters] as const,
  contract: (companyId: string, contractId: string) =>
    ['contract', companyId, contractId] as const,
  schedule: (companyId: string, contractId: string) =>
    ['schedule', companyId, contractId] as const,
  collections: (companyId: string, contractId: string) =>
    ['collections', companyId, contractId] as const,
  delinquency: (companyId: string, contractId: string) =>
    ['delinquency', companyId, contractId] as const,
  auditHistory: (companyId: string, contractId: string) =>
    ['auditHistory', companyId, contractId] as const,
};
