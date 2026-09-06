"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getCustomer360, type Customer360 } from "@/lib/api/crm";
import { classifyCrmError, getCompanyId, type CrmErrorState } from "@/components/crm/apiErrors";
import CrmStateBanner from "@/components/crm/CrmStateBanner";
import StatusBadge from "@/components/crm/StatusBadge";

const CREDIT_COLORS: Record<string, string> = {
  GOOD: "text-green-600",
  WARNING: "text-yellow-600",
  EXCEEDED: "text-red-600",
  HOLD: "text-red-700 font-semibold",
};

export default function Customer360Page() {
  const params = useParams<{ customerId: string }>();
  const customerId = params.customerId;
  const companyId = getCompanyId();

  const [data, setData] = useState<Customer360 | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorState, setErrorState] = useState<CrmErrorState | null>(null);

  const load = useCallback(async () => {
    if (!companyId || !customerId) return;
    setLoading(true);
    setErrorState(null);
    try {
      const res = await getCustomer360(companyId, customerId);
      setData(res.data);
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setLoading(false);
    }
  }, [companyId, customerId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return <div className="p-6 text-center text-gray-500">Loading…</div>;
  }

  if (!data) {
    return (
      <div className="p-6">
        {errorState && <CrmStateBanner state={errorState} />}
      </div>
    );
  }

  const hasCrmHistory =
    data.converted_leads.length > 0 || data.opportunities.length > 0 || data.activities.length > 0;

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{data.customer.legal_name}</h1>
          <p className="text-sm text-gray-500 mt-1">
            {data.customer.customer_code}
            {data.customer.trading_name ? ` · ${data.customer.trading_name}` : ""}
          </p>
        </div>
        <StatusBadge status={data.customer.status} />
      </div>

      {errorState && <CrmStateBanner state={errorState} />}

      <div className="grid grid-cols-2 gap-4 mb-6 text-sm">
        <div className="border border-gray-200 rounded-md p-3">
          <span className="text-gray-500">Last Interaction</span>
          <div className="text-gray-900 font-medium">{data.last_interaction ?? "None yet"}</div>
        </div>
        <div className="border border-gray-200 rounded-md p-3">
          <span className="text-gray-500">Next Follow-up</span>
          <div className="text-gray-900 font-medium">{data.next_follow_up ?? "None scheduled"}</div>
        </div>
      </div>

      <section className="mb-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-3 border-b border-gray-200 pb-2">
          Sales History
        </h2>
        <div className="grid grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-gray-500">Quotations</span>
            <div className="text-gray-900 font-medium">{data.sales_history.quotation_count}</div>
          </div>
          <div>
            <span className="text-gray-500">Orders</span>
            <div className="text-gray-900 font-medium">{data.sales_history.order_count}</div>
          </div>
          <div>
            <span className="text-gray-500">Invoices</span>
            <div className="text-gray-900 font-medium">{data.sales_history.invoice_count}</div>
          </div>
          <div>
            <span className="text-gray-500">Deliveries</span>
            <div className="text-gray-900 font-medium">{data.sales_history.delivery_count}</div>
          </div>
        </div>
      </section>

      <section className="mb-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-3 border-b border-gray-200 pb-2">
          Financial Summary
        </h2>
        <div className="grid grid-cols-3 gap-4 text-sm mb-3">
          <div>
            <span className="text-gray-500">Outstanding</span>
            <div className="text-gray-900 font-medium">
              {data.financial_summary.total_outstanding_base}
            </div>
          </div>
          <div>
            <span className="text-gray-500">Credit Limit</span>
            <div className="text-gray-900 font-medium">{data.financial_summary.credit_limit}</div>
          </div>
          <div>
            <span className="text-gray-500">Credit Status</span>
            <div
              className={`font-medium ${CREDIT_COLORS[data.financial_summary.credit_status] ?? "text-gray-900"}`}
            >
              {data.financial_summary.credit_status}
            </div>
          </div>
        </div>
        <div className="grid grid-cols-5 gap-2 text-xs">
          <div className="border border-gray-200 rounded p-2 text-center">
            <div className="text-gray-500">Current</div>
            <div className="font-medium">{data.financial_summary.current}</div>
          </div>
          <div className="border border-gray-200 rounded p-2 text-center">
            <div className="text-gray-500">1-30</div>
            <div className="font-medium">{data.financial_summary.days_1_30}</div>
          </div>
          <div className="border border-gray-200 rounded p-2 text-center">
            <div className="text-gray-500">31-60</div>
            <div className="font-medium">{data.financial_summary.days_31_60}</div>
          </div>
          <div className="border border-gray-200 rounded p-2 text-center">
            <div className="text-gray-500">61-90</div>
            <div className="font-medium">{data.financial_summary.days_61_90}</div>
          </div>
          <div className="border border-gray-200 rounded p-2 text-center">
            <div className="text-gray-500">91+</div>
            <div className="font-medium">{data.financial_summary.days_91_120}</div>
          </div>
        </div>
      </section>

      <section className="mb-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-3 border-b border-gray-200 pb-2">
          CRM History
        </h2>
        {!hasCrmHistory ? (
          <p className="text-sm text-gray-500">
            No CRM activity for this customer yet — no converted leads, opportunities, or
            logged activities.
          </p>
        ) : (
          <div className="space-y-4">
            {data.converted_leads.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                  Converted Leads
                </h3>
                <ul className="space-y-1">
                  {data.converted_leads.map((lead) => (
                    <li key={lead.id} className="text-sm">
                      <Link href={`../../leads/${lead.id}`} className="text-indigo-600 hover:underline">
                        {[lead.first_name, lead.last_name].filter(Boolean).join(" ") ||
                          lead.lead_company_name}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {data.opportunities.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                  Opportunities
                </h3>
                <ul className="space-y-1">
                  {data.opportunities.map((o) => (
                    <li key={o.id} className="text-sm flex items-center gap-2">
                      <Link
                        href={`../../opportunities/${o.id}`}
                        className="text-indigo-600 hover:underline"
                      >
                        {o.name}
                      </Link>
                      <StatusBadge status={o.status} />
                      <span className="text-gray-500">
                        {o.value} {o.currency_code}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {data.activities.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                  Recent Activities
                </h3>
                <ul className="space-y-1">
                  {data.activities.map((a) => (
                    <li key={a.id} className="text-sm flex items-center gap-2">
                      <span className="text-gray-500">{a.activity_type}</span>
                      <span className="text-gray-900">{a.subject}</span>
                      <StatusBadge status={a.status} />
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
