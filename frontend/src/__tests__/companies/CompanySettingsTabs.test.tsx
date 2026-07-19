/**
 * T096 — CompanySettingsTabs component tests.
 *
 * Tests:
 * - Active tab is highlighted based on current pathname.
 * - Each tab links to the correct route.
 * - Non-active tabs do not carry aria-selected="true".
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { CompanySettingsTabs } from '@/components/companies/CompanySettingsTabs';

// ── Mocks ─────────────────────────────────────────────────────────────────────

const mockUsePathname = jest.fn<string, []>();

jest.mock('next/navigation', () => ({
  usePathname: () => mockUsePathname(),
}));

// next/link renders as a plain <a> in tests
jest.mock('next/link', () => {
  const MockLink = ({ href, children, ...rest }: { href: string; children: React.ReactNode; [key: string]: unknown }) => (
    <a href={href} {...rest}>{children}</a>
  );
  MockLink.displayName = 'MockLink';
  return MockLink;
});

// ── Tests ─────────────────────────────────────────────────────────────────────

const COMPANY_ID = 'abc-123';

describe('CompanySettingsTabs', () => {
  it('renders all four tabs', () => {
    mockUsePathname.mockReturnValue(`/companies/${COMPANY_ID}/settings/profile`);

    render(<CompanySettingsTabs companyId={COMPANY_ID} />);

    expect(screen.getByText('Profile')).toBeInTheDocument();
    expect(screen.getByText('Regional')).toBeInTheDocument();
    expect(screen.getByText('Branding')).toBeInTheDocument();
    expect(screen.getByText('Preferences')).toBeInTheDocument();
  });

  it('marks the Profile tab as active on the profile route', () => {
    mockUsePathname.mockReturnValue(`/companies/${COMPANY_ID}/settings/profile`);

    render(<CompanySettingsTabs companyId={COMPANY_ID} />);

    const profileTab = screen.getByText('Profile').closest('[role="tab"]');
    expect(profileTab).toHaveAttribute('aria-selected', 'true');

    const regionalTab = screen.getByText('Regional').closest('[role="tab"]');
    expect(regionalTab).toHaveAttribute('aria-selected', 'false');
  });

  it('marks the Regional tab as active on the regional route', () => {
    mockUsePathname.mockReturnValue(`/companies/${COMPANY_ID}/settings/regional`);

    render(<CompanySettingsTabs companyId={COMPANY_ID} />);

    const regionalTab = screen.getByText('Regional').closest('[role="tab"]');
    expect(regionalTab).toHaveAttribute('aria-selected', 'true');

    const profileTab = screen.getByText('Profile').closest('[role="tab"]');
    expect(profileTab).toHaveAttribute('aria-selected', 'false');
  });

  it('marks the Branding tab as active on the branding route', () => {
    mockUsePathname.mockReturnValue(`/companies/${COMPANY_ID}/settings/branding`);

    render(<CompanySettingsTabs companyId={COMPANY_ID} />);

    const brandingTab = screen.getByText('Branding').closest('[role="tab"]');
    expect(brandingTab).toHaveAttribute('aria-selected', 'true');
  });

  it('marks the Preferences tab as active on the preferences route', () => {
    mockUsePathname.mockReturnValue(`/companies/${COMPANY_ID}/settings/preferences`);

    render(<CompanySettingsTabs companyId={COMPANY_ID} />);

    const prefsTab = screen.getByText('Preferences').closest('[role="tab"]');
    expect(prefsTab).toHaveAttribute('aria-selected', 'true');
  });

  it('each tab links to the correct route', () => {
    mockUsePathname.mockReturnValue(`/companies/${COMPANY_ID}/settings/profile`);

    render(<CompanySettingsTabs companyId={COMPANY_ID} />);

    expect(screen.getByText('Profile').closest('a')).toHaveAttribute(
      'href',
      `/companies/${COMPANY_ID}/settings/profile`
    );
    expect(screen.getByText('Regional').closest('a')).toHaveAttribute(
      'href',
      `/companies/${COMPANY_ID}/settings/regional`
    );
    expect(screen.getByText('Branding').closest('a')).toHaveAttribute(
      'href',
      `/companies/${COMPANY_ID}/settings/branding`
    );
    expect(screen.getByText('Preferences').closest('a')).toHaveAttribute(
      'href',
      `/companies/${COMPANY_ID}/settings/preferences`
    );
  });

  it('no tab is active when pathname does not match any segment', () => {
    mockUsePathname.mockReturnValue(`/companies/${COMPANY_ID}`);

    render(<CompanySettingsTabs companyId={COMPANY_ID} />);

    const tabs = screen.getAllByRole('tab');
    for (const tab of tabs) {
      expect(tab).toHaveAttribute('aria-selected', 'false');
    }
  });
});
