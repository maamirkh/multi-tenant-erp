"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

interface PRLine {
  id: string;
  line_number: number;
  product_description: string;
  quantity: string;
  estimated_unit_cost: string;
  estimated_line_total: string;
  notes?: string;
}

interface PurchaseRequest {
  id: string;
  pr_number: string;
  title: string;
  status: string;
  requestor_id: string;
  department?: string;
  required_by_date?: string;
  notes?: string;
  total_estimated_cost: string;
  currency_code: string;
  converted_to_po_id?: string;
  lines: PRLine[];
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  SUBMITTED: "bg-blue-100 text-blue-700",
  UNDER_REVIEW: "bg-yellow-100 text-yellow-700",
  APPROVED: "bg-green-100 text-green-700",
  REJECTED: "bg-red-100 text-red-700",
  CANCELLED: "bg-gray-200 text-gray-500",
};

export default function PurchaseRequestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [pr, _setPr] = useState<PurchaseRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    // TODO: Fetch PR from API using company context
    setLoading(false);
  }, [id]);

  const handleAction = async (action: "submit" | "approve" | "cancel") => {
    setActionLoading(true);
    try {
      // TODO: Call action API endpoint
      router.refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : `Failed to ${action} PR.`);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return <div className="p-6 text-sm text-gray-500">Loading...</div>;
  }

  if (!pr) {
    return (
      <div className="p-6">
        <p className="text-gray-500">Purchase request not found.</p>
        <Link href="../purchase-requests" className="text-blue-600 hover:underline text-sm mt-2 inline-block">
          Back to list
        </Link>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3">
            <span className="font-mono text-lg font-semibold text-gray-900">{pr.pr_number}</span>
            <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[pr.status] ?? ""}`}>
              {pr.status}
            </span>
          </div>
          <h1 className="text-xl font-medium text-gray-700 mt-1">{pr.title}</h1>
        </div>

        {/* Action buttons */}
        <div className="flex gap-2">
          {pr.status === "DRAFT" && (
            <>
              <Link
                href={`../purchase-requests/${pr.id}/edit`}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
              >
                Edit
              </Link>
              <button
                onClick={() => handleAction("submit")}
                disabled={actionLoading}
                className="rounded-md bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
              >
                Submit
              </button>
              <button
                onClick={() => handleAction("cancel")}
                disabled={actionLoading}
                className="rounded-md border border-red-200 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
              >
                Cancel
              </button>
            </>
          )}
          {(pr.status === "SUBMITTED" || pr.status === "UNDER_REVIEW") && (
            <button
              onClick={() => handleAction("approve")}
              disabled={actionLoading}
              className="rounded-md bg-green-600 px-3 py-1.5 text-sm text-white hover:bg-green-700 disabled:opacity-50"
            >
              Approve
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Meta */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {pr.department && (
          <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
            <div className="text-xs text-gray-400 uppercase tracking-wide">Department</div>
            <div className="text-sm font-medium text-gray-800 mt-0.5">{pr.department}</div>
          </div>
        )}
        {pr.required_by_date && (
          <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
            <div className="text-xs text-gray-400 uppercase tracking-wide">Required By</div>
            <div className="text-sm font-medium text-gray-800 mt-0.5">{pr.required_by_date}</div>
          </div>
        )}
        <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
          <div className="text-xs text-gray-400 uppercase tracking-wide">Total</div>
          <div className="text-sm font-medium text-gray-800 mt-0.5">
            {pr.currency_code} {parseFloat(pr.total_estimated_cost).toFixed(2)}
          </div>
        </div>
      </div>

      {/* Lines */}
      <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 text-sm font-medium text-gray-700">
          Line Items
        </div>
        <table className="min-w-full divide-y divide-gray-100">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase">#</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase">Description</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-gray-400 uppercase">Qty</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-gray-400 uppercase">Unit Cost</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-gray-400 uppercase">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {pr.lines.map((line) => (
              <tr key={line.id} className="hover:bg-gray-50">
                <td className="px-4 py-2.5 text-sm text-gray-500">{line.line_number}</td>
                <td className="px-4 py-2.5 text-sm text-gray-900">{line.product_description}</td>
                <td className="px-4 py-2.5 text-sm text-right text-gray-600">{parseFloat(line.quantity).toFixed(3)}</td>
                <td className="px-4 py-2.5 text-sm text-right text-gray-600">{parseFloat(line.estimated_unit_cost).toFixed(4)}</td>
                <td className="px-4 py-2.5 text-sm text-right font-medium text-gray-900">{parseFloat(line.estimated_line_total).toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="bg-gray-50">
              <td colSpan={4} className="px-4 py-2.5 text-sm font-medium text-gray-700 text-right">Total</td>
              <td className="px-4 py-2.5 text-sm font-bold text-gray-900 text-right">
                {pr.currency_code} {parseFloat(pr.total_estimated_cost).toFixed(2)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      {pr.notes && (
        <div className="mt-4 rounded-lg border border-gray-100 bg-gray-50 p-4">
          <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Notes</div>
          <p className="text-sm text-gray-700 whitespace-pre-wrap">{pr.notes}</p>
        </div>
      )}

      <div className="mt-4">
        <Link href="../purchase-requests" className="text-sm text-blue-600 hover:underline">
          ← Back to Purchase Requests
        </Link>
      </div>
    </div>
  );
}
