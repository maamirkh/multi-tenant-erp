'use client';

/**
 * T194 — Plans page. Requires `platform.plans.read`; management actions
 * (create/publish/retire) gated on `platform.plans.manage` server-side.
 * Retire is a destructive transition and is explicitly confirmed.
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listPlans, createPlan, updatePlan, type Plan } from '@/lib/api/platform-admin';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { ConfirmDialog } from '@/components/platform-admin/dialogs';
import {
  LoadingState,
  ErrorState,
  EmptyState,
  PermissionDeniedState,
  messageFromError,
  isForbidden,
} from '@/components/platform-admin/DataState';

function CreatePlanDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}): React.JSX.Element {
  const queryClient = useQueryClient();
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => createPlan({ code, name, description: description || null }),
    onSuccess: () => {
      setCode('');
      setName('');
      setDescription('');
      void queryClient.invalidateQueries({ queryKey: ['platform', 'plans'] });
      onClose();
    },
    onError: (err) => setError(messageFromError(err)),
  });

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create Plan</DialogTitle>
          <DialogDescription>Creates a new plan in draft status.</DialogDescription>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setError(null);
            mutation.mutate();
          }}
          noValidate
          className="space-y-3"
        >
          {error && (
            <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <div>
            <label htmlFor="plan_code" className="mb-1 block text-sm font-medium">Code</label>
            <Input id="plan_code" required value={code} onChange={(e) => setCode(e.target.value)} />
          </div>
          <div>
            <label htmlFor="plan_name" className="mb-1 block text-sm font-medium">Name</label>
            <Input id="plan_name" required value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label htmlFor="plan_description" className="mb-1 block text-sm font-medium">Description</label>
            <Input id="plan_description" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={mutation.isPending}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? 'Creating…' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function PlatformPlansPage(): React.JSX.Element {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [retireTarget, setRetireTarget] = useState<Plan | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['platform', 'plans'],
    queryFn: () => listPlans({ page: 1, page_size: 100 }),
  });

  const transitionMutation = useMutation({
    mutationFn: ({ planId, action }: { planId: string; action: 'publish' | 'retire' }) =>
      updatePlan(planId, { action }),
    onSuccess: () => {
      setRetireTarget(null);
      void queryClient.invalidateQueries({ queryKey: ['platform', 'plans'] });
    },
    onError: (err) => setActionError(messageFromError(err)),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Plans</h1>
          <p className="text-sm text-muted-foreground">Configuration-driven commercial plans.</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>New Plan</Button>
      </div>

      {actionError && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {actionError}
        </div>
      )}

      {isLoading && <LoadingState />}
      {isError && isForbidden(error) && <PermissionDeniedState />}
      {isError && !isForbidden(error) && (
        <ErrorState message={messageFromError(error)} onRetry={() => void refetch()} />
      )}

      {data && data.items.length === 0 && <EmptyState message="No plans configured yet." />}

      {data && data.items.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="p-3">Code</th>
                <th className="p-3">Name</th>
                <th className="p-3">Status</th>
                <th className="p-3">Available</th>
                <th className="p-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((plan) => (
                <tr key={plan.id} className="border-t border-border">
                  <td className="p-3">{plan.code}</td>
                  <td className="p-3">{plan.name}</td>
                  <td className="p-3">{plan.status}</td>
                  <td className="p-3">{plan.is_commercially_available ? 'Yes' : 'No'}</td>
                  <td className="p-3">
                    <div className="flex gap-2">
                      {plan.status === 'draft' && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setActionError(null);
                            transitionMutation.mutate({ planId: plan.id, action: 'publish' });
                          }}
                          disabled={transitionMutation.isPending}
                        >
                          Publish
                        </Button>
                      )}
                      {plan.status !== 'retired' && (
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => setRetireTarget(plan)}
                          disabled={transitionMutation.isPending}
                        >
                          Retire
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <CreatePlanDialog open={showCreate} onClose={() => setShowCreate(false)} />

      <ConfirmDialog
        open={retireTarget !== null}
        title="Retire Plan"
        description={`Retire ${retireTarget?.name ?? ''}? Tenants can no longer be assigned this plan.`}
        submitLabel="Retire"
        variant="destructive"
        onClose={() => setRetireTarget(null)}
        onConfirm={() => {
          if (retireTarget) {
            setActionError(null);
            transitionMutation.mutate({ planId: retireTarget.id, action: 'retire' });
          }
        }}
        isPending={transitionMutation.isPending}
      />
    </div>
  );
}
