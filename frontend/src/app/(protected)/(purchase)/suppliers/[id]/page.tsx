"use client";

import { useEffect, useState } from "react";
import {
  getSupplier,
  createSupplier,
  updateSupplier,
  activateSupplier,
  deactivateSupplier,
  blockSupplier,
  reactivateSupplier,
  archiveSupplier,
  getSupplierContacts,
  getSupplierAddresses,
  getSupplierDocuments,
  addSupplierDocument,
  deleteSupplierDocument,
  SupplierRead,
  SupplierContactRead,
  SupplierAddressRead,
  SupplierDocumentRead,
} from "@/lib/api/purchase";
import SupplierFinancialPanel from "@/components/purchase/SupplierFinancialPanel";

interface PageProps {
  params: { company_id: string; id: string };
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  ACTIVE: "bg-green-100 text-green-800",
  INACTIVE: "bg-yellow-100 text-yellow-800",
  BLOCKED: "bg-red-100 text-red-800",
  ARCHIVED: "bg-slate-100 text-slate-600",
};

type TabKey = "core" | "contacts" | "addresses" | "financial" | "documents";

/**
 * Supplier create/edit/detail page with contacts and addresses tabs.
 * Task: T045
 */
export default function SupplierDetailPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const supplierId = params?.id;
  const isNew = supplierId === "new";

  const [supplier, setSupplier] = useState<SupplierRead | null>(null);
  const [contacts, setContacts] = useState<SupplierContactRead[]>([]);
  const [addresses, setAddresses] = useState<SupplierAddressRead[]>([]);
  const [documents, setDocuments] = useState<SupplierDocumentRead[]>([]);
  const [isPreferred, setIsPreferred] = useState(false);
  const [loading, setLoading] = useState(!isNew);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("core");
  const [saving, setSaving] = useState(false);

  // Create/edit form
  const [form, setForm] = useState({
    supplier_code: "",
    legal_name: "",
    trading_name: "",
    supplier_type: "GOODS" as "GOODS" | "SERVICES" | "BOTH",
    currency_code: "USD",
    website: "",
    notes: "",
    lead_time_days: "",
  });

  // Block reason modal
  const [showBlockModal, setShowBlockModal] = useState(false);
  const [blockReason, setBlockReason] = useState("");

  useEffect(() => {
    if (!companyId || isNew) return;
    loadSupplier();
  }, [companyId, supplierId]);

  async function loadSupplier() {
    setLoading(true);
    try {
      const [sup, ctcts, addrs, docs] = await Promise.all([
        getSupplier(companyId, supplierId!).then((r) => r.data),
        getSupplierContacts(companyId, supplierId!).then((r) => r.data),
        getSupplierAddresses(companyId, supplierId!).then((r) => r.data),
        getSupplierDocuments(companyId, supplierId!).then((r) => r.data),
      ]);
      setSupplier(sup);
      setContacts(ctcts);
      setAddresses(addrs);
      setDocuments(docs);
      setIsPreferred(sup.is_preferred ?? false);
      setForm({
        supplier_code: sup.supplier_code,
        legal_name: sup.legal_name,
        trading_name: sup.trading_name ?? "",
        supplier_type: sup.supplier_type as "GOODS" | "SERVICES" | "BOTH",
        currency_code: sup.currency_code,
        website: sup.website ?? "",
        notes: sup.notes ?? "",
        lead_time_days: sup.lead_time_days != null ? String(sup.lead_time_days) : "",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load supplier");
    } finally {
      setLoading(false);
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (isNew) {
        await createSupplier(companyId, {
          supplier_code: form.supplier_code,
          legal_name: form.legal_name,
          ...(form.trading_name ? { trading_name: form.trading_name } : {}),
          supplier_type: form.supplier_type,
          currency_code: form.currency_code,
          ...(form.website ? { website: form.website } : {}),
          ...(form.notes ? { notes: form.notes } : {}),
          ...(form.lead_time_days ? { lead_time_days: parseInt(form.lead_time_days) } : {}),
        });
        setSuccess("Supplier created");
        window.location.href = `/companies/${companyId}/purchase/suppliers`;
      } else {
        const res = await updateSupplier(companyId, supplierId!, {
          legal_name: form.legal_name,
          ...(form.trading_name ? { trading_name: form.trading_name } : {}),
          supplier_type: form.supplier_type,
          currency_code: form.currency_code,
          ...(form.website ? { website: form.website } : {}),
          ...(form.notes ? { notes: form.notes } : {}),
          ...(form.lead_time_days ? { lead_time_days: parseInt(form.lead_time_days) } : {}),
        });
        setSupplier(res.data);
        setSuccess("Supplier updated");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save supplier");
    } finally {
      setSaving(false);
    }
  }

  async function handleLifecycleAction(action: string) {
    if (!supplierId) return;
    setSaving(true);
    setError(null);
    try {
      let res;
      if (action === "activate") res = await activateSupplier(companyId, supplierId, {});
      else if (action === "deactivate") res = await deactivateSupplier(companyId, supplierId, {});
      else if (action === "reactivate") res = await reactivateSupplier(companyId, supplierId, {});
      else if (action === "archive") res = await archiveSupplier(companyId, supplierId, {});
      if (res) {
        setSupplier(res.data);
        setSuccess(`Supplier ${action}d`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} supplier`);
    } finally {
      setSaving(false);
    }
  }

  async function handleBlock(e: React.FormEvent) {
    e.preventDefault();
    if (!supplierId || !blockReason.trim()) return;
    setSaving(true);
    try {
      const res = await blockSupplier(companyId, supplierId, { reason: blockReason });
      setSupplier(res.data);
      setBlockReason("");
      setShowBlockModal(false);
      setSuccess("Supplier blocked");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to block supplier");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="p-6 text-sm text-gray-500">Loading...</div>;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center gap-4 mb-6">
        <a href={`/companies/${companyId}/purchase/suppliers`} className="text-blue-600 hover:underline text-sm">
          &larr; Suppliers
        </a>
        <h1 className="text-2xl font-semibold text-gray-900">
          {isNew ? "New Supplier" : supplier?.legal_name ?? "Supplier"}
        </h1>
        {supplier && (
          <span className={`text-sm px-3 py-1 rounded ${STATUS_COLORS[supplier.status] ?? ""}`}>
            {supplier.status}
          </span>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded text-green-700 text-sm">
          {success}
        </div>
      )}

      {/* Lifecycle actions */}
      {!isNew && supplier && (
        <div className="flex gap-2 mb-6 flex-wrap">
          {supplier.status === "DRAFT" && (
            <button onClick={() => handleLifecycleAction("activate")} disabled={saving}
              className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50">
              Activate
            </button>
          )}
          {supplier.status === "ACTIVE" && (
            <>
              <button onClick={() => handleLifecycleAction("deactivate")} disabled={saving}
                className="px-3 py-1.5 bg-yellow-500 text-white rounded text-sm hover:bg-yellow-600 disabled:opacity-50">
                Deactivate
              </button>
              <button onClick={() => setShowBlockModal(true)} disabled={saving}
                className="px-3 py-1.5 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50">
                Block
              </button>
              <button onClick={() => handleLifecycleAction("archive")} disabled={saving}
                className="px-3 py-1.5 border text-gray-700 rounded text-sm hover:bg-gray-50 disabled:opacity-50">
                Archive
              </button>
            </>
          )}
          {(supplier.status === "INACTIVE" || supplier.status === "BLOCKED") && (
            <button onClick={() => handleLifecycleAction("reactivate")} disabled={saving}
              className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50">
              Reactivate
            </button>
          )}
          {supplier.status === "INACTIVE" && (
            <button onClick={() => handleLifecycleAction("archive")} disabled={saving}
              className="px-3 py-1.5 border text-gray-700 rounded text-sm hover:bg-gray-50 disabled:opacity-50">
              Archive
            </button>
          )}
        </div>
      )}

      {/* Block modal */}
      {showBlockModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full shadow-xl">
            <h2 className="text-lg font-semibold mb-3">Block Supplier</h2>
            <p className="text-sm text-gray-500 mb-3">Provide a mandatory reason for blocking this supplier.</p>
            <form onSubmit={handleBlock}>
              <textarea
                value={blockReason}
                onChange={(e) => setBlockReason(e.target.value)}
                required minLength={1}
                className="w-full border rounded px-3 py-2 text-sm mb-3 h-20"
                placeholder="Reason for blocking..."
              />
              <div className="flex gap-2">
                <button type="submit" className="px-4 py-1.5 bg-red-600 text-white rounded text-sm hover:bg-red-700">
                  Block Supplier
                </button>
                <button type="button" onClick={() => setShowBlockModal(false)}
                  className="px-4 py-1.5 border rounded text-sm hover:bg-gray-50">
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b mb-6">
        {[
          { key: "core" as TabKey, label: "Core Details" },
          { key: "contacts" as TabKey, label: `Contacts (${contacts.length})` },
          { key: "addresses" as TabKey, label: `Addresses (${addresses.length})` },
          ...(!isNew ? [
            { key: "financial" as TabKey, label: "Financial" },
            { key: "documents" as TabKey, label: `Documents (${documents.length})` },
          ] : []),
        ].map((tab) => (
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

      {/* Core Details */}
      {activeTab === "core" && (
        <form onSubmit={handleSave} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Supplier Code *</label>
              <input
                value={form.supplier_code}
                onChange={(e) => setForm({ ...form, supplier_code: e.target.value.toUpperCase() })}
                required maxLength={30} disabled={!isNew}
                className="w-full border rounded px-3 py-1.5 text-sm disabled:bg-gray-50"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Supplier Type</label>
              <select
                value={form.supplier_type}
                onChange={(e) => setForm({ ...form, supplier_type: e.target.value as "GOODS" | "SERVICES" | "BOTH" })}
                className="w-full border rounded px-3 py-1.5 text-sm"
              >
                <option value="GOODS">GOODS</option>
                <option value="SERVICES">SERVICES</option>
                <option value="BOTH">BOTH</option>
              </select>
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-700 mb-1">Legal Name *</label>
              <input
                value={form.legal_name}
                onChange={(e) => setForm({ ...form, legal_name: e.target.value })}
                required maxLength={300}
                className="w-full border rounded px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Trading Name</label>
              <input
                value={form.trading_name}
                onChange={(e) => setForm({ ...form, trading_name: e.target.value })}
                maxLength={300}
                className="w-full border rounded px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Currency</label>
              <input
                value={form.currency_code}
                onChange={(e) => setForm({ ...form, currency_code: e.target.value.toUpperCase() })}
                maxLength={3}
                className="w-full border rounded px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Website</label>
              <input
                value={form.website}
                onChange={(e) => setForm({ ...form, website: e.target.value })}
                type="url" maxLength={500}
                className="w-full border rounded px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Lead Time (days)</label>
              <input
                value={form.lead_time_days}
                onChange={(e) => setForm({ ...form, lead_time_days: e.target.value })}
                type="number" min={0}
                className="w-full border rounded px-3 py-1.5 text-sm"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-700 mb-1">Notes</label>
              <textarea
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                rows={3}
                className="w-full border rounded px-3 py-1.5 text-sm"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button type="submit" disabled={saving}
              className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50">
              {saving ? "Saving..." : isNew ? "Create Supplier" : "Save Changes"}
            </button>
            <a href={`/companies/${companyId}/purchase/suppliers`}
              className="px-4 py-1.5 border rounded text-sm hover:bg-gray-50">
              Cancel
            </a>
          </div>
        </form>
      )}

      {/* Contacts Tab */}
      {activeTab === "contacts" && !isNew && (
        <div>
          <h2 className="text-lg font-medium mb-4">Contacts</h2>
          {contacts.length === 0 ? (
            <p className="text-sm text-gray-500">No contacts added yet.</p>
          ) : (
            <table className="w-full text-sm border-collapse mb-4">
              <thead>
                <tr className="bg-gray-50 border-b">
                  <th className="text-left px-4 py-2 font-medium text-gray-700">Name</th>
                  <th className="text-left px-4 py-2 font-medium text-gray-700">Role</th>
                  <th className="text-left px-4 py-2 font-medium text-gray-700">Email</th>
                  <th className="text-left px-4 py-2 font-medium text-gray-700">Phone</th>
                  <th className="text-left px-4 py-2 font-medium text-gray-700">Primary</th>
                </tr>
              </thead>
              <tbody>
                {contacts.map((c) => (
                  <tr key={c.id} className="border-b">
                    <td className="px-4 py-2">{c.first_name} {c.last_name}</td>
                    <td className="px-4 py-2 text-gray-500">{c.role ?? "-"}</td>
                    <td className="px-4 py-2">{c.email ?? "-"}</td>
                    <td className="px-4 py-2">{c.phone ?? c.mobile ?? "-"}</td>
                    <td className="px-4 py-2">
                      {c.is_primary && <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">Primary</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Addresses Tab */}
      {activeTab === "addresses" && !isNew && (
        <div>
          <h2 className="text-lg font-medium mb-4">Addresses</h2>
          {addresses.length === 0 ? (
            <p className="text-sm text-gray-500">No addresses added yet.</p>
          ) : (
            <div className="space-y-3">
              {addresses.map((a) => (
                <div key={a.id} className="border rounded p-4 text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{a.address_type}</span>
                    {a.is_default && <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">Default</span>}
                  </div>
                  <p>{a.address_line_1}</p>
                  {a.address_line_2 && <p>{a.address_line_2}</p>}
                  <p>{a.city}{a.state ? `, ${a.state}` : ""} {a.postal_code}</p>
                  <p className="font-medium">{a.country_code}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Financial Tab (Phase 2) */}
      {activeTab === "financial" && !isNew && supplierId && (
        <SupplierFinancialPanel
          companyId={companyId}
          supplierId={supplierId}
          isPreferred={isPreferred}
          onPreferredChange={(val) => {
            setIsPreferred(val);
            setSupplier((prev) => prev ? { ...prev, is_preferred: val } : prev);
          }}
        />
      )}

      {/* Documents Tab (Phase 2) */}
      {activeTab === "documents" && !isNew && supplierId && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium">Compliance Documents</h2>
            <button
              onClick={async () => {
                const docType = prompt("Document type (e.g. Trade License):");
                if (!docType) return;
                const expiry = prompt("Expiry date (YYYY-MM-DD), leave blank if none:");
                try {
                  const res = await addSupplierDocument(companyId, supplierId, {
                    document_type: docType,
                    ...(expiry ? { expiry_date: expiry } : {}),
                  });
                  setDocuments((prev) => [...prev, res.data]);
                  setSuccess("Document added");
                } catch {
                  setError("Failed to add document");
                }
              }}
              className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
            >
              + Add Document
            </button>
          </div>
          {documents.length === 0 ? (
            <p className="text-sm text-gray-500">No compliance documents uploaded.</p>
          ) : (
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-gray-50 border-b">
                  <th className="text-left px-4 py-2 font-medium text-gray-700">Type</th>
                  <th className="text-left px-4 py-2 font-medium text-gray-700">Number</th>
                  <th className="text-left px-4 py-2 font-medium text-gray-700">Expiry</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {documents.map((d) => (
                  <tr key={d.id} className="border-b">
                    <td className="px-4 py-2">{d.document_type}</td>
                    <td className="px-4 py-2 text-gray-500">{d.document_number ?? "-"}</td>
                    <td className="px-4 py-2">
                      {d.expiry_date ? (
                        <span className={new Date(d.expiry_date) < new Date() ? "text-red-600" : "text-gray-700"}>
                          {d.expiry_date}
                        </span>
                      ) : "-"}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={async () => {
                          if (!confirm("Delete this document?")) return;
                          try {
                            await deleteSupplierDocument(companyId, supplierId, d.id);
                            setDocuments((prev) => prev.filter((doc) => doc.id !== d.id));
                          } catch {
                            setError("Failed to delete document");
                          }
                        }}
                        className="text-xs text-red-600 hover:underline"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
