/**
 * MyPreferencesPage — self-service preferences editing for all authenticated users.
 *
 * Loads preferences via usePreferences(), renders PreferencesForm.
 * Applies stored theme from localStorage on mount before the API response
 * is available (prevents flash of wrong theme).
 *
 * No rank restriction — all authenticated users can edit their own preferences.
 *
 * Spec reference: Epic 4, Phase 13 (T121).
 */

'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { ArrowLeftIcon } from 'lucide-react';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PreferencesForm } from '@/components/users-roles/PreferencesForm';
import { usePreferences } from '@/hooks/users-roles/usePreferences';
import { cn } from '@/lib/utils';
import type { ThemePreference } from '@/types/users-roles';

function PreferencesSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading preferences">
      <div className="h-8 w-48 animate-pulse rounded bg-muted" />
      <div className="h-96 animate-pulse rounded-xl bg-muted" />
    </div>
  );
}

export default function MyPreferencesPage() {
  const { data: preferences, isLoading, isError, error, refetch } = usePreferences();

  // Apply theme from localStorage immediately on mount (before API response).
  useEffect(() => {
    try {
      const stored = localStorage.getItem('erp-theme') as ThemePreference | null;
      if (!stored) return;
      const root = document.documentElement;
      if (stored === 'dark') {
        root.classList.add('dark');
      } else if (stored === 'light') {
        root.classList.remove('dark');
      } else {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        root.classList.toggle('dark', prefersDark);
      }
    } catch {
      // localStorage unavailable — ignore
    }
  }, []);

  // Once API data loads, sync document class with persisted preference.
  useEffect(() => {
    if (!preferences) return;
    const theme = preferences.theme as ThemePreference;
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else if (theme === 'light') {
      root.classList.remove('dark');
    } else {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      root.classList.toggle('dark', prefersDark);
    }
    try {
      localStorage.setItem('erp-theme', theme);
    } catch {
      // localStorage unavailable — ignore
    }
  }, [preferences]);

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
      <h1 className="text-xl font-semibold text-foreground">My Preferences</h1>

      {/* Content */}
      {isLoading && <PreferencesSkeleton />}

      {isError && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
        >
          {error?.message ?? 'Failed to load preferences'}
        </div>
      )}

      {preferences && (
        <Card>
          <CardHeader>
            <CardTitle>Preferences</CardTitle>
          </CardHeader>
          <CardContent>
            <PreferencesForm preferences={preferences} onSuccess={() => void refetch()} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
