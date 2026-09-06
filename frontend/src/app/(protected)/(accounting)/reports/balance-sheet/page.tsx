"use client";

import { useState } from "react";
import ExportButton from "@/components/accounting/ExportButton";
import { BalanceSheetReport, BalanceSheetSection, getBalanceSheetReport } from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string };
}

function SectionTable({
  section,
  comparative,
}: {
  section: BalanceSheetSection;
  comparative?: BalanceSheetSection | undefined;
}) {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <div className="mb-4">
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="flex w-full items-center justify-between border-b border-gray-200 pb-1 text-left text-sm font-semibold text-gray-900"
      >
        <span>
          {collapsed ? "▸" : "▾"} {section.name}
        </span>
        <span>{section.total}</span>
      </button>
      {!collapsed && (
        <table className="mt-1 min-w-full text-sm">
          <tbody className="divide-y divide-gray-100">
            {section.lines.map((line) => {
              const compLine = comparative?.lines.find((l) => l.account_code === line.account_code);
              return (
                <tr key={line.account_id ?? line.account_code}>
                  <td className="py-1 pr-4 pl-4 text-gray-600">
                    {line.account_code !== "CYE" ? line.account_code + " — " : ""}
                    {line.account_name}
                  </td>
                  <td className="py-1 pr-4 text-right">{line.amount}</td>
                  {comparative && (
                    <td className="py-1 pr-4 text-right text-gray-500">
                      {compLine?.amount ?? "—"}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

/**
 * Balance Sheet report: hierarchical view by section (Assets/Liabilities/
 * Equity), comparative date column, expand/collapse groups.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T262
 */
export default function BalanceSheetPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";

  const [asOfDate, setAsOfDate] = useState(new Date().toISOString().slice(0, 10));
  const [comparativeDate, setComparativeDate] = useState("");
  const [reportCurrency, setReportCurrency] = useState("");
  const [report, setReport] = useState<BalanceSheetReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setLoading(true);
    setError(null);
    try {
      const res = await getBalanceSheetReport(
        companyId,
        asOfDate,
        comparativeDate || undefined,
        reportCurrency || undefined
      );
      setReport(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load balance sheet");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Balance Sheet</h1>
          <p className="mt-1 text-sm text-gray-500">Assets, liabilities, and equity as of a date.</p>
        </div>
        {report && (
          <ExportButton
            companyId={companyId}
            reportPath="/reports/balance-sheet"
            filename="balance-sheet"
            extraParams={{ as_of_date: asOfDate }}
          />
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      <div className="mb-6 flex flex-wrap items-end gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div>
          <label className="block text-xs text-gray-500">As Of Date</label>
          <input
            type="date"
            value={asOfDate}
            onChange={(e) => setAsOfDate(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500">Comparative Date (optional)</label>
          <input
            type="date"
            value={comparativeDate}
            onChange={(e) => setComparativeDate(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500">Report Currency (optional)</label>
          <input
            type="text"
            maxLength={3}
            placeholder="e.g. EUR"
            value={reportCurrency}
            onChange={(e) => setReportCurrency(e.target.value.toUpperCase())}
            className="w-24 rounded-md border border-gray-300 px-2 py-1 text-sm uppercase"
          />
        </div>
        <button
          onClick={handleRun}
          disabled={loading}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Loading..." : "Run Report"}
        </button>
      </div>

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : !report ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          Select a date and run the report.
        </div>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-900">
              As of {report.as_of_date} ({report.report_currency})
            </h2>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                report.is_balanced ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
              }`}
            >
              {report.is_balanced ? "Balanced" : "Out of Balance"}
            </span>
          </div>

          <SectionTable section={report.assets} comparative={report.comparative?.assets} />
          <SectionTable section={report.liabilities} comparative={report.comparative?.liabilities} />
          <SectionTable section={report.equity} comparative={report.comparative?.equity} />

          <div className="mt-4 border-t border-gray-200 pt-2 text-sm font-semibold text-gray-900">
            <div className="flex justify-between">
              <span>Total Assets</span>
              <span>{report.total_assets}</span>
            </div>
            <div className="flex justify-between">
              <span>Total Liabilities + Equity</span>
              <span>
                {(
                  parseFloat(report.total_liabilities) + parseFloat(report.total_equity)
                ).toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
