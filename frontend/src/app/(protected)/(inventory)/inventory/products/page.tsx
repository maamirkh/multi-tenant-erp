/**
 * T075 — Product Master List Page.
 *
 * Displays a paginated, searchable list of products for the current company.
 * Supports filter by status and product type.
 *
 * Spec ref: specs/005-inventory-management/spec.md §14
 */

'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import {
  listProducts,
  type ProductResponse,
  type ProductStatus,
  type ProductType,
} from '@/lib/api/inventory';

const STATUS_LABELS: Record<ProductStatus, string> = {
  DRAFT: 'Draft',
  ACTIVE: 'Active',
  INACTIVE: 'Inactive',
  DISCONTINUED: 'Discontinued',
  ARCHIVED: 'Archived',
};

const STATUS_COLORS: Record<ProductStatus, string> = {
  DRAFT: 'text-muted-foreground',
  ACTIVE: 'text-green-600',
  INACTIVE: 'text-yellow-600',
  DISCONTINUED: 'text-orange-600',
  ARCHIVED: 'text-destructive',
};

const TYPE_LABELS: Record<ProductType, string> = {
  STANDARD: 'Standard',
  VARIANT: 'Variant',
  SERVICE: 'Service',
  BUNDLE: 'Bundle',
  RAW_MATERIAL: 'Raw Material',
};

function ProductRowSkeleton() {
  return (
    <div className="h-14 animate-pulse rounded-lg bg-muted" role="status" />
  );
}

function ProductRow({ product }: { product: ProductResponse }) {
  const statusLabel = STATUS_LABELS[product.status] ?? product.status;
  const statusColor = STATUS_COLORS[product.status] ?? 'text-muted-foreground';
  const typeLabel = TYPE_LABELS[product.product_type] ?? product.product_type;

  return (
    <Link
      href={`/inventory/products/${product.id}`}
      className="flex items-center justify-between rounded-lg border bg-card px-4 py-3 hover:bg-accent/50 transition-colors"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-foreground truncate">{product.name}</span>
          <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
            {product.product_code}
          </span>
        </div>
        <span className="text-xs text-muted-foreground">{typeLabel}</span>
      </div>
      <span className={`ml-4 shrink-0 text-xs font-medium ${statusColor}`}>
        {statusLabel}
      </span>
    </Link>
  );
}

export default function ProductsPage() {
  const companyId =
    typeof window !== 'undefined'
      ? localStorage.getItem('erp_active_company_id') ?? ''
      : '';

  const [products, setProducts] = useState<ProductResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, statusFilter, typeFilter]);

  const load = useCallback(() => {
    if (!companyId) return;
    setIsLoading(true);
    setError(null);
    listProducts(companyId, {
      q: debouncedSearch || undefined,
      status: statusFilter || undefined,
      product_type: typeFilter || undefined,
      page,
      page_size: 20,
    })
      .then((res) => {
        setProducts(res.data.items);
        setTotal(res.data.total);
        setPages(res.data.pages);
      })
      .catch(() => setError('Failed to load products.'))
      .finally(() => setIsLoading(false));
  }, [companyId, debouncedSearch, statusFilter, typeFilter, page]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Products</h1>
          <p className="text-sm text-muted-foreground">
            Manage your product master catalogue.
          </p>
        </div>
        <Link
          href={`/inventory/products/new`}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          New Product
        </Link>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <input
          type="search"
          placeholder="Search products…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-9 flex-1 min-w-[200px] rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">All Statuses</option>
          {Object.entries(STATUS_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">All Types</option>
          {Object.entries(TYPE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* List */}
      <div className="space-y-2">
        {isLoading
          ? Array.from({ length: 5 }).map((_, i) => <ProductRowSkeleton key={i} />)
          : products.map((p) => (
              <ProductRow key={p.id} product={p} />
            ))}
        {!isLoading && products.length === 0 && !error && (
          <div className="rounded-lg border border-dashed px-4 py-10 text-center text-sm text-muted-foreground">
            No products found.{' '}
            <Link
              href={`/inventory/products/new`}
              className="text-primary underline-offset-2 hover:underline"
            >
              Create your first product
            </Link>
          </div>
        )}
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Page {page} of {pages} — {total} products
          </span>
          <div className="flex gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded-md border px-3 py-1 text-xs hover:bg-accent disabled:opacity-40"
            >
              Previous
            </button>
            <button
              disabled={page >= pages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-md border px-3 py-1 text-xs hover:bg-accent disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
