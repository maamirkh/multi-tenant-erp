"use client";

import { useState, useEffect, useCallback } from "react";
import {
  listApprovalMatrices,
  createApprovalMatrix,
  type SalesApprovalMatrixRead,
} from "@/lib/api/sales";

export default function ApprovalMatrixPage() {
  const [matrices, setMatrices] = useState<SalesApprovalMatrixRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formLoading, setFormLoading] = useState(false);

  const [formName, setFormName] = useState("");
  const [formDocType, setFormDocType] = useState<"SALES_ORDER" | "SALES_RETURN">("SALES_ORDER");

  const companyId =
    typeof window !== "undefined"
      ? (localStorage.getItem("company_id") ?? "")
      : "";
  const token =
    typeof window !== "undefined"
      ? (localStorage.getItem("access_token") ?? undefined)
      : undefined;

  const load = useCallback(async () => {
    if (!companyId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await listApprovalMatrices(companyId, undefined, token);
      setMatrices(res.data as SalesApprovalMatrixRead[]);
    } catch {
      setError("Failed to load approval matrices.");
    } finally {
      setLoading(false);
    }
  }, [companyId, token]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!formName.trim() || !companyId) return;
    setFormLoading(true);
    setError(null);
    try {
      await createApprovalMatrix(
        companyId,
        {
          name: formName,
          document_type: formDocType,
          is_active: true,
          rules: [],
        },
        token
      );
      setShowForm(false);
      setFormName("");
      await load();
    } catch {
      setError("Failed to create approval matrix.");
    } finally {
      setFormLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Approval Matrix</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium"
        >
          {showForm ? "Cancel" : "+ New Matrix"}
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">{error}</div>
      )}

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">New Approval Matrix</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Name</label>
              <input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                placeholder="e.g. Standard SO Approval"
                required
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Document Type</label>
              <select
                value={formDocType}
                onChange={(e) => setFormDocType(e.target.value as "SALES_ORDER" | "SALES_RETURN")}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
              >
                <option value="SALES_ORDER">Sales Order</option>
                <option value="SALES_RETURN">Sales Return</option>
              </select>
            </div>
          </div>
          <div className="mt-3 flex justify-end">
            <button
              type="submit"
              disabled={formLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium disabled:opacity-50"
            >
              Create Matrix
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="text-gray-500 text-sm py-8 text-center">Loading...</p>
      ) : matrices.length === 0 ? (
        <div className="flex flex-col items-center py-16 text-gray-400">
          <p className="text-lg font-medium">No approval matrices configured</p>
          <p className="text-sm mt-1">Create a matrix to define approval workflows for sales orders.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {matrices.map((m) => (
            <div key={m.id} className="bg-white rounded-lg border border-gray-200 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-gray-900">{m.name}</h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {m.document_type.replace(/_/g, " ")} ·{" "}
                    <span className={m.is_active ? "text-green-600" : "text-gray-400"}>
                      {m.is_active ? "Active" : "Inactive"}
                    </span>
                  </p>
                </div>
                <span className="text-xs text-gray-400">{m.rules?.length ?? 0} rules</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
