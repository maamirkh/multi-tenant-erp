"use client";

import { useState } from "react";

interface ProductImage {
  id: string;
  url: string;
  thumbnail_url: string | null;
  s3_key: string;
  is_primary: boolean;
  sort_order: number;
}

interface ProductImageGalleryProps {
  companyId: string;
  productId: string;
  images: ProductImage[];
  onUpload?: (file: File) => Promise<void>;
  onDelete?: (imageId: string) => Promise<void>;
  onSetPrimary?: (imageId: string) => Promise<void>;
  readonly?: boolean;
}

export function ProductImageGallery({
  companyId: _companyId,
  productId: _productId,
  images,
  onUpload,
  onDelete,
  onSetPrimary,
  readonly = false,
}: ProductImageGalleryProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !onUpload) return;
    setUploading(true);
    setError(null);
    try {
      await onUpload(file);
    } catch {
      setError("Failed to upload image. Please try again.");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const primary = images.find((img) => img.is_primary);
  const rest = images.filter((img) => !img.is_primary);

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-gray-700">Product Images</h3>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Primary Image */}
      {primary && (
        <div className="relative overflow-hidden rounded-lg border border-gray-200">
          <div className="aspect-video bg-gray-50">
            <img
              src={primary.url}
              alt="Primary product image"
              className="h-full w-full object-contain"
              onError={(e) => {
                (e.target as HTMLImageElement).src =
                  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='150'%3E%3Crect width='200' height='150' fill='%23f3f4f6'/%3E%3Ctext x='50%25' y='50%25' text-anchor='middle' dy='.3em' fill='%239ca3af'%3ENo Image%3C/text%3E%3C/svg%3E";
              }}
            />
          </div>
          <span className="absolute left-2 top-2 rounded bg-blue-600 px-2 py-0.5 text-xs font-medium text-white">
            Primary
          </span>
          {!readonly && onDelete && (
            <button
              onClick={() => onDelete(primary.id)}
              className="absolute right-2 top-2 rounded bg-red-600 px-2 py-0.5 text-xs text-white hover:bg-red-700"
            >
              Remove
            </button>
          )}
        </div>
      )}

      {/* Gallery grid */}
      {rest.length > 0 && (
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {rest.map((img) => (
            <div
              key={img.id}
              className="group relative aspect-square overflow-hidden rounded border border-gray-200 bg-gray-50"
            >
              <img
                src={img.url}
                alt="Product image"
                className="h-full w-full object-cover"
                onError={(e) => {
                  (e.target as HTMLImageElement).src =
                    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100'%3E%3Crect width='100' height='100' fill='%23f3f4f6'/%3E%3C/svg%3E";
                }}
              />
              {!readonly && (
                <div className="absolute inset-0 flex items-center justify-center gap-1 bg-black/50 opacity-0 transition-opacity group-hover:opacity-100">
                  {onSetPrimary && (
                    <button
                      onClick={() => onSetPrimary(img.id)}
                      className="rounded bg-blue-600 px-1.5 py-0.5 text-xs text-white hover:bg-blue-700"
                    >
                      Set primary
                    </button>
                  )}
                  {onDelete && (
                    <button
                      onClick={() => onDelete(img.id)}
                      className="rounded bg-red-600 px-1.5 py-0.5 text-xs text-white hover:bg-red-700"
                    >
                      ✕
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {images.length === 0 && (
        <div className="flex items-center justify-center rounded-lg border-2 border-dashed border-gray-300 py-8 text-sm text-gray-500">
          No images uploaded yet
        </div>
      )}

      {/* Upload button */}
      {!readonly && onUpload && (
        <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-blue-600 hover:text-blue-700">
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleFileChange}
            disabled={uploading}
          />
          {uploading ? "Uploading…" : "+ Add Image"}
        </label>
      )}
    </div>
  );
}
