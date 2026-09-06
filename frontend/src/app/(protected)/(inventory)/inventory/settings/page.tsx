/**
 * T045 — Inventory Settings Page.
 *
 * Provides management for brands and units of measure (UOM).
 * Both are scoped per company (tenant isolation).
 *
 * Spec ref: specs/005-inventory-management/spec.md §14
 */

'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { listBrands, listUOMs, type BrandResponse, type UOMResponse } from '@/lib/api/inventory';

function TableSkeleton({ cols }: { cols: number }) {
  return (
    <div className="space-y-2" aria-busy="true">
      {Array.from({ length: 3 }).map((_, i) => (
        <div
          key={i}
          className="grid h-10 animate-pulse gap-4 rounded bg-muted"
          style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
          role="status"
        />
      ))}
    </div>
  );
}

function BrandsSection({ companyId }: { companyId: string }) {
  const [brands, setBrands] = useState<BrandResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    listBrands(companyId)
      .then((res) => setBrands(res.data.items))
      .catch(() => setError('Failed to load brands.'))
      .finally(() => setIsLoading(false));
  }, [companyId]);

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-base font-semibold text-foreground">Brands</h2>
        <p className="text-sm text-muted-foreground">Manage product brands for your catalogue.</p>
      </div>

      {isLoading && <TableSkeleton cols={3} />}
      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}
      {!isLoading && !error && brands.length === 0 && (
        <p className="text-sm text-muted-foreground">No brands configured.</p>
      )}
      {!isLoading && !error && brands.length > 0 && (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Code</th>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Name</th>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {brands.map((brand) => (
                <tr key={brand.id} className="bg-card">
                  <td className="px-4 py-2 font-mono text-xs">{brand.code}</td>
                  <td className="px-4 py-2">{brand.name}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`text-xs font-medium ${
                        brand.status === 'active' ? 'text-green-600' : 'text-muted-foreground'
                      }`}
                    >
                      {brand.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function UOMSection({ companyId }: { companyId: string }) {
  const [uoms, setUoms] = useState<UOMResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    listUOMs(companyId)
      .then((res) => setUoms(res.data.items))
      .catch(() => setError('Failed to load units of measure.'))
      .finally(() => setIsLoading(false));
  }, [companyId]);

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-base font-semibold text-foreground">Units of Measure</h2>
        <p className="text-sm text-muted-foreground">
          Define measurement units used across products and stock operations.
        </p>
      </div>

      {isLoading && <TableSkeleton cols={4} />}
      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}
      {!isLoading && !error && uoms.length === 0 && (
        <p className="text-sm text-muted-foreground">No units of measure configured.</p>
      )}
      {!isLoading && !error && uoms.length > 0 && (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Code</th>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Name</th>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Type</th>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Symbol</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {uoms.map((uom) => (
                <tr key={uom.id} className="bg-card">
                  <td className="px-4 py-2 font-mono text-xs">{uom.code}</td>
                  <td className="px-4 py-2">{uom.name}</td>
                  <td className="px-4 py-2 text-xs text-muted-foreground">{uom.uom_type}</td>
                  <td className="px-4 py-2 text-xs">{uom.symbol ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default function InventorySettingsPage() {
  const params = useParams<{ companyId: string }>();
  const companyId = params?.companyId ?? '';

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Inventory Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage master data used across inventory: brands, units of measure, and more.
        </p>
      </div>

      <BrandsSection companyId={companyId} />
      <UOMSection companyId={companyId} />
    </div>
  );
}
