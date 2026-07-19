/**
 * MyProfilePage — self-service profile editing for all authenticated users.
 *
 * Loads the current user's profile via useProfile(), renders ProfileForm.
 * No rank restriction — all authenticated users can edit their own profile.
 *
 * Spec reference: Epic 4, Phase 13 (T120).
 */

'use client';

import Link from 'next/link';
import { ArrowLeftIcon } from 'lucide-react';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ProfileForm } from '@/components/users-roles/ProfileForm';
import { useProfile } from '@/hooks/users-roles/useProfile';
import { cn } from '@/lib/utils';

function ProfileSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading profile">
      <div className="h-8 w-48 animate-pulse rounded bg-muted" />
      <div className="h-96 animate-pulse rounded-xl bg-muted" />
    </div>
  );
}

export default function MyProfilePage() {
  const { data: profile, isLoading, isError, error, refetch } = useProfile();

  return (
    <div className="space-y-6">
      {/* Navigation */}
      <Link
        href="/dashboard"
        aria-label="Back to dashboard"
        className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'gap-1.5')}
      >
        <ArrowLeftIcon className="size-4" />
        Dashboard
      </Link>

      {/* Header */}
      <h1 className="text-xl font-semibold text-foreground">My Profile</h1>

      {/* Content */}
      {isLoading && <ProfileSkeleton />}

      {isError && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
        >
          {error?.message ?? 'Failed to load profile'}
        </div>
      )}

      {profile && (
        <Card>
          <CardHeader>
            <CardTitle>Profile</CardTitle>
          </CardHeader>
          <CardContent>
            <ProfileForm profile={profile} onSuccess={() => void refetch()} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
