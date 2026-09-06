"use client";

import { useEffect, useState } from "react";
import {
  createPaymentTerms,
  createPurchaseReasonCode,
  getPaymentTerms,
  getPurchasePolicy,
  getPurchaseReasonCodes,
  PaymentTermsRead,
  PurchasePolicyRead,
  PurchaseReasonCodeRead,
  updatePurchasePolicy,
} from "@/lib/api/purchase";

interface PageProps {
  params: { company_id: string };
}

/**
 * Purchase Settings page.
 * Manages Payment Terms, Reason Codes, and Purchase Policy.
 *
 * Spec ref: specs/006-purchase-management/spec.md §14, §29
 */
export default function PurchaseSettingsPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const [activeTab, setActiveTab] = useState<"terms" | "reasons" | "policy">("terms");
  const [paymentTerms, setPaymentTerms] = useState<PaymentTermsRead[]>([]);
  const [reasonCodes, setReasonCodes] = useState<PurchaseReasonCodeRead[]>([]);
  const [policy, setPolicy] = useState<PurchasePolicyRead | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Payment terms form
  const [termsForm, setTermsForm] = useState({ code: "", name: "", net_days: 30 });
  const [showTermsForm, setShowTermsForm] = useState(false);

  // Reason code form
  const [reasonForm, setReasonForm] = useState({
    code: "",
    name: "",
    reason_type: "RETURN" as "RETURN" | "CANCELLATION" | "REJECTION" | "GENERAL",
  });
  const [showReasonForm, setShowReasonForm] = useState(false);

  useEffect(() => {
    if (!companyId) return;
    loadAll();
  }, [companyId]);

  async function loadAll() {
    setLoading(true);
    try {
      const [terms, reasons, pol] = await Promise.all([
        getPaymentTerms(companyId).then((r) => r.data),
        getPurchaseReasonCodes(companyId).then((r) => r.data),
        getPurchasePolicy(companyId).then((r) => r.data),
      ]);
      setPaymentTerms(terms);
      setReasonCodes(reasons);
      setPolicy(pol);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateTerms(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createPaymentTerms(companyId, termsForm);
      setShowTermsForm(false);
      setTermsForm({ code: "", name: "", net_days: 30 });
      setSuccess("Payment terms created");
      const res = await getPaymentTerms(companyId);
      setPaymentTerms(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create payment terms");
    }
  }

  async function handleCreateReasonCode(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createPurchaseReasonCode(companyId, reasonForm);
      setShowReasonForm(false);
      setReasonForm({ code: "", name: "", reason_type: "RETURN" });
      setSuccess("Reason code created");
      const res = await getPurchaseReasonCodes(companyId);
      setReasonCodes(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create reason code");
    }
  }

  async function handlePolicyUpdate(field: string, value: boolean | string | number) {
    if (!policy) return;
    try {
      const res = await updatePurchasePolicy(companyId, { [field]: value });
      setPolicy(res.data);
      setSuccess("Policy updated");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update policy");
    }
  }

  const tabs = [
    { key: "terms" as const, label: "Payment Terms" },
    { key: "reasons" as const, label: "Reason Codes" },
    { key: "policy" as const, label: "Procurement Policy" },
  ];

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-semibold text-gray-900 mb-6">
        Purchase Settings
      </h1>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error} <button onClick={() => setError(null)} className="ml-2 underline">Dismiss</button>
        </div>
      )}
      {success && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded text-green-700 text-sm">
          {success} <button onClick={() => setSuccess(null)} className="ml-2 underline">Dismiss</button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b mb-6">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
              activeTab === tab.key
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : (
        <>
          {/* Payment Terms Tab */}
          {activeTab === "terms" && (
            <div>
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-medium">Payment Terms</h2>
                <button
                  onClick={() => setShowTermsForm(!showTermsForm)}
                  className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
                >
                  + Add Terms
                </button>
              </div>

              {showTermsForm && (
                <form onSubmit={handleCreateTerms} className="mb-4 p-4 border rounded bg-gray-50">
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Code</label>
                      <input
                        value={termsForm.code}
                        onChange={(e) => setTermsForm({ ...termsForm, code: e.target.value.toUpperCase() })}
                        required maxLength={20}
                        className="w-full border rounded px-2 py-1.5 text-sm"
                        placeholder="NET30"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Name</label>
                      <input
                        value={termsForm.name}
                        onChange={(e) => setTermsForm({ ...termsForm, name: e.target.value })}
                        required
                        className="w-full border rounded px-2 py-1.5 text-sm"
                        placeholder="Net 30 Days"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Net Days</label>
                      <input
                        type="number" min={0}
                        value={termsForm.net_days}
                        onChange={(e) => setTermsForm({ ...termsForm, net_days: parseInt(e.target.value) })}
                        required
                        className="w-full border rounded px-2 py-1.5 text-sm"
                      />
                    </div>
                  </div>
                  <div className="flex gap-2 mt-3">
                    <button type="submit" className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">Create</button>
                    <button type="button" onClick={() => setShowTermsForm(false)} className="px-3 py-1.5 border rounded text-sm hover:bg-gray-100">Cancel</button>
                  </div>
                </form>
              )}

              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="bg-gray-50 border-b">
                    <th className="text-left px-4 py-2 font-medium text-gray-700">Code</th>
                    <th className="text-left px-4 py-2 font-medium text-gray-700">Name</th>
                    <th className="text-left px-4 py-2 font-medium text-gray-700">Net Days</th>
                    <th className="text-left px-4 py-2 font-medium text-gray-700">Active</th>
                  </tr>
                </thead>
                <tbody>
                  {paymentTerms.map((t) => (
                    <tr key={t.id} className="border-b hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono text-xs">{t.code}</td>
                      <td className="px-4 py-2">{t.name}</td>
                      <td className="px-4 py-2">{t.net_days}</td>
                      <td className="px-4 py-2">
                        <span className={`text-xs px-2 py-0.5 rounded ${t.is_active ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"}`}>
                          {t.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {paymentTerms.length === 0 && (
                    <tr><td colSpan={4} className="px-4 py-3 text-gray-500 text-center">No payment terms configured.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* Reason Codes Tab */}
          {activeTab === "reasons" && (
            <div>
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-medium">Reason Codes</h2>
                <button
                  onClick={() => setShowReasonForm(!showReasonForm)}
                  className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
                >
                  + Add Code
                </button>
              </div>

              {showReasonForm && (
                <form onSubmit={handleCreateReasonCode} className="mb-4 p-4 border rounded bg-gray-50">
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Code</label>
                      <input
                        value={reasonForm.code}
                        onChange={(e) => setReasonForm({ ...reasonForm, code: e.target.value.toUpperCase() })}
                        required maxLength={20}
                        className="w-full border rounded px-2 py-1.5 text-sm"
                        placeholder="WRONG-ITEM"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Name</label>
                      <input
                        value={reasonForm.name}
                        onChange={(e) => setReasonForm({ ...reasonForm, name: e.target.value })}
                        required
                        className="w-full border rounded px-2 py-1.5 text-sm"
                        placeholder="Wrong item delivered"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Type</label>
                      <select
                        value={reasonForm.reason_type}
                        onChange={(e) => setReasonForm({ ...reasonForm, reason_type: e.target.value as typeof reasonForm.reason_type })}
                        className="w-full border rounded px-2 py-1.5 text-sm"
                      >
                        <option value="RETURN">RETURN</option>
                        <option value="CANCELLATION">CANCELLATION</option>
                        <option value="REJECTION">REJECTION</option>
                        <option value="GENERAL">GENERAL</option>
                      </select>
                    </div>
                  </div>
                  <div className="flex gap-2 mt-3">
                    <button type="submit" className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">Create</button>
                    <button type="button" onClick={() => setShowReasonForm(false)} className="px-3 py-1.5 border rounded text-sm hover:bg-gray-100">Cancel</button>
                  </div>
                </form>
              )}

              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="bg-gray-50 border-b">
                    <th className="text-left px-4 py-2 font-medium text-gray-700">Code</th>
                    <th className="text-left px-4 py-2 font-medium text-gray-700">Name</th>
                    <th className="text-left px-4 py-2 font-medium text-gray-700">Type</th>
                    <th className="text-left px-4 py-2 font-medium text-gray-700">Active</th>
                  </tr>
                </thead>
                <tbody>
                  {reasonCodes.map((r) => (
                    <tr key={r.id} className="border-b hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono text-xs">{r.code}</td>
                      <td className="px-4 py-2">{r.name}</td>
                      <td className="px-4 py-2">
                        <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">{r.reason_type}</span>
                      </td>
                      <td className="px-4 py-2">
                        <span className={`text-xs px-2 py-0.5 rounded ${r.is_active ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"}`}>
                          {r.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {reasonCodes.length === 0 && (
                    <tr><td colSpan={4} className="px-4 py-3 text-gray-500 text-center">No reason codes configured.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* Policy Tab */}
          {activeTab === "policy" && policy && (
            <div>
              <h2 className="text-lg font-medium mb-4">Procurement Policy</h2>
              <div className="space-y-4">
                {[
                  { field: "direct_po_allowed", label: "Allow Direct PO (without PR)", value: policy.direct_po_allowed },
                  { field: "pr_approval_required", label: "PR Approval Required", value: policy.pr_approval_required },
                  { field: "po_approval_required", label: "PO Approval Required", value: policy.po_approval_required },
                ].map((item) => (
                  <div key={item.field} className="flex items-center justify-between p-4 border rounded">
                    <div>
                      <p className="text-sm font-medium text-gray-900">{item.label}</p>
                    </div>
                    <button
                      onClick={() => handlePolicyUpdate(item.field, !item.value)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        item.value ? "bg-blue-600" : "bg-gray-200"
                      }`}
                    >
                      <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        item.value ? "translate-x-6" : "translate-x-1"
                      }`} />
                    </button>
                  </div>
                ))}

                <div className="flex items-center justify-between p-4 border rounded">
                  <div>
                    <p className="text-sm font-medium text-gray-900">Over-Receipt Policy</p>
                    <p className="text-xs text-gray-500">Behaviour when GR quantity exceeds PO quantity</p>
                  </div>
                  <select
                    value={policy.over_receipt_policy}
                    onChange={(e) => handlePolicyUpdate("over_receipt_policy", e.target.value)}
                    className="border rounded px-3 py-1.5 text-sm"
                  >
                    <option value="BLOCK">BLOCK</option>
                    <option value="WARN">WARN</option>
                    <option value="ALLOW">ALLOW</option>
                  </select>
                </div>

                <div className="flex items-center justify-between p-4 border rounded">
                  <div>
                    <p className="text-sm font-medium text-gray-900">Credit Limit Mode</p>
                    <p className="text-xs text-gray-500">Enforcement at PO approval</p>
                  </div>
                  <select
                    value={policy.credit_limit_mode}
                    onChange={(e) => handlePolicyUpdate("credit_limit_mode", e.target.value)}
                    className="border rounded px-3 py-1.5 text-sm"
                  >
                    <option value="BLOCK">BLOCK</option>
                    <option value="WARN">WARN</option>
                    <option value="OFF">OFF</option>
                  </select>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
