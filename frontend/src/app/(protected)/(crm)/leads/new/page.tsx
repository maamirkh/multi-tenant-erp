"use client";

import { useState, useEffect, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { createLead, listLeadSources, type LeadSourceRead } from "@/lib/api/crm";
import { classifyCrmError, getCompanyId, type CrmErrorState } from "@/components/crm/apiErrors";
import CrmStateBanner from "@/components/crm/CrmStateBanner";

export default function NewLeadPage() {
  const router = useRouter();
  const companyId = getCompanyId();

  const [sources, setSources] = useState<LeadSourceRead[]>([]);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [leadCompanyName, setLeadCompanyName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorState, setErrorState] = useState<CrmErrorState | null>(null);

  useEffect(() => {
    if (!companyId) return;
    listLeadSources(companyId)
      .then((res) => setSources(res.data?.items ?? []))
      .catch(() => setSources([]));
  }, [companyId]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!companyId) return;

    if (!firstName && !lastName && !leadCompanyName) {
      setErrorState({
        message: "Provide at least a first name, last name, or company name.",
        forbidden: false,
        featureDisabled: false,
      });
      return;
    }
    if (!email && !phone) {
      setErrorState({
        message: "Provide at least an email or a phone number.",
        forbidden: false,
        featureDisabled: false,
      });
      return;
    }

    setSubmitting(true);
    setErrorState(null);
    try {
      const res = await createLead(companyId, {
        ...(firstName ? { first_name: firstName } : {}),
        ...(lastName ? { last_name: lastName } : {}),
        ...(leadCompanyName ? { lead_company_name: leadCompanyName } : {}),
        ...(email ? { email } : {}),
        ...(phone ? { phone } : {}),
        ...(sourceId ? { source_id: sourceId } : {}),
        ...(notes ? { notes } : {}),
      });
      router.push(`../leads/${res.data.id}`);
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">New Lead</h1>

      {errorState && <CrmStateBanner state={errorState} />}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">First Name</label>
            <input
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Last Name</label>
            <input
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Company Name</label>
          <input
            value={leadCompanyName}
            onChange={(e) => setLeadCompanyName(e.target.value)}
            className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Source</label>
          <select
            value={sourceId}
            onChange={(e) => setSourceId(e.target.value)}
            className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm"
          >
            <option value="">(none)</option>
            {sources.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm"
          />
        </div>

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={submitting || !companyId}
            className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 text-sm font-medium disabled:opacity-50"
          >
            {submitting ? "Saving…" : "Create Lead"}
          </button>
          <button
            type="button"
            onClick={() => router.back()}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
