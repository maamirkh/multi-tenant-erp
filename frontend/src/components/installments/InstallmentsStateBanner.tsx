import type { InstallmentsErrorState } from "./apiErrors";

/** Renders the appropriate banner for a classified Installments API error.
 * Mirrors `crm/CrmStateBanner.tsx` exactly. */
export default function InstallmentsStateBanner({ state }: { state: InstallmentsErrorState }) {
  if (state.featureDisabled) {
    return (
      <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-md text-sm text-amber-800">
        Installments is not enabled for this company yet. Existing contracts remain fully
        serviceable; ask an administrator to enable it to originate new contracts.
      </div>
    );
  }
  if (state.forbidden) {
    return (
      <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
        You do not have permission to do this. {state.message}
      </div>
    );
  }
  return (
    <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
      {state.message}
    </div>
  );
}
