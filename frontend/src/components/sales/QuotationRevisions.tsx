"use client";

import { useState, useEffect } from "react";
import { getQuotationRevisions, type QuotationRevisionRead } from "@/lib/api/sales";

interface QuotationRevisionsProps {
  companyId: string;
  quotationId: string;
  token?: string;
  onClose: () => void;
}

export default function QuotationRevisions({
  companyId,
  quotationId,
  token,
  onClose,
}: QuotationRevisionsProps) {
  const [revisions, setRevisions] = useState<QuotationRevisionRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await getQuotationRevisions(companyId, quotationId, token);
        const data = res.data as QuotationRevisionRead[];
        setRevisions([...data].reverse()); // newest first
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load revisions",
        );
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [companyId, quotationId, token]);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-end z-50">
      <div className="bg-white w-full max-w-lg h-full overflow-y-auto shadow-2xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 sticky top-0 bg-white">
          <h2 className="text-lg font-semibold text-gray-900">
            Revision History
          </h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-xl font-bold"
            aria-label="Close revisions panel"
          >
            ×
          </button>
        </div>

        <div className="p-6">
          {loading ? (
            <div className="text-center py-8 text-gray-500">
              Loading revisions...
            </div>
          ) : error ? (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          ) : revisions.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm">
              No revisions found
            </div>
          ) : (
            <div className="space-y-3">
              {revisions.map((rev) => (
                <div
                  key={rev.id}
                  className="border border-gray-200 rounded-lg overflow-hidden"
                >
                  <button
                    className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
                    onClick={() =>
                      setExpanded(expanded === rev.id ? null : rev.id)
                    }
                  >
                    <div>
                      <span className="font-medium text-gray-800 text-sm">
                        Revision {rev.revision_number}
                      </span>
                      {rev.change_summary && (
                        <p className="text-xs text-gray-500 mt-0.5">
                          {rev.change_summary}
                        </p>
                      )}
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-gray-500">
                        {rev.modified_at.replace("T", " ").substring(0, 16)}
                      </p>
                      <span className="text-xs text-gray-400">
                        {expanded === rev.id ? "▲ hide" : "▼ show"} snapshot
                      </span>
                    </div>
                  </button>

                  {expanded === rev.id && (
                    <div className="px-4 py-3 bg-white">
                      <div className="space-y-2 text-sm mb-3">
                        <div className="flex justify-between">
                          <span className="text-gray-500">Status</span>
                          <span className="font-medium text-gray-700">
                            {rev.snapshot.status as string}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Total</span>
                          <span className="font-medium text-gray-700">
                            {rev.snapshot.total_amount as string}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Valid Until</span>
                          <span className="text-gray-700">
                            {rev.snapshot.validity_date as string}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Lines</span>
                          <span className="text-gray-700">
                            {
                              (
                                rev.snapshot.lines as Array<unknown>
                              ).length
                            }{" "}
                            item(s)
                          </span>
                        </div>
                      </div>
                      {(rev.snapshot.lines as Array<Record<string, unknown>>)
                        .length > 0 && (
                        <div className="border-t border-gray-100 pt-2">
                          <p className="text-xs font-medium text-gray-500 mb-1">
                            Lines at this revision:
                          </p>
                          <div className="space-y-1">
                            {(
                              rev.snapshot.lines as Array<
                                Record<string, unknown>
                              >
                            ).map((ln, i) => (
                              <div
                                key={i}
                                className="flex justify-between text-xs text-gray-600"
                              >
                                <span className="truncate max-w-[200px]">
                                  {ln.description as string}
                                </span>
                                <span className="font-medium">
                                  {ln.extended_amount as string}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
