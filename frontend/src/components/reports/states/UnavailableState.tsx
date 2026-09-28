import { CircleSlashIcon } from 'lucide-react';
import { StateFrame } from './StateFrame';

/**
 * A prerequisite isn't set up yet (e.g. no chart of accounts) —
 * `REPORT_UNAVAILABLE`. Deliberately distinct from Empty: an unavailable
 * figure must never read as a zero.
 */
export function UnavailableState({
  message = 'This report is not available yet — a required setup step has not been completed.',
}: {
  message?: string;
}): React.JSX.Element {
  return (
    <StateFrame
      testId="report-state-unavailable"
      tone="warning"
      icon={<CircleSlashIcon className="size-6" />}
      title="Not available yet"
      message={message}
    />
  );
}
