"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getAccessToken } from "@/lib/auth/tokenStorage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface WarehouseResponse {
  id: string;
  code: string;
  name: string;
  warehouse_type: string;
  status: string;
  branch_id: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state_province: string | null;
  postal_code: string | null;
  country_code: string | null;
  phone: string | null;
  notes: string | null;
}

interface LocationResponse {
  id: string;
  location_code: string;
  aisle: string | null;
  zone: string | null;
  shelf: string | null;
  is_active: boolean;
}

const STATUS_ACTIONS: Record<string, { label: string; endpoint: string }[]> = {
  ACTIVE: [{ label: "Deactivate", endpoint: "deactivate" }],
  INACTIVE: [
    { label: "Activate", endpoint: "activate" },
    { label: "Archive", endpoint: "archive" },
  ],
  ARCHIVED: [],
};

export default function WarehouseDetailPage() {
  const params = useParams<{ warehouse_id: string }>();
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  const warehouseId = params?.warehouse_id;
  const router = useRouter();

  const [warehouse, setWarehouse] = useState<WarehouseResponse | null>(null);
  const [locations, setLocations] = useState<LocationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddLoc, setShowAddLoc] = useState(false);
  const [locForm, setLocForm] = useState({
    location_code: "",
    aisle: "",
    zone: "",
    shelf: "",
  });
  const [saving, setSaving] = useState(false);

  const baseUrl = `${API_BASE}/api/v1/companies/${companyId}/inventory/warehouses/${warehouseId}`;
  const authHeaders = { Authorization: `Bearer ${getAccessToken()}` };

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [whResp, locResp] = await Promise.all([
        fetch(baseUrl, { headers: authHeaders }),
        fetch(`${baseUrl}/locations`, { headers: authHeaders }),
      ]);
      if (!whResp.ok) throw new Error(await whResp.text());
      if (!locResp.ok) throw new Error(await locResp.text());
      const whData = await whResp.json();
      const locData = await locResp.json();
      setWarehouse(whData.data);
      setLocations(locData.data ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (companyId && warehouseId) fetchData();
  }, [companyId, warehouseId]);

  const handleStatusAction = async (endpoint: string) => {
    try {
      const resp = await fetch(`${baseUrl}/${endpoint}`, {
        method: "POST",
        headers: authHeaders,
      });
      if (!resp.ok) throw new Error(await resp.text());
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    }
  };

  const handleAddLocation = async () => {
    if (!locForm.location_code.trim()) return;
    setSaving(true);
    try {
      const resp = await fetch(`${baseUrl}/locations`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({
          location_code: locForm.location_code.trim(),
          aisle: locForm.aisle || null,
          zone: locForm.zone || null,
          shelf: locForm.shelf || null,
        }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      setShowAddLoc(false);
      setLocForm({ location_code: "", aisle: "", zone: "", shelf: "" });
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add location");
    } finally {
      setSaving(false);
    }
  };

  const handleToggleLocation = async (loc: LocationResponse) => {
    try {
      const resp = await fetch(`${baseUrl}/locations/${loc.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({ is_active: !loc.is_active }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update location");
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <div className="h-48 animate-pulse rounded-lg bg-gray-100" />
      </div>
    );
  }

  if (!warehouse) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8 text-center text-gray-500">
        Warehouse not found.
      </div>
    );
  }

  const actions = STATUS_ACTIONS[warehouse.status] ?? [];

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button
            onClick={() => router.back()}
            className="mb-2 text-sm text-gray-500 hover:text-gray-700"
          >
            ← Back
          </button>
          <h1 className="text-xl font-semibold text-gray-900">{warehouse.name}</h1>
          <div className="mt-1 flex items-center gap-3 text-sm text-gray-500">
            <span className="font-mono">{warehouse.code}</span>
            <span>·</span>
            <span>{warehouse.warehouse_type}</span>
            <span>·</span>
            <span
              className={
                warehouse.status === "ACTIVE"
                  ? "text-green-600 font-medium"
                  : warehouse.status === "ARCHIVED"
                    ? "text-gray-400"
                    : "text-yellow-600"
              }
            >
              {warehouse.status}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          {actions.map((action) => (
            <button
              key={action.endpoint}
              onClick={() => handleStatusAction(action.endpoint)}
              className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Address */}
      {(warehouse.address_line1 || warehouse.city) && (
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h2 className="mb-2 text-sm font-semibold text-gray-700">Address</h2>
          <div className="text-sm text-gray-600 space-y-0.5">
            {warehouse.address_line1 && <p>{warehouse.address_line1}</p>}
            {warehouse.address_line2 && <p>{warehouse.address_line2}</p>}
            <p>
              {[warehouse.city, warehouse.state_province, warehouse.postal_code]
                .filter(Boolean)
                .join(", ")}
            </p>
            {warehouse.country_code && <p>{warehouse.country_code}</p>}
            {warehouse.phone && (
              <p className="mt-1 text-gray-500">📞 {warehouse.phone}</p>
            )}
          </div>
        </div>
      )}

      {/* Locations */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">
            Locations ({locations.length})
          </h2>
          {warehouse.status !== "ARCHIVED" && (
            <button
              onClick={() => setShowAddLoc(true)}
              className="text-sm text-blue-600 hover:text-blue-700"
            >
              + Add Location
            </button>
          )}
        </div>

        {showAddLoc && (
          <div className="mb-4 rounded-lg border border-blue-100 bg-blue-50 p-3">
            <div className="grid grid-cols-4 gap-2">
              {[
                { key: "location_code", label: "Code *", placeholder: "A-01-01" },
                { key: "aisle", label: "Aisle", placeholder: "A" },
                { key: "zone", label: "Zone", placeholder: "Zone1" },
                { key: "shelf", label: "Shelf", placeholder: "Top" },
              ].map(({ key, label, placeholder }) => (
                <div key={key}>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    {label}
                  </label>
                  <input
                    className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
                    placeholder={placeholder}
                    value={locForm[key as keyof typeof locForm]}
                    onChange={(e) =>
                      setLocForm((f) => ({ ...f, [key]: e.target.value }))
                    }
                  />
                </div>
              ))}
            </div>
            <div className="mt-2 flex gap-2">
              <button
                onClick={handleAddLocation}
                disabled={saving}
                className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? "Adding…" : "Add"}
              </button>
              <button
                onClick={() => setShowAddLoc(false)}
                className="rounded border border-gray-300 px-3 py-1 text-sm text-gray-600 hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {locations.length === 0 ? (
          <div className="rounded-lg border-2 border-dashed border-gray-200 py-8 text-center text-sm text-gray-400">
            No locations defined yet.
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-gray-200">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500">
                <tr>
                  <th className="px-4 py-2 text-left">Code</th>
                  <th className="px-4 py-2 text-left">Aisle</th>
                  <th className="px-4 py-2 text-left">Zone</th>
                  <th className="px-4 py-2 text-left">Shelf</th>
                  <th className="px-4 py-2 text-left">Status</th>
                  {warehouse.status !== "ARCHIVED" && (
                    <th className="px-4 py-2 text-right">Action</th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {locations.map((loc) => (
                  <tr key={loc.id} className="bg-white">
                    <td className="px-4 py-2 font-mono font-medium">
                      {loc.location_code}
                    </td>
                    <td className="px-4 py-2 text-gray-500">{loc.aisle ?? "—"}</td>
                    <td className="px-4 py-2 text-gray-500">{loc.zone ?? "—"}</td>
                    <td className="px-4 py-2 text-gray-500">{loc.shelf ?? "—"}</td>
                    <td className="px-4 py-2">
                      <span
                        className={`text-xs font-medium ${loc.is_active ? "text-green-600" : "text-gray-400"}`}
                      >
                        {loc.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    {warehouse.status !== "ARCHIVED" && (
                      <td className="px-4 py-2 text-right">
                        <button
                          onClick={() => handleToggleLocation(loc)}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          {loc.is_active ? "Deactivate" : "Activate"}
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {warehouse.notes && (
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h2 className="mb-1 text-sm font-semibold text-gray-700">Notes</h2>
          <p className="text-sm text-gray-600 whitespace-pre-wrap">{warehouse.notes}</p>
        </div>
      )}
    </div>
  );
}
