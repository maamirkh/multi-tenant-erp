/**
 * T077 — Product Variants Page.
 *
 * Lists all variants for a given product.
 *
 * Spec ref: specs/005-inventory-management/spec.md §14
 */

'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  getProduct,
  listProductVariants,
  type ProductResponse,
  type ProductVariantResponse,
} from '@/lib/api/inventory';

function VariantRow({ variant }: { variant: ProductVariantResponse }) {
  const attrs = variant.attributes
    ? Object.entries(variant.attributes)
        .map(([k, v]) => `${k}: ${v}`)
        .join(', ')
    : '';

  return (
    <div className="flex items-center justify-between rounded-lg border bg-card px-4 py-3">
      <div>
        <span className="font-medium text-foreground">{variant.variant_code}</span>
        {attrs && (
          <p className="text-xs text-muted-foreground mt-0.5">{attrs}</p>
        )}
      </div>
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span>{variant.is_stock_tracked ? 'Stock tracked' : 'Not tracked'}</span>
        <span
          className={
            variant.status === 'ACTIVE' ? 'text-green-600 font-medium' : ''
          }
        >
          {variant.status}
        </span>
      </div>
    </div>
  );
}

export default function VariantsPage() {
  const params = useParams<{ companyId: string; id: string }>();
  const companyId = params?.companyId ?? '';
  const productId = params?.id ?? '';

  const [product, setProduct] = useState<ProductResponse | null>(null);
  const [variants, setVariants] = useState<ProductVariantResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId || !productId) return;
    setIsLoading(true);

    Promise.all([
      getProduct(companyId, productId),
      listProductVariants(companyId, productId),
    ])
      .then(([productRes, variantsRes]) => {
        setProduct(productRes.data);
        setVariants(variantsRes.data);
      })
      .catch(() => setError('Failed to load variants.'))
      .finally(() => setIsLoading(false));
  }, [companyId, productId]);

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1 text-sm text-muted-foreground">
        <Link href={`/companies/${companyId}/inventory/products`} className="hover:text-foreground">
          Products
        </Link>
        <span>/</span>
        {product ? (
          <Link
            href={`/companies/${companyId}/inventory/products/${productId}`}
            className="hover:text-foreground"
          >
            {product.name}
          </Link>
        ) : (
          <span>…</span>
        )}
        <span>/</span>
        <span className="text-foreground">Variants</span>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">
            {product ? `${product.name} — Variants` : 'Variants'}
          </h1>
          <p className="text-sm text-muted-foreground">
            SKU variants for this product (size, colour, etc.).
          </p>
        </div>
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
          ? Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-14 animate-pulse rounded-lg bg-muted" />
            ))
          : variants.map((v) => <VariantRow key={v.id} variant={v} />)}
        {!isLoading && variants.length === 0 && !error && (
          <div className="rounded-lg border border-dashed px-4 py-10 text-center text-sm text-muted-foreground">
            No variants defined for this product.
          </div>
        )}
      </div>
    </div>
  );
}
