/**
 * T234 — InstallmentsStateBanner component tests. Verifies the correct
 * variant renders for FEATURE_DISABLED vs. ordinary 403 vs. generic
 * error (mirrors `classifyInstallmentsError`'s three-state contract).
 */

import { render, screen } from '@testing-library/react';
import InstallmentsStateBanner from '@/components/installments/InstallmentsStateBanner';

describe('T234 — InstallmentsStateBanner', () => {
  it('renders the feature-disabled variant when featureDisabled is true', () => {
    render(
      <InstallmentsStateBanner
        state={{ message: 'ignored', forbidden: true, featureDisabled: true }}
      />
    );
    expect(screen.getByText(/installments is not enabled for this company/i)).toBeInTheDocument();
    expect(screen.queryByText(/you do not have permission/i)).not.toBeInTheDocument();
  });

  it('renders the forbidden variant when forbidden is true and featureDisabled is false', () => {
    render(
      <InstallmentsStateBanner
        state={{ message: 'Missing installments.contract.approve', forbidden: true, featureDisabled: false }}
      />
    );
    expect(screen.getByText(/you do not have permission to do this/i)).toBeInTheDocument();
    expect(screen.getByText(/missing installments\.contract\.approve/i)).toBeInTheDocument();
    expect(screen.queryByText(/installments is not enabled/i)).not.toBeInTheDocument();
  });

  it('renders the generic error variant for any other error', () => {
    render(
      <InstallmentsStateBanner
        state={{ message: 'Contract not found', forbidden: false, featureDisabled: false }}
      />
    );
    expect(screen.getByText('Contract not found')).toBeInTheDocument();
    expect(screen.queryByText(/you do not have permission/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/installments is not enabled/i)).not.toBeInTheDocument();
  });
});
