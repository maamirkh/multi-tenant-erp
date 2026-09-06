/**
 * T076 — Product Detail / Edit Page.
 *
 * Displays full product details and provides inline editing.
 * Also surfaces lifecycle status actions (activate, deactivate, etc.).
 *
 * Spec ref: specs/005-inventory-management/spec.md §14, §17
 */

'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  getProduct,
  updateProduct,
  transitionProductStatus,
  deleteProduct,
  type ProductResponse,
  type ProductStatus,
} from '@/lib/api/inventory';

const STATUS_LABELS: Record<ProductStatus, string> = {
  DRAFT: 'Draft',
  ACTIVE: 'Active',
  INACTIVE: 'Inactive',
  DISCONTINUED: 'Discontinued',
  ARCHIVED: 'Archived',
};

const STATUS_COLORS: Record<ProductStatus, string> = {
  DRAFT: 'bg-muted text-muted-foreground',
  ACTIVE: 'bg-green-100 text-green-700',
  INACTIVE: 'bg-yellow-100 text-yellow-700',
  DISCONTINUED: 'bg-orange-100 text-orange-700',
  ARCHIVED: 'bg-red-100 text-red-700',
};

const LIFECYCLE_ACTIONS: Partial<Record<ProductStatus, Array<{ action: 'activate' | 'deactivate' | 'discontinue' | 'archive'; label: string }>>> = {
  DRAFT: [{ action: 'activate', label: 'Activate' }],
  ACTIVE: [
    { action: 'deactivate', label: 'Deactivate' },
    { action: 'discontinue', label: 'Discontinue' },
  ],
  INACTIVE: [
    { action: 'activate', label: 'Reactivate' },
    { action: 'archive', label: 'Archive' },
  ],
  DISCONTINUED: [{ action: 'archive', label: 'Archive' }],
};

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  if (value === null || value === undefined || value === '') return null;
  return (
    <div className="flex gap-4 py-2 border-b last:border-b-0">
      <span className="w-40 shrink-0 text-sm text-muted-foreground">{label}</span>
      <span className="text-sm text-foreground">{value}</span>
    </div>
  );
}

export default function ProductDetailPage() {
  const params = useParams<{ id: string }>();
  const companyId =
    typeof window !== 'undefined'
      ? localStorage.getItem('erp_active_company_id') ?? ''
      : '';
  const productId = params?.id ?? '';
  const router = useRouter();

  const [product, setProduct] = useState<ProductResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!companyId || !productId || productId === 'new') return;
    setIsLoading(true);
    getProduct(companyId, productId)
      .then((res) => {
        setProduct(res.data);
        setEditName(res.data.name);
        setEditDescription(res.data.description ?? '');
      })
      .catch(() => setError('Product not found.'))
      .finally(() => setIsLoading(false));
  }, [companyId, productId]);

  async function handleSave() {
    if (!product) return;
    setIsSaving(true);
    setActionError(null);
    try {
      const payload: { name: string; description?: string | undefined } = { name: editName };
      if (editDescription) payload.description = editDescription;
      const res = await updateProduct(companyId, product.id, payload);
      setProduct(res.data);
      setIsEditing(false);
    } catch {
      setActionError('Failed to save changes.');
    } finally {
      setIsSaving(false);
    }
  }

  async function handleAction(action: 'activate' | 'deactivate' | 'discontinue' | 'archive') {
    if (!product) return;
    setActionError(null);
    try {
      const res = await transitionProductStatus(companyId, product.id, action);
      setProduct(res.data);
    } catch {
      setActionError(`Failed to ${action} product.`);
    }
  }

  async function handleDelete() {
    if (!product) return;
    if (!window.confirm(`Delete product "${product.name}"? This cannot be undone.`)) return;
    try {
      await deleteProduct(companyId, product.id);
      router.push(`/inventory/products`);
    } catch {
      setActionError('Failed to delete product.');
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-10 animate-pulse rounded bg-muted" />
        ))}
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="rounded-lg border border-destructive/20 bg-destructive/5 px-4 py-6 text-center text-sm text-destructive">
        {error ?? 'Product not found.'}
      </div>
    );
  }

  const lifecycleActions = LIFECYCLE_ACTIONS[product.status] ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <Link
              href={`/inventory/products`}
              className="hover:text-foreground"
            >
              Products
            </Link>
            <span>/</span>
            <span className="text-foreground">{product.product_code}</span>
          </div>
          {isEditing ? (
            <input
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              className="text-xl font-semibold w-full rounded border bg-background px-2 py-1 focus:outline-none focus:ring-2 focus:ring-ring"
            />
          ) : (
            <h1 className="text-xl font-semibold text-foreground">{product.name}</h1>
          )}
          <div className="mt-1 flex items-center gap-2">
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[product.status]}`}
            >
              {STATUS_LABELS[product.status]}
            </span>
            <span className="text-xs text-muted-foreground">{product.product_type}</span>
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          {isEditing ? (
            <>
              <button
                onClick={() => setIsEditing(false)}
                className="rounded-md border px-3 py-1.5 text-sm hover:bg-accent"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
              >
                {isSaving ? 'Saving…' : 'Save'}
              </button>
            </>
          ) : (
            <button
              onClick={() => setIsEditing(true)}
              className="rounded-md border px-3 py-1.5 text-sm hover:bg-accent"
            >
              Edit
            </button>
          )}
        </div>
      </div>

      {/* Action error */}
      {actionError && (
        <div className="rounded-lg border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {actionError}
        </div>
      )}

      {/* Details */}
      <div className="rounded-lg border bg-card px-4 py-2">
        <DetailRow label="Product Code" value={product.product_code} />
        <DetailRow label="Product Type" value={product.product_type} />
        {isEditing ? (
          <div className="flex gap-4 py-2 border-b">
            <span className="w-40 shrink-0 text-sm text-muted-foreground">Description</span>
            <textarea
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              rows={3}
              className="flex-1 rounded border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        ) : (
          <DetailRow label="Description" value={product.description} />
        )}
        <DetailRow label="Short Description" value={product.short_description} />
        <DetailRow label="HS Code" value={product.hs_code} />
        <DetailRow label="Country of Origin" value={product.country_of_origin} />
        <DetailRow label="Lead Time (days)" value={product.lead_time_days} />
        <DetailRow label="Reorder Point" value={product.reorder_point} />
        <DetailRow label="Cost Price" value={product.cost_price} />
        <DetailRow label="Serialised" value={product.is_serialized ? 'Yes' : 'No'} />
        <DetailRow label="Batch Tracked" value={product.is_batch_tracked ? 'Yes' : 'No'} />
      </div>

      {/* Variants link */}
      <Link
        href={`/inventory/products/${product.id}/variants`}
        className="flex items-center justify-between rounded-lg border bg-card px-4 py-3 hover:bg-accent/50 transition-colors"
      >
        <span className="text-sm font-medium">Variants</span>
        <span className="text-xs text-muted-foreground">View →</span>
      </Link>

      {/* Lifecycle actions */}
      {lifecycleActions.length > 0 && (
        <div className="rounded-lg border bg-card px-4 py-4 space-y-3">
          <h2 className="text-sm font-medium text-foreground">Lifecycle Actions</h2>
          <div className="flex flex-wrap gap-2">
            {lifecycleActions.map(({ action, label }) => (
              <button
                key={action}
                onClick={() => handleAction(action)}
                className="rounded-md border px-3 py-1.5 text-sm hover:bg-accent"
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Danger zone */}
      {product.status !== 'ARCHIVED' && (
        <div className="rounded-lg border border-destructive/20 bg-destructive/5 px-4 py-4 space-y-2">
          <h2 className="text-sm font-medium text-destructive">Danger Zone</h2>
          <p className="text-xs text-muted-foreground">
            Deleting a product is permanent and cannot be undone.
          </p>
          <button
            onClick={handleDelete}
            className="rounded-md border border-destructive/50 px-3 py-1.5 text-sm text-destructive hover:bg-destructive/10"
          >
            Delete Product
          </button>
        </div>
      )}
    </div>
  );
}
