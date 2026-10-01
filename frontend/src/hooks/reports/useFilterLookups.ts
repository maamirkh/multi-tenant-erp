/**
 * useFilterLookups (Phase 8) — option lists for the few report filters that
 * take an internal ID (fiscal period, bank/cash account, cost center),
 * loaded from Accounting's own existing read endpoints. Only lookups a
 * report actually declares are fetched. If a lookup can't load (e.g. the
 * user lacks the Accounting permission behind it), the field falls back to
 * a plain text input, so the report stays usable.
 */

import { useQuery } from '@tanstack/react-query';
import {
  getBankAccounts,
  getCashAccounts,
  getCostCenters,
  getFiscalPeriods,
  getFiscalYears,
} from '@/lib/api/accounting';
import type { FilterFieldOption } from '@/components/reports/FilterBar';
import type { FilterLookup } from '@/components/reports/reportConfigs';
import { useActiveCompanyId } from './useActiveCompanyId';

export type LookupOptions = Partial<Record<FilterLookup, FilterFieldOption[]>>;

async function loadFiscalPeriods(companyId: string): Promise<FilterFieldOption[]> {
  const years = (await getFiscalYears(companyId)).data;
  const periods = await Promise.all(
    years.map(async (year) => ({ year, periods: (await getFiscalPeriods(companyId, year.id)).data }))
  );
  return periods.flatMap(({ year, periods: list }) =>
    list.map((p) => ({ value: p.id, label: `${year.fiscal_year_name} · ${p.period_name}` }))
  );
}

async function loadBankOrCashAccounts(companyId: string): Promise<FilterFieldOption[]> {
  const [banks, cash] = await Promise.all([getBankAccounts(companyId), getCashAccounts(companyId)]);
  return [
    ...banks.data.map((b) => ({ value: b.id, label: `Bank · ${b.bank_name} ${b.account_number}` })),
    ...cash.data.map((c) => ({ value: c.id, label: `Cash · ${c.account_name}` })),
  ];
}

async function loadCostCenters(companyId: string): Promise<FilterFieldOption[]> {
  const centers = (await getCostCenters(companyId)).data;
  return centers.map((c) => ({ value: c.id, label: `${c.center_code} · ${c.center_name}` }));
}

const LOADERS: Record<FilterLookup, (companyId: string) => Promise<FilterFieldOption[]>> = {
  fiscal_period: loadFiscalPeriods,
  bank_or_cash_account: loadBankOrCashAccounts,
  cost_center: loadCostCenters,
};

function useLookup(lookup: FilterLookup, companyId: string, wanted: boolean) {
  return useQuery<FilterFieldOption[]>({
    queryKey: ['reports', companyId, 'lookup', lookup],
    queryFn: () => LOADERS[lookup](companyId),
    enabled: wanted && companyId !== '',
    staleTime: 5 * 60_000,
    retry: false,
  });
}

export function useFilterLookups(lookups: readonly FilterLookup[]): LookupOptions {
  const companyId = useActiveCompanyId();
  const fiscal = useLookup('fiscal_period', companyId, lookups.includes('fiscal_period'));
  const accounts = useLookup('bank_or_cash_account', companyId, lookups.includes('bank_or_cash_account'));
  const centers = useLookup('cost_center', companyId, lookups.includes('cost_center'));
  const options: LookupOptions = {};
  if (fiscal.data) options.fiscal_period = fiscal.data;
  if (accounts.data) options.bank_or_cash_account = accounts.data;
  if (centers.data) options.cost_center = centers.data;
  return options;
}
