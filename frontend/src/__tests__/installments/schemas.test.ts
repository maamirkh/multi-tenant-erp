/**
 * Phase-13 closure — zod schema regression coverage for the confirmed
 * schema-drift/validation-gap defects (items I and J of the closure
 * spec):
 *
 *   I: `InstallmentPlanTemplateSchema` previously modeled flat
 *   `down_payment_type`/`down_payment_value` fields that don't exist on
 *   the backend's `InstallmentPlanTemplateCreate` at all — the real
 *   field is an opaque `down_payment_rule: dict`
 *   (`backend/modules/installments/schemas/plan_template.py`). The page
 *   manually reshaped the fictional fields into the real one before
 *   every request, masking the drift. The schema now nests
 *   `down_payment_rule` directly, matching exactly what's sent.
 *
 *   J: `InstallmentCollectionCreateSchema.amount` previously allowed "0"
 *   client-side while the backend requires `amount: Decimal = Field(...,
 *   gt=0)` (`backend/modules/installments/schemas/collection.py`) — the
 *   only client feedback was a round-trip to a 422.
 */
import {
  InstallmentCollectionCreateSchema,
  InstallmentPlanTemplateSchema,
  positiveDecimalString,
} from "@/schemas/installments";

describe("positiveDecimalString", () => {
  it("rejects zero", () => {
    expect(positiveDecimalString.safeParse("0").success).toBe(false);
    expect(positiveDecimalString.safeParse("0.00").success).toBe(false);
  });

  it("rejects a value that doesn't parse as a positive decimal at all (negative sign not in the base pattern)", () => {
    expect(positiveDecimalString.safeParse("-5").success).toBe(false);
  });

  it("accepts a valid positive decimal", () => {
    expect(positiveDecimalString.safeParse("0.01").success).toBe(true);
    expect(positiveDecimalString.safeParse("100").success).toBe(true);
    expect(positiveDecimalString.safeParse("1500.75").success).toBe(true);
  });
});

describe("InstallmentCollectionCreateSchema", () => {
  const base = {
    payment_method: "CASH",
    bank_account_id: "",
    cash_account_id: "11111111-1111-1111-1111-111111111111",
  };

  it("rejects a zero collection amount", () => {
    const result = InstallmentCollectionCreateSchema.safeParse({ ...base, amount: "0" });
    expect(result.success).toBe(false);
  });

  it("rejects a negative collection amount", () => {
    const result = InstallmentCollectionCreateSchema.safeParse({ ...base, amount: "-10" });
    expect(result.success).toBe(false);
  });

  it("accepts a valid positive collection amount", () => {
    const result = InstallmentCollectionCreateSchema.safeParse({ ...base, amount: "250.00" });
    expect(result.success).toBe(true);
  });
});

describe("InstallmentPlanTemplateSchema", () => {
  const base = {
    name: "Standard 12-Month",
    frequency: "MONTHLY",
    installment_count: 12,
  };

  it("rejects the old, no-longer-real down_payment_type/down_payment_value shape", () => {
    const result = InstallmentPlanTemplateSchema.safeParse({
      ...base,
      down_payment_type: "PERCENTAGE",
      down_payment_value: "10",
    });
    expect(result.success).toBe(false);
  });

  it("accepts the actual backend request shape: a nested down_payment_rule object", () => {
    const result = InstallmentPlanTemplateSchema.safeParse({
      ...base,
      down_payment_rule: { type: "PERCENTAGE", amount: "10" },
    });
    expect(result.success).toBe(true);
    if (result.success) {
      // Proves the parsed value round-trips as exactly what the request
      // body needs — no page-level reshape required.
      expect(result.data.down_payment_rule).toEqual({ type: "PERCENTAGE", amount: "10" });
    }
  });

  it("rejects an unknown down_payment_rule.type", () => {
    const result = InstallmentPlanTemplateSchema.safeParse({
      ...base,
      down_payment_rule: { type: "BOGUS", amount: "10" },
    });
    expect(result.success).toBe(false);
  });
});
