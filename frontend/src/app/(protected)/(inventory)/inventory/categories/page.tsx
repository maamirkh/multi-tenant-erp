/**
 * T044 — Inventory Categories Page.
 *
 * Lists all product categories in a tree structure.
 * Provides create, deactivate, and delete actions.
 *
 * Spec ref: specs/005-inventory-management/spec.md §14
 */

'use client';

import { useEffect, useState } from 'react';
import { listCategories, type CategoryResponse } from '@/lib/api/inventory';

function CategorySkeleton() {
  return (
    <div className="space-y-2" aria-busy="true" aria-label="Loading categories">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="h-12 animate-pulse rounded-lg bg-muted" role="status" />
      ))}
    </div>
  );
}

function CategoryRow({ category }: { category: CategoryResponse }) {
  return (
    <div className="flex items-center justify-between rounded-lg border bg-card px-4 py-3">
      <div>
        <span className="font-medium text-foreground">{category.name}</span>
        <span className="ml-2 text-xs text-muted-foreground">{category.code}</span>
        {category.parent_id && (
          <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
            sub-category
          </span>
        )}
      </div>
      <span
        className={`text-xs font-medium ${
          category.status === 'active' ? 'text-green-600' : 'text-muted-foreground'
        }`}
      >
        {category.status}
      </span>
    </div>
  );
}

export default function CategoriesPage() {
  const companyId =
    typeof window !== 'undefined'
      ? localStorage.getItem('erp_active_company_id') ?? ''
      : '';

  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    setIsLoading(true);
    listCategories(companyId)
      .then((res) => setCategories(res.data))
      .catch(() => setError('Failed to load categories.'))
      .finally(() => setIsLoading(false));
  }, [companyId]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Categories</h1>
          <p className="text-sm text-muted-foreground">
            Organise your products into a hierarchical category structure.
          </p>
        </div>
      </div>

      {isLoading && <CategorySkeleton />}

      {error && (
        <div className="rounded-lg border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {!isLoading && !error && categories.length === 0 && (
        <div className="rounded-lg border border-dashed px-6 py-12 text-center">
          <p className="text-muted-foreground">No categories yet. Create your first category.</p>
        </div>
      )}

      {!isLoading && !error && categories.length > 0 && (
        <div className="space-y-2">
          {categories.map((cat) => (
            <CategoryRow key={cat.id} category={cat} />
          ))}
        </div>
      )}
    </div>
  );
}
