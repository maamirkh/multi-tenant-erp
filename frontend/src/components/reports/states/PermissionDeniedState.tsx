import { LockIcon } from 'lucide-react';
import { StateFrame } from './StateFrame';

/** The module is on, but this user lacks the `reports.*` permission. */
export function PermissionDeniedState({
  message = "You don't have permission to view this report. Ask a company administrator for access.",
}: {
  message?: string;
}): React.JSX.Element {
  return (
    <StateFrame
      testId="report-state-permission-denied"
      tone="warning"
      icon={<LockIcon className="size-6" />}
      title="Access restricted"
      message={message}
    />
  );
}
