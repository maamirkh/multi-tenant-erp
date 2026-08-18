"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getCustomer,
  updateCustomer,
  listCustomerContacts,
  addCustomerContact,
  listCustomerAddresses,
  addCustomerAddress,
  listCustomerNotes,
  addCustomerNote,
  type Customer,
  type CustomerContact,
  type CustomerAddress,
  type CustomerNote,
} from "@/lib/api/sales";
import CustomerStatusActions, {
  CustomerStatusBadge,
} from "@/components/sales/CustomerStatusActions";

type Tab = "general" | "contacts" | "addresses" | "notes";

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const companyId =
    typeof window !== "undefined"
      ? (localStorage.getItem("erp_active_company_id") ?? "")
      : "";
  const token =
    typeof window !== "undefined"
      ? (localStorage.getItem("access_token") ?? undefined)
      : undefined;

  const [customer, setCustomer] = useState<Customer | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("general");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  // Edit form state (general tab)
  const [editMode, setEditMode] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});

  // Sub-entity lists
  const [contacts, setContacts] = useState<CustomerContact[]>([]);
  const [addresses, setAddresses] = useState<CustomerAddress[]>([]);
  const [notes, setNotes] = useState<CustomerNote[]>([]);
  const [noteText, setNoteText] = useState("");

  const loadCustomer = useCallback(async () => {
    if (!companyId || !id) return;
    setLoading(true);
    try {
      const res = await getCustomer(companyId, id as string, token);
      setCustomer(res.data);
      setForm({
        legal_name: res.data?.legal_name ?? "",
        trading_name: res.data?.trading_name ?? "",
        payment_term: res.data?.payment_term ?? "",
        website: res.data?.website ?? "",
        notes: res.data?.notes ?? "",
        rating: res.data?.rating ?? "",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load customer");
    } finally {
      setLoading(false);
    }
  }, [companyId, id, token]);

  const loadContacts = useCallback(async () => {
    if (!companyId || !id) return;
    const res = await listCustomerContacts(companyId, id as string, token);
    setContacts(res.data ?? []);
  }, [companyId, id, token]);

  const loadAddresses = useCallback(async () => {
    if (!companyId || !id) return;
    const res = await listCustomerAddresses(companyId, id as string, token);
    setAddresses(res.data ?? []);
  }, [companyId, id, token]);

  const loadNotes = useCallback(async () => {
    if (!companyId || !id) return;
    const res = await listCustomerNotes(companyId, id as string, token);
    setNotes(res.data ?? []);
  }, [companyId, id, token]);

  useEffect(() => { loadCustomer(); }, [loadCustomer]);

  useEffect(() => {
    if (tab === "contacts") loadContacts();
    if (tab === "addresses") loadAddresses();
    if (tab === "notes") loadNotes();
  }, [tab, loadContacts, loadAddresses, loadNotes]);

  async function saveGeneral() {
    if (!companyId || !id) return;
    setSaving(true);
    setSaveMsg(null);
    try {
      await updateCustomer(companyId, id as string, form, token);
      setSaveMsg("Saved successfully.");
      setEditMode(false);
      loadCustomer();
    } catch (err) {
      setSaveMsg(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function postNote() {
    if (!companyId || !id || !noteText.trim()) return;
    await addCustomerNote(companyId, id as string, noteText, token);
    setNoteText("");
    loadNotes();
  }

  if (loading) return <div className="p-6 text-gray-500">Loading…</div>;
  if (error) return <div className="p-6 text-red-600">{error}</div>;
  if (!customer) return <div className="p-6 text-gray-500">Not found.</div>;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3">
            <Link href="../customers" className="text-sm text-indigo-600 hover:underline">
              ← Customers
            </Link>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mt-1">
            {customer.legal_name}
          </h1>
          <p className="text-sm text-gray-500 font-mono">{customer.customer_code}</p>
          <div className="mt-2 flex gap-2">
            <CustomerStatusBadge status={customer.status} />
            <span className="text-sm text-gray-500">{customer.customer_type}</span>
          </div>
        </div>
        <CustomerStatusActions
          companyId={companyId}
          customerId={id as string}
          currentStatus={customer.status}
          token={token}
          onSuccess={loadCustomer}
        />
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex -mb-px gap-6">
          {(["general", "contacts", "addresses", "notes"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`py-2 px-1 text-sm font-medium border-b-2 transition-colors ${
                tab === t
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </nav>
      </div>

      {/* General tab */}
      {tab === "general" && (
        <div className="space-y-4">
          {saveMsg && (
            <p className={`text-sm ${saveMsg.includes("failed") ? "text-red-600" : "text-green-600"}`}>
              {saveMsg}
            </p>
          )}
          <div className="grid grid-cols-2 gap-4">
            {[
              { key: "legal_name", label: "Legal Name" },
              { key: "trading_name", label: "Trading Name" },
              { key: "payment_term", label: "Payment Term" },
              { key: "website", label: "Website" },
              { key: "rating", label: "Rating" },
            ].map(({ key, label }) => (
              <div key={key}>
                <label className="text-xs font-medium text-gray-500 uppercase">{label}</label>
                {editMode ? (
                  <input
                    value={form[key] ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                    className="mt-1 w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm"
                  />
                ) : (
                  <p className="mt-1 text-sm text-gray-900">{String((customer as unknown as Record<string, string>)[key] ?? "") || "—"}</p>
                )}
              </div>
            ))}
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-500 uppercase">Internal Notes</label>
              {editMode ? (
                <textarea
                  value={form.notes ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                  rows={3}
                  className="mt-1 w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm"
                />
              ) : (
                <p className="mt-1 text-sm text-gray-900">{customer.notes || "—"}</p>
              )}
            </div>
          </div>

          {/* Read-only financial fields */}
          <div className="grid grid-cols-3 gap-4 mt-4 p-4 bg-gray-50 rounded-lg">
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase">Currency</p>
              <p className="text-sm font-medium text-gray-900">{customer.currency_code}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase">Credit Limit</p>
              <p className="text-sm font-medium text-gray-900">
                {Number(customer.credit_limit).toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase">Credit Used</p>
              <p className="text-sm font-medium text-gray-900">
                {Number(customer.credit_used).toLocaleString()}
              </p>
            </div>
          </div>

          <div className="flex gap-2 pt-2">
            {editMode ? (
              <>
                <button
                  onClick={saveGeneral}
                  disabled={saving}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700 disabled:opacity-50"
                >
                  {saving ? "Saving…" : "Save"}
                </button>
                <button
                  onClick={() => setEditMode(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
                >
                  Cancel
                </button>
              </>
            ) : (
              <button
                onClick={() => setEditMode(true)}
                className="px-4 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
              >
                Edit
              </button>
            )}
          </div>
        </div>
      )}

      {/* Contacts tab */}
      {tab === "contacts" && (
        <div className="space-y-4">
          {contacts.length === 0 ? (
            <p className="text-sm text-gray-500">No contacts yet.</p>
          ) : (
            <div className="divide-y">
              {contacts.map((c) => (
                <div key={c.id} className="py-3 flex items-start justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {c.contact_name}
                      {c.is_primary && (
                        <span className="ml-2 text-xs bg-blue-100 text-blue-700 px-1.5 rounded">Primary</span>
                      )}
                    </p>
                    <p className="text-xs text-gray-500">{c.email} · {c.phone}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
          <AddContactForm
            companyId={companyId}
            customerId={id as string}
            token={token}
            onAdded={loadContacts}
          />
        </div>
      )}

      {/* Addresses tab */}
      {tab === "addresses" && (
        <div className="space-y-4">
          {addresses.length === 0 ? (
            <p className="text-sm text-gray-500">No addresses yet.</p>
          ) : (
            <div className="grid grid-cols-2 gap-4">
              {addresses.map((a) => (
                <div key={a.id} className="p-3 border rounded-lg text-sm">
                  <span className="text-xs font-semibold uppercase text-gray-500">{a.address_type}</span>
                  <p className="mt-1 text-gray-900">{a.address_line_1}</p>
                  {a.address_line_2 && <p className="text-gray-500">{a.address_line_2}</p>}
                  <p className="text-gray-900">{a.city}, {a.country_code}</p>
                  <div className="mt-1 flex gap-2">
                    {a.is_default_billing && <span className="text-xs bg-green-100 text-green-700 px-1.5 rounded">Default Billing</span>}
                    {a.is_default_shipping && <span className="text-xs bg-blue-100 text-blue-700 px-1.5 rounded">Default Shipping</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
          <AddAddressForm
            companyId={companyId}
            customerId={id as string}
            token={token}
            onAdded={loadAddresses}
          />
        </div>
      )}

      {/* Notes tab */}
      {tab === "notes" && (
        <div className="space-y-4">
          <div className="space-y-3">
            {notes.map((n) => (
              <div key={n.id} className="p-3 bg-gray-50 rounded-lg text-sm">
                <p className="text-gray-900">{n.content}</p>
                <p className="text-xs text-gray-400 mt-1">
                  {n.author_name} · {new Date(n.created_at).toLocaleDateString()}
                </p>
              </div>
            ))}
          </div>
          <div className="mt-4">
            <textarea
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              rows={3}
              placeholder="Add an internal note…"
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            />
            <button
              onClick={postNote}
              disabled={!noteText.trim()}
              className="mt-2 px-4 py-2 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700 disabled:opacity-50"
            >
              Add Note
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mini sub-forms
// ---------------------------------------------------------------------------

function AddContactForm({
  companyId, customerId, token, onAdded,
}: { companyId: string; customerId: string; token: string | undefined; onAdded: () => void | Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState({ contact_name: "", email: "", phone: "", position: "", is_primary: false });
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await addCustomerContact(companyId, customerId, data, token);
      setOpen(false);
      setData({ contact_name: "", email: "", phone: "", position: "", is_primary: false });
      onAdded();
    } finally {
      setSaving(false);
    }
  }

  if (!open) return (
    <button onClick={() => setOpen(true)} className="text-sm text-indigo-600 hover:underline">
      + Add Contact
    </button>
  );

  return (
    <div className="p-4 border rounded-lg space-y-2 mt-2">
      <h4 className="text-sm font-medium text-gray-700">New Contact</h4>
      {[
        { key: "contact_name", label: "Name *" },
        { key: "email", label: "Email" },
        { key: "phone", label: "Phone" },
        { key: "position", label: "Position" },
      ].map(({ key, label }) => (
        <div key={key}>
          <label className="text-xs text-gray-500">{label}</label>
          <input
            value={String((data as unknown as Record<string, string>)[key] ?? "")}
            onChange={(e) => setData((d) => ({ ...d, [key]: e.target.value }))}
            className="w-full border border-gray-300 rounded-md px-2 py-1 text-sm"
          />
        </div>
      ))}
      <label className="flex items-center gap-2 text-sm text-gray-700">
        <input type="checkbox" checked={data.is_primary} onChange={(e) => setData((d) => ({ ...d, is_primary: e.target.checked }))} />
        Primary contact
      </label>
      <div className="flex gap-2">
        <button onClick={save} disabled={saving || !data.contact_name} className="px-3 py-1 bg-indigo-600 text-white text-sm rounded-md disabled:opacity-50">
          {saving ? "Saving…" : "Save"}
        </button>
        <button onClick={() => setOpen(false)} className="px-3 py-1 border text-sm rounded-md">Cancel</button>
      </div>
    </div>
  );
}

function AddAddressForm({
  companyId, customerId, token, onAdded,
}: { companyId: string; customerId: string; token: string | undefined; onAdded: () => void | Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState({
    address_type: "BILLING", address_line_1: "", city: "", country_code: "US",
    is_default_billing: false, is_default_shipping: false,
  });
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await addCustomerAddress(companyId, customerId, data, token);
      setOpen(false);
      onAdded();
    } finally {
      setSaving(false);
    }
  }

  if (!open) return (
    <button onClick={() => setOpen(true)} className="text-sm text-indigo-600 hover:underline">
      + Add Address
    </button>
  );

  return (
    <div className="p-4 border rounded-lg space-y-2 mt-2">
      <h4 className="text-sm font-medium text-gray-700">New Address</h4>
      <div>
        <label className="text-xs text-gray-500">Type</label>
        <select value={data.address_type} onChange={(e) => setData((d) => ({ ...d, address_type: e.target.value }))} className="w-full border border-gray-300 rounded-md px-2 py-1 text-sm">
          <option value="BILLING">Billing</option>
          <option value="SHIPPING">Shipping</option>
          <option value="BOTH">Both</option>
        </select>
      </div>
      {[
        { key: "address_line_1", label: "Address Line 1 *" },
        { key: "city", label: "City *" },
        { key: "country_code", label: "Country Code *" },
      ].map(({ key, label }) => (
        <div key={key}>
          <label className="text-xs text-gray-500">{label}</label>
          <input
            value={String((data as unknown as Record<string, string>)[key] ?? "")}
            onChange={(e) => setData((d) => ({ ...d, [key]: e.target.value }))}
            className="w-full border border-gray-300 rounded-md px-2 py-1 text-sm"
          />
        </div>
      ))}
      <div className="flex gap-4">
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={data.is_default_billing} onChange={(e) => setData((d) => ({ ...d, is_default_billing: e.target.checked }))} />
          Default Billing
        </label>
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={data.is_default_shipping} onChange={(e) => setData((d) => ({ ...d, is_default_shipping: e.target.checked }))} />
          Default Shipping
        </label>
      </div>
      <div className="flex gap-2">
        <button onClick={save} disabled={saving || !data.address_line_1 || !data.city || !data.country_code} className="px-3 py-1 bg-indigo-600 text-white text-sm rounded-md disabled:opacity-50">
          {saving ? "Saving…" : "Save"}
        </button>
        <button onClick={() => setOpen(false)} className="px-3 py-1 border text-sm rounded-md">Cancel</button>
      </div>
    </div>
  );
}
