"use client";

/**
 * Supplier status badge + lifecycle action buttons.
 * Task: T046
 */

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  ACTIVE: "bg-green-100 text-green-800",
  INACTIVE: "bg-yellow-100 text-yellow-800",
  BLOCKED: "bg-red-100 text-red-800",
  ARCHIVED: "bg-slate-100 text-slate-600",
};

const STATUS_LABELS: Record<string, string> = {
  DRAFT: "Draft",
  ACTIVE: "Active",
  INACTIVE: "Inactive",
  BLOCKED: "Blocked",
  ARCHIVED: "Archived",
};

interface SupplierStatusBadgeProps {
  status: string;
}

export function SupplierStatusBadge({ status }: SupplierStatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[status] ?? "bg-gray-100 text-gray-600"}`}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

interface SupplierLifecycleActionsProps {
  status: string;
  onActivate?: () => void;
  onDeactivate?: () => void;
  onBlock?: () => void;
  onReactivate?: () => void;
  onArchive?: () => void;
  disabled?: boolean;
}

export function SupplierLifecycleActions({
  status,
  onActivate,
  onDeactivate,
  onBlock,
  onReactivate,
  onArchive,
  disabled = false,
}: SupplierLifecycleActionsProps) {
  const btn =
    "px-3 py-1.5 rounded text-sm font-medium disabled:opacity-50 transition-colors";

  return (
    <div className="flex gap-2 flex-wrap">
      {status === "DRAFT" && onActivate && (
        <button
          onClick={onActivate}
          disabled={disabled}
          className={`${btn} bg-green-600 text-white hover:bg-green-700`}
        >
          Activate
        </button>
      )}
      {status === "ACTIVE" && (
        <>
          {onDeactivate && (
            <button
              onClick={onDeactivate}
              disabled={disabled}
              className={`${btn} bg-yellow-500 text-white hover:bg-yellow-600`}
            >
              Deactivate
            </button>
          )}
          {onBlock && (
            <button
              onClick={onBlock}
              disabled={disabled}
              className={`${btn} bg-red-600 text-white hover:bg-red-700`}
            >
              Block
            </button>
          )}
          {onArchive && (
            <button
              onClick={onArchive}
              disabled={disabled}
              className={`${btn} border border-gray-300 text-gray-700 hover:bg-gray-50`}
            >
              Archive
            </button>
          )}
        </>
      )}
      {(status === "INACTIVE" || status === "BLOCKED") && onReactivate && (
        <button
          onClick={onReactivate}
          disabled={disabled}
          className={`${btn} bg-green-600 text-white hover:bg-green-700`}
        >
          Reactivate
        </button>
      )}
      {status === "INACTIVE" && onArchive && (
        <button
          onClick={onArchive}
          disabled={disabled}
          className={`${btn} border border-gray-300 text-gray-700 hover:bg-gray-50`}
        >
          Archive
        </button>
      )}
    </div>
  );
}
