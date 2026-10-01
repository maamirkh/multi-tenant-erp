import { AlertTriangleIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { StateFrame } from './StateFrame';

/** An unexpected failure — distinct from "no data" and from "not allowed". */
export function ErrorState({
  message = 'The report could not be loaded.',
  onRetry,
}: {
  message?: string | undefined;
  onRetry?: (() => void) | undefined;
}): React.JSX.Element {
  return (
    <StateFrame
      testId="report-state-error"
      role="alert"
      tone="danger"
      icon={<AlertTriangleIcon className="size-6" />}
      title="Something went wrong"
      message={message}
      action={
        onRetry ? (
          <Button type="button" variant="outline" size="sm" onClick={onRetry}>
            Try again
          </Button>
        ) : undefined
      }
    />
  );
}
