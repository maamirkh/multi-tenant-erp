/**
 * Phase-13 closure item G — early settlement is now a user-reachable
 * workflow (quote -> display -> execute), backed by the pre-existing
 * idempotency-protected `executeInstallmentSettlement` API function.
 * Proves:
 *   - hidden without installments.settlement.execute;
 *   - the execute form is not rendered until a quote exists;
 *   - execute sends the quote's own quoted_amount/quoted_as_of_date
 *     unchanged (browser never computes the settlement amount) plus a
 *     fresh Idempotency-Key;
 *   - one submit click produces exactly one execute request (no
 *     duplicate financial mutation).
 */

import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import SettlementPage from "@/app/(protected)/(installments)/contracts/[contractId]/settlement/page";

const mockPush = jest.fn();
const mockBack = jest.fn();
jest.mock("next/navigation", () => ({
  useParams: () => ({ contractId: "contract-1" }),
  useRouter: () => ({ push: mockPush, back: mockBack }),
}));

const mockGenerateQuote = jest.fn();
const mockExecuteSettlement = jest.fn();
jest.mock("@/lib/api/installments", () => ({
  generateInstallmentSettlementQuote: (...args: unknown[]) => mockGenerateQuote(...args),
  executeInstallmentSettlement: (...args: unknown[]) => mockExecuteSettlement(...args),
  newIdempotencyKey: () => "test-idempotency-key",
}));

jest.mock("@/components/installments/apiErrors", () => ({
  getCompanyId: () => "company-1",
  classifyInstallmentsError: (err: unknown) => ({
    message: err instanceof Error ? err.message : "error",
    forbidden: false,
    featureDisabled: false,
  }),
}));

const mockUseInstallmentsPermissions = jest.fn();
jest.mock("@/hooks/installments/useInstallmentsPermissions", () => ({
  useInstallmentsPermissions: () => mockUseInstallmentsPermissions(),
  useHasInstallmentsPermission: (
    state: { isReady: boolean; permissions: string[] },
    code: string
  ) => state.isReady && state.permissions.includes(code),
}));

function renderWithClient() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    React.createElement(QueryClientProvider, { client: queryClient }, <SettlementPage />)
  );
}

const mockQuote = {
  contract_id: "contract-1",
  as_of_date: "2026-06-01",
  schedule_outstanding: "800.00",
  late_charge_outstanding: "25.00",
  settlement_amount: "825.00",
  currency_code: "USD",
  early_settlement_policy: null,
};

describe("Early settlement page", () => {
  beforeEach(() => {
    mockGenerateQuote.mockReset();
    mockExecuteSettlement.mockReset();
    mockPush.mockReset();
    mockUseInstallmentsPermissions.mockReset();
    mockUseInstallmentsPermissions.mockReturnValue({
      permissions: ["installments.settlement.execute"],
      isLoading: false,
      isReady: true,
    });
  });

  it("hides the page content without installments.settlement.execute", () => {
    mockUseInstallmentsPermissions.mockReturnValue({
      permissions: [],
      isLoading: false,
      isReady: true,
    });

    renderWithClient();

    expect(
      screen.queryByRole("button", { name: "Generate Settlement Quote" })
    ).not.toBeInTheDocument();
    expect(screen.getByText(/cannot execute an early settlement/i)).toBeInTheDocument();
  });

  it("does not render the execute form until a quote has been generated", () => {
    renderWithClient();

    expect(screen.getByRole("button", { name: "Generate Settlement Quote" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Execute Settlement" })).not.toBeInTheDocument();
  });

  it("displays the quote and sends its exact quoted_amount/quoted_as_of_date on execute, with a fresh Idempotency-Key, exactly once", async () => {
    mockGenerateQuote.mockResolvedValueOnce({ data: mockQuote });
    mockExecuteSettlement.mockResolvedValueOnce({ data: { id: "contract-1", status: "COMPLETED" } });

    renderWithClient();

    fireEvent.click(screen.getByRole("button", { name: "Generate Settlement Quote" }));

    await waitFor(() => expect(screen.getByText("825.00 USD")).toBeInTheDocument());
    expect(mockGenerateQuote).toHaveBeenCalledWith("company-1", "contract-1");

    fireEvent.change(screen.getByPlaceholderText("Cash account UUID"), {
      target: { value: "11111111-1111-1111-1111-111111111111" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Execute Settlement" }));

    await waitFor(() => expect(mockExecuteSettlement).toHaveBeenCalledTimes(1));
    expect(mockExecuteSettlement).toHaveBeenCalledWith(
      "company-1",
      "contract-1",
      {
        quoted_amount: "825.00",
        quoted_as_of_date: "2026-06-01",
        payment_method: "CASH",
        bank_account_id: null,
        cash_account_id: "11111111-1111-1111-1111-111111111111",
      },
      "test-idempotency-key"
    );

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("../contract-1"));
  });

  it("surfaces a stale-quote/backend error via the state banner without crashing", async () => {
    mockGenerateQuote.mockResolvedValueOnce({ data: mockQuote });
    mockExecuteSettlement.mockRejectedValueOnce(new Error("SETTLEMENT_QUOTE_STALE"));

    renderWithClient();

    fireEvent.click(screen.getByRole("button", { name: "Generate Settlement Quote" }));
    await waitFor(() => expect(screen.getByText("825.00 USD")).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText("Cash account UUID"), {
      target: { value: "11111111-1111-1111-1111-111111111111" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Execute Settlement" }));

    await waitFor(() => expect(screen.getByText("SETTLEMENT_QUOTE_STALE")).toBeInTheDocument());
    expect(mockPush).not.toHaveBeenCalled();
  });
});
