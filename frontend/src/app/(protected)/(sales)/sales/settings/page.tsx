"use client";

import { useEffect, useState } from "react";
import {
  createCustomerGroup,
  createSalesPaymentTerm,
  createSalesReasonCode,
  getCustomerGroups,
  getSalesConfiguration,
  getSalesPaymentTerms,
  getSalesReasonCodes,
  CustomerGroupRead,
  SalesPaymentTermRead,
  SalesReasonCodeRead,
  SalesConfigurationRead,
} from "@/lib/api/sales";

interface PageProps {
  params: { company_id: string };
}

/**
 * Sales Settings page.
 * Manages Customer Groups, Payment Terms, Reason Codes, and Sales Configuration.
 *
 * Spec ref: specs/007-sales-management/spec.md §14, §30
 */
export default function SalesSettingsPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const [activeTab, setActiveTab] = useState<"groups" | "terms" | "reasons" | "config">("groups");
  const [groups, setGroups] = useState<CustomerGroupRead[]>([]);
  const [paymentTerms, setPaymentTerms] = useState<SalesPaymentTermRead[]>([]);
  const [reasonCodes, setReasonCodes] = useState<SalesReasonCodeRead[]>([]);
  const [config, setConfig] = useState<SalesConfigurationRead | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [groupForm, setGroupForm] = useState({ code: "", name: "" });
  const [showGroupForm, setShowGroupForm] = useState(false);

  const [termsForm, setTermsForm] = useState({ code: "", name: "", due_days: 30 });
  const [showTermsForm, setShowTermsForm] = useState(false);

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
      const [g, t, r, c] = await Promise.all([
        getCustomerGroups(companyId).then((res) => res.data),
        getSalesPaymentTerms(companyId).then((res) => res.data),
        getSalesReasonCodes(companyId).then((res) => res.data),
        getSalesConfiguration(companyId).then((res) => res.data),
      ]);
      setGroups(g);
      setPaymentTerms(t);
      setReasonCodes(r);
      setConfig(c);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateGroup(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createCustomerGroup(companyId, groupForm);
      setShowGroupForm(false);
      setGroupForm({ code: "", name: "" });
      setSuccess("Customer group created");
      const res = await getCustomerGroups(companyId);
      setGroups(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create group");
    }
  }

  async function handleCreateTerms(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createSalesPaymentTerm(companyId, termsForm);
      setShowTermsForm(false);
      setTermsForm({ code: "", name: "", due_days: 30 });
      setSuccess("Payment terms created");
      const res = await getSalesPaymentTerms(companyId);
      setPaymentTerms(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create payment terms");
    }
  }

  async function handleCreateReason(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createSalesReasonCode(companyId, reasonForm);
      setShowReasonForm(false);
      setReasonForm({ code: "", name: "", reason_type: "RETURN" });
      setSuccess("Reason code created");
      const res = await getSalesReasonCodes(companyId);
      setReasonCodes(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create reason code");
    }
  }

  const tabs = [
    { key: "groups" as const, label: "Customer Groups" },
    { key: "terms" as const, label: "Payment Terms" },
    { key: "reasons" as const, label: "Reason Codes" },
    { key: "config" as const, label: "Configuration" },
  ];

  if (loading) {
    return <div className="p-6 text-center text-gray-500">Loading...</div>;
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold mb-6">Sales Settings</h1>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-700 rounded">{error}</div>
      )}
      {success && (
        <div className="mb-4 p-3 bg-green-50 text-green-700 rounded">{success}</div>
      )}

      <div className="flex gap-2 mb-6 border-b">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 -mb-px ${
              activeTab === tab.key
                ? "border-b-2 border-blue-600 text-blue-600 font-medium"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "groups" && (
        <div>
          <div className="flex justify-between mb-4">
            <h2 className="text-lg font-medium">Customer Groups</h2>
            <button
              onClick={() => setShowGroupForm(!showGroupForm)}
              className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
            >
              {showGroupForm ? "Cancel" : "New Group"}
            </button>
          </div>
          {showGroupForm && (
            <form onSubmit={handleCreateGroup} className="mb-4 p-4 border rounded space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">Code</label>
                  <input
                    value={groupForm.code}
                    onChange={(e) => setGroupForm({ ...groupForm, code: e.target.value })}
                    className="w-full border rounded px-3 py-2"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Name</label>
                  <input
                    value={groupForm.name}
                    onChange={(e) => setGroupForm({ ...groupForm, name: e.target.value })}
                    className="w-full border rounded px-3 py-2"
                    required
                  />
                </div>
              </div>
              <button type="submit" className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">Create</button>
            </form>
          )}
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left p-3">Code</th>
                <th className="text-left p-3">Name</th>
                <th className="text-left p-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => (
                <tr key={g.id} className="border-b hover:bg-gray-50">
                  <td className="p-3 font-mono text-sm">{g.code}</td>
                  <td className="p-3">{g.name}</td>
                  <td className="p-3">
                    <span className={`px-2 py-1 rounded text-xs ${g.is_active ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"}`}>
                      {g.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
              {groups.length === 0 && (
                <tr><td colSpan={3} className="p-3 text-center text-gray-400">No groups found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === "terms" && (
        <div>
          <div className="flex justify-between mb-4">
            <h2 className="text-lg font-medium">Payment Terms</h2>
            <button
              onClick={() => setShowTermsForm(!showTermsForm)}
              className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
            >
              {showTermsForm ? "Cancel" : "New Term"}
            </button>
          </div>
          {showTermsForm && (
            <form onSubmit={handleCreateTerms} className="mb-4 p-4 border rounded space-y-3">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">Code</label>
                  <input
                    value={termsForm.code}
                    onChange={(e) => setTermsForm({ ...termsForm, code: e.target.value })}
                    className="w-full border rounded px-3 py-2"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Name</label>
                  <input
                    value={termsForm.name}
                    onChange={(e) => setTermsForm({ ...termsForm, name: e.target.value })}
                    className="w-full border rounded px-3 py-2"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Due Days</label>
                  <input
                    type="number"
                    value={termsForm.due_days}
                    onChange={(e) => setTermsForm({ ...termsForm, due_days: parseInt(e.target.value) || 0 })}
                    className="w-full border rounded px-3 py-2"
                    required
                    min={0}
                  />
                </div>
              </div>
              <button type="submit" className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">Create</button>
            </form>
          )}
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left p-3">Code</th>
                <th className="text-left p-3">Name</th>
                <th className="text-left p-3">Due Days</th>
                <th className="text-left p-3">Discount</th>
                <th className="text-left p-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {paymentTerms.map((t) => (
                <tr key={t.id} className="border-b hover:bg-gray-50">
                  <td className="p-3 font-mono text-sm">{t.code}</td>
                  <td className="p-3">{t.name}</td>
                  <td className="p-3">{t.due_days}</td>
                  <td className="p-3">{t.discount_percent ? `${t.discount_percent}% / ${t.discount_days}d` : "-"}</td>
                  <td className="p-3">
                    <span className={`px-2 py-1 rounded text-xs ${t.is_active ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"}`}>
                      {t.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
              {paymentTerms.length === 0 && (
                <tr><td colSpan={5} className="p-3 text-center text-gray-400">No payment terms found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === "reasons" && (
        <div>
          <div className="flex justify-between mb-4">
            <h2 className="text-lg font-medium">Reason Codes</h2>
            <button
              onClick={() => setShowReasonForm(!showReasonForm)}
              className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
            >
              {showReasonForm ? "Cancel" : "New Code"}
            </button>
          </div>
          {showReasonForm && (
            <form onSubmit={handleCreateReason} className="mb-4 p-4 border rounded space-y-3">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">Code</label>
                  <input
                    value={reasonForm.code}
                    onChange={(e) => setReasonForm({ ...reasonForm, code: e.target.value })}
                    className="w-full border rounded px-3 py-2"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Name</label>
                  <input
                    value={reasonForm.name}
                    onChange={(e) => setReasonForm({ ...reasonForm, name: e.target.value })}
                    className="w-full border rounded px-3 py-2"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Type</label>
                  <select
                    value={reasonForm.reason_type}
                    onChange={(e) => setReasonForm({ ...reasonForm, reason_type: e.target.value as typeof reasonForm.reason_type })}
                    className="w-full border rounded px-3 py-2"
                  >
                    <option value="RETURN">Return</option>
                    <option value="CANCELLATION">Cancellation</option>
                    <option value="REJECTION">Rejection</option>
                    <option value="GENERAL">General</option>
                  </select>
                </div>
              </div>
              <button type="submit" className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">Create</button>
            </form>
          )}
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left p-3">Code</th>
                <th className="text-left p-3">Name</th>
                <th className="text-left p-3">Type</th>
                <th className="text-left p-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {reasonCodes.map((r) => (
                <tr key={r.id} className="border-b hover:bg-gray-50">
                  <td className="p-3 font-mono text-sm">{r.code}</td>
                  <td className="p-3">{r.name}</td>
                  <td className="p-3">{r.reason_type}</td>
                  <td className="p-3">
                    <span className={`px-2 py-1 rounded text-xs ${r.is_active ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"}`}>
                      {r.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
              {reasonCodes.length === 0 && (
                <tr><td colSpan={4} className="p-3 text-center text-gray-400">No reason codes found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === "config" && config && (
        <div className="space-y-4">
          <h2 className="text-lg font-medium">Sales Configuration</h2>
          <div className="grid grid-cols-2 gap-4 p-4 border rounded">
            <div>
              <span className="text-sm text-gray-500">Quotation Validity</span>
              <p className="font-medium">{config.default_quotation_validity_days} days</p>
            </div>
            <div>
              <span className="text-sm text-gray-500">Expiry Warning</span>
              <p className="font-medium">{config.quotation_expiry_warning_days} days</p>
            </div>
            <div>
              <span className="text-sm text-gray-500">Auto-Approve Threshold</span>
              <p className="font-medium">{config.auto_approve_threshold ?? "Disabled"}</p>
            </div>
            <div>
              <span className="text-sm text-gray-500">Min Margin %</span>
              <p className="font-medium">{config.minimum_margin_percentage ?? "Disabled"}</p>
            </div>
            <div>
              <span className="text-sm text-gray-500">Credit Warning Threshold</span>
              <p className="font-medium">{config.credit_warning_threshold}%</p>
            </div>
            <div>
              <span className="text-sm text-gray-500">Reservation Expiry</span>
              <p className="font-medium">{config.reservation_expiry_hours} hours</p>
            </div>
            <div>
              <span className="text-sm text-gray-500">Quotation Required</span>
              <p className="font-medium">{config.require_quotation_before_order ? "Yes" : "No"}</p>
            </div>
            <div>
              <span className="text-sm text-gray-500">Tax Inclusive</span>
              <p className="font-medium">{config.tax_inclusive_pricing ? "Yes" : "No"}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
