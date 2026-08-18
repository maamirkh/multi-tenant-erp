"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  TaxCodeResponse,
  TaxGroupLineResponse,
  TaxGroupResponse,
  addTaxGroupLine,
  createTaxGroup,
  getTaxCodes,
  getTaxGroupLines,
  getTaxGroups,
} from "@/lib/api/accounting";

const emptyForm = {
  group_code: "",
  group_name: "",
  applicability: "BOTH",
};

/**
 * Tax Group management: bundle multiple tax codes applied together.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T240
 */
export default function TaxGroupsPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  const [groups, setGroups] = useState<TaxGroupResponse[]>([]);
  const [taxCodes, setTaxCodes] = useState<TaxCodeResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);

  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [lines, setLines] = useState<TaxGroupLineResponse[]>([]);
  const [selectedTaxCodeId, setSelectedTaxCodeId] = useState("");
  const [displayOrder, setDisplayOrder] = useState("0");

  useEffect(() => {
    if (!companyId) return;
    load();
  }, [companyId]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [groupsRes, codesRes] = await Promise.all([
        getTaxGroups(companyId),
        getTaxCodes(companyId, true),
      ]);
      setGroups(groupsRes.data);
      setTaxCodes(codesRes.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tax groups");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    if (!form.group_code || !form.group_name) {
      setError("Group code and name are required.");
      return;
    }
    setError(null);
    try {
      await createTaxGroup(companyId, form);
      setForm(emptyForm);
      setShowForm(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create tax group");
    }
  }

  async function handleViewLines(groupId: string) {
    setSelectedGroupId(groupId === selectedGroupId ? null : groupId);
    setError(null);
    if (groupId === selectedGroupId) return;
    try {
      const res = await getTaxGroupLines(companyId, groupId);
      setLines(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tax group lines");
    }
  }

  async function handleAddLine(groupId: string) {
    if (!selectedTaxCodeId) {
      setError("Select a tax code to add.");
      return;
    }
    setError(null);
    try {
      await addTaxGroupLine(companyId, groupId, {
        tax_code_id: selectedTaxCodeId,
        display_order: Number(displayOrder) || 0,
      });
      setSelectedTaxCodeId("");
      setDisplayOrder("0");
      const res = await getTaxGroupLines(companyId, groupId);
      setLines(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add tax code to group");
    }
  }

  function taxCodeLabel(taxCodeId: string): string {
    const code = taxCodes.find((c) => c.id === taxCodeId);
    return code ? `${code.tax_code} — ${code.tax_name}` : taxCodeId;
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Tax Groups</h1>
          <p className="mt-1 text-sm text-gray-500">
            Bundle multiple tax codes to be applied together (e.g. Federal + Provincial).
          </p>
        </div>
        <div className="flex gap-3">
          <Link
            href={`/${companyId}/tax/codes`}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Tax Codes
          </Link>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            New Tax Group
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {showForm && (
        <div className="mb-6 grid grid-cols-1 gap-4 rounded-lg border border-gray-200 bg-white p-4 shadow-sm sm:grid-cols-3">
          <input
            type="text"
            value={form.group_code}
            onChange={(e) => setForm({ ...form, group_code: e.target.value })}
            placeholder="Group code"
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
          <input
            type="text"
            value={form.group_name}
            onChange={(e) => setForm({ ...form, group_name: e.target.value })}
            placeholder="Group name"
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
          <select
            value={form.applicability}
            onChange={(e) => setForm({ ...form, applicability: e.target.value })}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          >
            <option value="SALES">Sales</option>
            <option value="PURCHASES">Purchases</option>
            <option value="BOTH">Both</option>
          </select>
          <div className="sm:col-span-3">
            <button
              onClick={handleCreate}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Create
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : groups.length === 0 ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No tax groups yet.
        </div>
      ) : (
        <div className="space-y-3">
          {groups.map((group) => (
            <div key={group.id} className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-gray-900">
                    {group.group_code} — {group.group_name}
                  </p>
                  <p className="text-xs text-gray-500">
                    {group.applicability}
                    {!group.is_active && " · Inactive"}
                  </p>
                </div>
                <button
                  onClick={() => handleViewLines(group.id)}
                  className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                >
                  Member Codes
                </button>
              </div>

              {selectedGroupId === group.id && (
                <div className="mt-4 border-t border-gray-100 pt-4">
                  {lines.length === 0 ? (
                    <p className="mb-3 text-sm text-gray-500">No member tax codes yet.</p>
                  ) : (
                    <ul className="mb-3 space-y-1 text-sm">
                      {lines
                        .slice()
                        .sort((a, b) => a.display_order - b.display_order)
                        .map((line) => (
                          <li key={line.id} className="text-gray-700">
                            {line.display_order}. {taxCodeLabel(line.tax_code_id)}
                          </li>
                        ))}
                    </ul>
                  )}

                  <div className="flex gap-3">
                    <select
                      value={selectedTaxCodeId}
                      onChange={(e) => setSelectedTaxCodeId(e.target.value)}
                      className="flex-1 rounded-md border border-gray-300 px-2 py-1 text-sm"
                    >
                      <option value="">Select a tax code</option>
                      {taxCodes.map((code) => (
                        <option key={code.id} value={code.id}>
                          {code.tax_code} — {code.tax_name}
                        </option>
                      ))}
                    </select>
                    <input
                      type="number"
                      value={displayOrder}
                      onChange={(e) => setDisplayOrder(e.target.value)}
                      placeholder="Order"
                      className="w-20 rounded-md border border-gray-300 px-2 py-1 text-sm"
                    />
                    <button
                      onClick={() => handleAddLine(group.id)}
                      className="rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700"
                    >
                      Add
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
