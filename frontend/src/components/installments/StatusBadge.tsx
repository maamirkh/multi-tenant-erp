const INSTALLMENT_STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-600",
  PENDING_APPROVAL: "bg-amber-100 text-amber-700",
  APPROVED: "bg-blue-100 text-blue-700",
  ACTIVE: "bg-green-100 text-green-700",
  DEFAULTED: "bg-red-100 text-red-700",
  COMPLETED: "bg-teal-100 text-teal-700",
  CANCELLED: "bg-gray-100 text-gray-600",
  WRITTEN_OFF: "bg-red-100 text-red-800",
};

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
        INSTALLMENT_STATUS_COLORS[status] ?? "bg-gray-100 text-gray-700"
      }`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
