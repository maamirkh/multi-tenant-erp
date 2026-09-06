"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getAccessToken } from "@/lib/auth/tokenStorage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface WarehouseResponse {
  id: string;
  code: string;
  name: string;
  warehouse_type: string;
  status: string;
  city: string | null;
  country_code: string | null;
}

const TYPE_COLORS: Record<string, string> = {
  MAIN: "bg-blue-100 text-blue-700",
  BRANCH: "bg-purple-100 text-purple-700",
  TRANSIT: "bg-orange-100 text-orange-700",
  VIRTUAL: "bg-gray-100 text-gray-600",
  CONSIGNMENT: "bg-teal-100 text-teal-700",
};

const STATUS_COLORS: Record<string, string> = {
  ACTIVE: "text-green-700",
  INACTIVE: "text-yellow-600",
  ARCHIVED: "text-gray-400",
};

export default function WarehousesPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  const router = useRouter();

  const [warehouses, setWarehouses] = useState<WarehouseResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({
    code: "",
    name: "",
    warehouse_type: "MAIN",
  });
  const [saving, setSaving] = useState(false);

  const fetchWarehouses = async () => {
    setLoading(true);
    try {
      const resp = await fetch(
        `${API_BASE}/api/v1/companies/${companyId}/inventory/warehouses`,
        { headers: { Authorization: `Bearer ${getAccessToken()}` } }
      );
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();
      setWarehouses(data.data ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (companyId) fetchWarehouses();
  }, [companyId]);

  const handleCreate = async () => {
    if (!createForm.code.trim() || !createForm.name.trim()) return;
    setSaving(true);
    try {
      const resp = await fetch(
        `${API_BASE}/api/v1/companies/${companyId}/inventory/warehouses`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${getAccessToken()}`,
          },
          body: JSON.stringify(createForm),
        }
      );
      if (!resp.ok) throw new Error(await resp.text());
      setShowCreate(false);
      setCreateForm({ code: "", name: "", warehouse_type: "MAIN" });
      await fetchWarehouses();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-gray-100" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Warehouses</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          + New Warehouse
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <div className="mb-6 rounded-lg border border-blue-100 bg-blue-50 p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-800">New Warehouse</h2>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Code *</label>
              <input
                className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
                placeholder="WH-MAIN"
                value={createForm.code}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, code: e.target.value }))
                }
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Name *</label>
              <input
                className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
                placeholder="Main Warehouse"
                value={createForm.name}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, name: e.target.value }))
                }
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Type</label>
              <select
                className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
                value={createForm.warehouse_type}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, warehouse_type: e.target.value }))
                }
              >
                {["MAIN", "BRANCH", "TRANSIT", "VIRTUAL", "CONSIGNMENT"].map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="mt-3 flex gap-2">
            <button
              onClick={handleCreate}
              disabled={saving}
              className="rounded bg-blue-600 px-4 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Creating…" : "Create"}
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="rounded border border-gray-300 px-4 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Warehouse list */}
      {warehouses.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-gray-300 py-12 text-center text-sm text-gray-500">
          No warehouses yet. Create your first warehouse to get started.
        </div>
      ) : (
        <div className="space-y-2">
          {warehouses.map((wh) => (
            <div
              key={wh.id}
              onClick={() =>
                router.push(`/inventory/warehouses/${wh.id}`)
              }
              className="flex cursor-pointer items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3 hover:border-blue-300 hover:bg-blue-50/30 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span
                  className={`rounded px-2 py-0.5 text-xs font-medium ${TYPE_COLORS[wh.warehouse_type] ?? "bg-gray-100 text-gray-600"}`}
                >
                  {wh.warehouse_type}
                </span>
                <div>
                  <span className="font-medium text-gray-900">{wh.name}</span>
                  <span className="ml-2 text-xs font-mono text-gray-500">{wh.code}</span>
                  {wh.city && (
                    <span className="ml-2 text-xs text-gray-400">{wh.city}</span>
                  )}
                </div>
              </div>
              <span
                className={`text-xs font-medium ${STATUS_COLORS[wh.status] ?? "text-gray-500"}`}
              >
                {wh.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
