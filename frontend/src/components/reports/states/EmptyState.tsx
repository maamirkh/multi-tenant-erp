import { InboxIcon } from 'lucide-react';
import { StateFrame } from './StateFrame';

/** The report ran and legitimately returned no rows for this filter scope. */
export function EmptyState({
  title = 'No data for this selection',
  message = 'Try a different period or widen your filters.',
}: {
  title?: string;
  message?: string;
}): React.JSX.Element {
  return (
    <StateFrame
      testId="report-state-empty"
      icon={<InboxIcon className="size-6" />}
      title={title}
      message={message}
    />
  );
}
