"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AccountCreateRequest,
  AccountTreeNode,
  createAccount,
  getAccounts,
  getCOATemplates,
  applyCOATemplate,
  COATemplateInfo,
} from "@/lib/api/accounting";
import AccountFormModal from "@/components/accounting/AccountFormModal";

interface PageProps {
  params: { company_id: string };
}

const TYPE_ORDER = ["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"] as const;

function TreeNode({ node, depth }: { node: AccountTreeNode; depth: number }) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = node.children.length > 0;

  return (
    <div>
      <div
        className="flex items-center gap-2 border-b border-gray-100 py-1.5 hover:bg-gray-50"
        style={{ paddingLeft: `${depth * 20}px` }}
      >
        {hasChildren ? (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="w-4 text-xs text-gray-500"
            aria-label={expanded ? "Collapse" : "Expand"}
          >
            {expanded ? "▾" : "▸"}
          </button>
        ) : (
          <span className="w-4" />
        )}
        <span className="w-16 font-mono text-xs text-gray-500">{node.account_code}</span>
        <span className="flex-1 text-sm text-gray-900">{node.account_name}</span>
        {node.is_leaf && (
          <span className="rounded bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-700">
            leaf
          </span>
        )}
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
            node.is_active ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-500"
          }`}
        >
          {node.is_active ? "Active" : "Inactive"}
        </span>
      </div>
      {expanded && hasChildren && (
        <div>
          {node.children.map((child) => (
            <TreeNode key={child.id} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Chart of Accounts page — expandable hierarchical tree grouped by account type.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T059
 */
export default function ChartOfAccountsPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const [tree, setTree] = useState<AccountTreeNode[]>([]);
  const [templates, setTemplates] = useState<COATemplateInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState("");

  useEffect(() => {
    if (!companyId) return;
    load();
  }, [companyId]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [treeRes, templatesRes] = await Promise.all([
        getAccounts(companyId, true),
        getCOATemplates(companyId),
      ]);
      setTree(treeRes.data as AccountTreeNode[]);
      setTemplates(templatesRes.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load chart of accounts");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(data: AccountCreateRequest) {
    await createAccount(companyId, data);
    setSuccess("Account created");
    await load();
  }

  async function handleApplyTemplate() {
    if (!selectedTemplate) return;
    setError(null);
    try {
      const res = await applyCOATemplate(companyId, selectedTemplate);
      setSuccess(`Template applied: ${res.data.length} accounts created`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to apply template");
    }
  }

  const grouped = TYPE_ORDER.map((type) => ({
    type,
    nodes: tree.filter((n) => n.account_type === type),
  })).filter((g) => g.nodes.length > 0);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">Chart of Accounts</h1>
        <div className="flex items-center gap-3">
          <Link
            href={`/${companyId}/chart-of-accounts/system-accounts`}
            className="text-sm font-medium text-blue-600 hover:underline"
          >
            System Accounts
          </Link>
          <Link
            href={`/${companyId}/chart-of-accounts/import`}
            className="text-sm font-medium text-blue-600 hover:underline"
          >
            Bulk Import
          </Link>
          <button
            onClick={() => setShowModal(true)}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Add Account
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-4 rounded-md bg-green-50 p-3 text-sm text-green-700" role="status">
          {success}
        </div>
      )}

      {tree.length === 0 && !loading && (
        <div className="mb-6 rounded-md border border-dashed border-gray-300 p-6 text-center">
          <p className="mb-3 text-sm text-gray-500">
            No accounts yet. Start from an industry template.
          </p>
          <div className="flex items-center justify-center gap-2">
            <select
              value={selectedTemplate}
              onChange={(e) => setSelectedTemplate(e.target.value)}
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="">Select a template…</option>
              {templates.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label}
                </option>
              ))}
            </select>
            <button
              onClick={handleApplyTemplate}
              disabled={!selectedTemplate}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              Apply Template
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : (
        <div className="rounded-md border border-gray-200">
          {grouped.map((group) => (
            <div key={group.type}>
              <div className="bg-gray-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-gray-600">
                {group.type}
              </div>
              {group.nodes.map((node) => (
                <TreeNode key={node.id} node={node} depth={0} />
              ))}
            </div>
          ))}
        </div>
      )}

      <AccountFormModal
        open={showModal}
        onClose={() => setShowModal(false)}
        onSubmit={handleCreate}
      />
    </div>
  );
}
