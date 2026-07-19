import { Button } from '@/components/ui/button';

export default function Home() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          DevSphere ERP &mdash; Foundation Platform
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Foundation Platform is ready. ERP modules will appear here as they are built.
        </p>
      </div>

      <div className="flex items-center gap-3">
        <Button variant="default">Get Started</Button>
        <Button variant="outline">Learn More</Button>
      </div>

      <div className="rounded-lg border border-border bg-card p-4 text-sm text-card-foreground">
        <p className="font-medium">Status</p>
        <p className="mt-1 text-muted-foreground">
          Backend API:{' '}
          <span className="font-mono">
            {process.env['NEXT_PUBLIC_API_URL'] ?? 'http://localhost:8000'}
          </span>
        </p>
      </div>
    </div>
  );
}
