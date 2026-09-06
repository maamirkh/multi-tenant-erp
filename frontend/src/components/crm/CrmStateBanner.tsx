import type { CrmErrorState } from "./apiErrors";

/** Renders the appropriate banner for a classified CRM API error. */
export default function CrmStateBanner({ state }: { state: CrmErrorState }) {
  if (state.featureDisabled) {
    return (
      <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-md text-sm text-amber-800">
        CRM is not enabled for this company yet. Ask an administrator to enable it in CRM
        Settings.
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
