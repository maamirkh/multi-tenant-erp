import { PowerOffIcon } from 'lucide-react';
import { StateFrame } from './StateFrame';

/** Reports, or the report's source module, is not enabled for this company. */
export function ModuleDisabledState({
  moduleName,
}: {
  moduleName?: string;
}): React.JSX.Element {
  const subject = moduleName ? `The ${moduleName} module` : 'This module';
  return (
    <StateFrame
      testId="report-state-module-disabled"
      icon={<PowerOffIcon className="size-6" />}
      title="Module not enabled"
      message={`${subject} is not enabled for this company.`}
    />
  );
}
