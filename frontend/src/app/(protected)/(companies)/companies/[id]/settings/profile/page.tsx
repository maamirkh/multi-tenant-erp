/**
 * T093 — /companies/[id]/settings/profile.
 *
 * Company profile settings page.
 * Renders CompanySettingsTabs + CompanyProfileForm + address list
 * with CompanyAddressForm in a dialog.
 *
 * Spec ref: Epic 3, Phase 12 (T093).
 */

'use client';

import { use, useState } from 'react';
import { useCompany } from '@/hooks/companies/useCompany';
import {
  useCompanyAddresses,
  useCreateAddress,
  useUpdateAddress,
  useDeleteAddress,
} from '@/hooks/companies/useCompanyAddresses';
import { CompanySettingsTabs } from '@/components/companies/CompanySettingsTabs';
import { CompanyProfileForm } from '@/components/companies/CompanyProfileForm';
import { CompanyAddressForm } from '@/components/companies/CompanyAddressForm';
import type { CompanyAddress, CreateAddressInput } from '@/types/companies';

interface Props {
  params: Promise<{ id: string }>;
}

export default function CompanyProfileSettingsPage({ params }: Props) {
  const { id } = use(params);
  const { data: company, isLoading, isError } = useCompany(id);
  const { data: addressesResult } = useCompanyAddresses(id);

  // Dialog state
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [editingAddress, setEditingAddress] = useState<CompanyAddress | null>(null);

  const createAddress = useCreateAddress(id);
  const updateAddress = useUpdateAddress(id);
  const deleteAddress = useDeleteAddress(id);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <CompanySettingsTabs companyId={id} />
        <div className="mt-6 space-y-3 animate-pulse">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-8 rounded bg-muted" />
          ))}
        </div>
      </div>
    );
  }

  if (isError || !company) {
    return (
      <div className="space-y-4">
        <CompanySettingsTabs companyId={id} />
        <p role="alert" className="mt-6 text-sm text-destructive">
          Failed to load company profile.
        </p>
      </div>
    );
  }

  const addresses = addressesResult ?? [];

  function handleAddAddress(data: CreateAddressInput) {
    createAddress.mutate(data, {
      onSuccess: () => setShowAddDialog(false),
    });
  }

  function handleEditAddress(data: CreateAddressInput) {
    if (!editingAddress) return;
    updateAddress.mutate(
      { addressId: editingAddress.id, data },
      { onSuccess: () => setEditingAddress(null) }
    );
  }

  return (
    <div className="space-y-6">
      <CompanySettingsTabs companyId={id} />

      <div className="mt-6 space-y-8">
        {/* Profile form */}
        <section aria-labelledby="profile-heading">
          <h2 id="profile-heading" className="mb-4 text-base font-semibold text-foreground">
            Company Profile
          </h2>
          <CompanyProfileForm company={company} />
        </section>

        {/* Addresses */}
        <section aria-labelledby="addresses-heading">
          <div className="mb-4 flex items-center justify-between">
            <h2 id="addresses-heading" className="text-base font-semibold text-foreground">
              Addresses
            </h2>
            <button
              type="button"
              onClick={() => setShowAddDialog(true)}
              className="rounded-lg border border-input px-3 py-1.5 text-xs font-medium hover:bg-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Add Address
            </button>
          </div>

          {addresses.length === 0 ? (
            <p className="text-sm text-muted-foreground">No addresses on file.</p>
          ) : (
            <ul className="space-y-3" aria-label="Company addresses">
              {addresses.map((addr) => (
                <li
                  key={addr.id}
                  className="rounded-lg border border-border p-4 text-sm"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-0.5">
                      <p className="font-medium capitalize">{addr.address_type} address</p>
                      <p className="text-muted-foreground">{addr.street_line_1}</p>
                      {addr.street_line_2 && (
                        <p className="text-muted-foreground">{addr.street_line_2}</p>
                      )}
                      <p className="text-muted-foreground">
                        {[addr.city, addr.state_province, addr.postal_code, addr.country]
                          .filter(Boolean)
                          .join(', ')}
                      </p>
                      {addr.is_primary && (
                        <span className="inline-block text-xs font-medium text-primary">
                          Primary
                        </span>
                      )}
                    </div>
                    <div className="flex gap-2 shrink-0">
                      <button
                        type="button"
                        onClick={() => setEditingAddress(addr)}
                        className="text-xs text-muted-foreground hover:text-foreground underline-offset-2 hover:underline"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteAddress.mutate(addr.id)}
                        disabled={deleteAddress.isPending}
                        className="text-xs text-destructive hover:underline underline-offset-2"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}

          {/* Add Address Dialog */}
          {showAddDialog && (
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="add-address-dialog-title"
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
            >
              <div className="w-full max-w-lg rounded-xl bg-background p-6 shadow-lg">
                <h3 id="add-address-dialog-title" className="mb-4 text-base font-semibold">
                  Add Address
                </h3>
                <CompanyAddressForm
                  onSubmit={handleAddAddress}
                  onCancel={() => setShowAddDialog(false)}
                  isPending={createAddress.isPending}
                  error={createAddress.isError ? (createAddress.error?.message ?? 'Failed to add address.') : null}
                />
              </div>
            </div>
          )}

          {/* Edit Address Dialog */}
          {editingAddress && (
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="edit-address-dialog-title"
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
            >
              <div className="w-full max-w-lg rounded-xl bg-background p-6 shadow-lg">
                <h3 id="edit-address-dialog-title" className="mb-4 text-base font-semibold">
                  Edit Address
                </h3>
                <CompanyAddressForm
                  address={editingAddress}
                  onSubmit={handleEditAddress}
                  onCancel={() => setEditingAddress(null)}
                  isPending={updateAddress.isPending}
                  error={updateAddress.isError ? (updateAddress.error?.message ?? 'Failed to update address.') : null}
                />
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
