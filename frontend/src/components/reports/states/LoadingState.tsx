/** Loading placeholder shared by Reports pages (Constitution §23's loading state). */
export function LoadingState({ label = 'Loading report…' }: { label?: string }): React.JSX.Element {
  return (
    <div className="flex h-32 items-center justify-center gap-2 text-sm text-muted-foreground">
      <span
        className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent"
        role="status"
        aria-label={label}
      />
      {label}
    </div>
  );
}
