export default function KpiTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-gray-200 rounded-md p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-semibold text-gray-900 mt-1">{value}</div>
    </div>
  );
}
