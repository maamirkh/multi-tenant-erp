/**
 * Unit tests for AppLayout component.
 *
 * T142 — renders without throwing, renders header/aside/main, passes children.
 *
 * Note: AppLayout renders Sidebar which uses useAuthContext() and usePathname().
 * Both are mocked here to keep the test isolated from auth and routing concerns.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import AppLayout from '@/components/layout/AppLayout';

// Sidebar uses useAuthContext — mock it so AppLayout tests don't need a real provider.
jest.mock('@/contexts/AuthContext', () => ({
  useAuthContext: () => ({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    login: jest.fn(),
    logout: jest.fn(),
  }),
}));

// Sidebar uses usePathname from next/navigation for active route highlighting.
jest.mock('next/navigation', () => ({
  usePathname: () => '/',
}));

describe('AppLayout', () => {
  it('renders without throwing', () => {
    expect(() => render(<AppLayout>content</AppLayout>)).not.toThrow();
  });

  it('renders a header element', () => {
    render(<AppLayout>content</AppLayout>);
    expect(screen.getByRole('banner')).toBeInTheDocument();
  });

  it('renders an aside element', () => {
    render(<AppLayout>content</AppLayout>);
    expect(screen.getByRole('complementary')).toBeInTheDocument();
  });

  it('renders children in the main area', () => {
    render(
      <AppLayout>
        <span>hello world</span>
      </AppLayout>
    );
    expect(screen.getByText('hello world')).toBeInTheDocument();
  });
});
