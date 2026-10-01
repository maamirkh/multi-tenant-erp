'use client';

/**
 * ExportButton (T232) — downloads the report in the **exact filter scope
 * currently on screen** via `exportReport()` → the live
 * `GET /reports/{report_key}/export` route (Phase 6). Offered formats come
 * from the report's discovery entry (`export_formats`); a report with none,
 * or a user without the `.export` permission (which the backend enforces
 * regardless), sees a clear message rather than a silent failure.
 *
 * The backend only returns file bytes after the export's audit record is
 * committed; limit/permission/audit failures come back as the standard error
 * envelope and are shown inline (e.g. "narrow your filters" for
 * `EXPORT_TOO_LARGE`).
 */

import { useState } from 'react';
import { DownloadIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ApiClientError } from '@/lib/api/client';
import {
  exportReport,
  saveExportedFile,
  type ExportFormat,
  type ReportFilters,
} from '@/lib/api/reports';
import { useActiveCompanyId } from '@/hooks/reports/useActiveCompanyId';

const FORMAT_LABELS: Record<ExportFormat, string> = {
  csv: 'CSV',
  xlsx: 'Excel',
  pdf: 'PDF',
};

export function exportErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    switch (error.error.error?.code) {
      case 'EXPORT_TOO_LARGE':
        return 'This export exceeds the synchronous export limit. Narrow your filters and try again.';
      case 'REPORT_PERMISSION_DENIED':
        return "You don't have permission to export this report.";
      case 'EXPORT_AUDIT_FAILED':
        return 'The export could not be recorded, so it was not delivered. Please try again.';
    }
    return error.error.error?.message ?? error.message;
  }
  return error instanceof Error ? error.message : 'Export failed.';
}

export function ExportButton({
  reportKey,
  formats,
  filters,
  sort,
}: {
  reportKey: string;
  formats: ExportFormat[];
  filters?: ReportFilters | undefined;
  sort?: string | null | undefined;
}): React.JSX.Element | null {
  const companyId = useActiveCompanyId();
  const [pending, setPending] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (formats.length === 0) return null;

  const run = async (format: ExportFormat) => {
    setPending(format);
    setError(null);
    try {
      saveExportedFile(await exportReport(companyId, reportKey, format, { filters, sort }));
    } catch (err) {
      setError(exportErrorMessage(err));
    } finally {
      setPending(null);
    }
  };

  return (
    <div className="flex flex-col items-end gap-1">
      <div role="group" aria-label="Export report" className="flex gap-1">
        {formats.map((format) => (
          <Button
            key={format}
            type="button"
            variant="outline"
            size="sm"
            disabled={pending !== null || companyId === ''}
            aria-busy={pending === format || undefined}
            onClick={() => void run(format)}
          >
            <DownloadIcon aria-hidden="true" />
            {pending === format ? 'Exporting…' : `Export ${FORMAT_LABELS[format]}`}
          </Button>
        ))}
      </div>
      {error && (
        <p role="alert" className="max-w-sm text-right text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
