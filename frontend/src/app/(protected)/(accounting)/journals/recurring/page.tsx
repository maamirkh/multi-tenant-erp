"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  RecurringInstanceResponse,
  RecurringTemplateResponse,
  activateRecurringTemplate,
  deactivateRecurringTemplate,
  getRecurringTemplateHistory,
  getRecurringTemplates,
} from "@/lib/api/accounting";

/**
 * Recurring Journal Templates list page.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T126
 */
export default function RecurringJournalsPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  const [templates, setTemplates] = useState<RecurringTemplateResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [history, setHistory] = useState<RecurringInstanceResponse[]>([]);

  useEffect(() => {
    if (!companyId) return;
    load();
  }, [companyId]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getRecurringTemplates(companyId);
      setTemplates(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load recurring templates");
    } finally {
      setLoading(false);
    }
  }

  async function toggleActive(template: RecurringTemplateResponse) {
    setError(null);
    try {
      if (template.is_active) {
        await deactivateRecurringTemplate(companyId, template.id);
      } else {
        await activateRecurringTemplate(companyId, template.id);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update template");
    }
  }

  async function toggleHistory(templateId: string) {
    if (expandedId === templateId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(templateId);
    try {
      const res = await getRecurringTemplateHistory(companyId, templateId);
      setHistory(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load execution history");
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Link href={`/${companyId}/journals`} className="text-sm text-blue-600 hover:underline">
            ← Journal Entries
          </Link>
          <h1 className="mt-1 text-2xl font-semibold text-gray-900">
            Recurring Journal Templates
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Automated periodic entries — rent, insurance, subscriptions, accruals.
          </p>
        </div>
        <Link
          href={`/${companyId}/journals/recurring/new`}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          New Template
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : templates.length === 0 ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No recurring journal templates yet.
        </div>
      ) : (
        <div className="space-y-3">
          {templates.map((t) => (
            <div key={t.id} className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-gray-900">{t.template_name}</p>
                  <p className="text-xs text-gray-500">
                    {t.frequency} · Next run: {t.next_run_date} ·{" "}
                    {t.auto_post ? "Auto-post" : t.approval_required ? "Requires approval" : "Manual draft"}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                      t.is_active ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {t.is_active ? "Active" : "Inactive"}
                  </span>
                  <button
                    onClick={() => toggleHistory(t.id)}
                    className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                  >
                    History
                  </button>
                  <button
                    onClick={() => toggleActive(t)}
                    className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                  >
                    {t.is_active ? "Deactivate" : "Activate"}
                  </button>
                </div>
              </div>

              {expandedId === t.id && (
                <div className="mt-3 border-t border-gray-100 pt-3">
                  {history.length === 0 ? (
                    <p className="text-xs text-gray-400">No executions yet.</p>
                  ) : (
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-left text-gray-500">
                          <th className="py-1">Date</th>
                          <th className="py-1">Status</th>
                          <th className="py-1">Detail</th>
                        </tr>
                      </thead>
                      <tbody>
                        {history.map((h) => (
                          <tr key={h.id}>
                            <td className="py-1">{h.execution_date}</td>
                            <td className="py-1">
                              <span
                                className={
                                  h.status === "SUCCESS" ? "text-green-700" : "text-red-700"
                                }
                              >
                                {h.status}
                              </span>
                            </td>
                            <td className="py-1 text-gray-500">{h.error_message ?? ""}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
