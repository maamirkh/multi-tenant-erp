/**
 * Phase-13 closure — regression coverage for the BIWEEKLY-frequency
 * defect: the frontend previously offered a `BIWEEKLY` option in three
 * frequency selectors (contracts/new, plans, configuration) that
 * `backend/modules/installments/services/schedule_engine.py`'s
 * `SUPPORTED_FREQUENCIES` does not support, throwing at quote/activation
 * time. `INSTALLMENT_SUPPORTED_FREQUENCIES` is now the single source of
 * truth every selector imports — this test pins it to the exact backend
 * set so a future drift fails here instead of at runtime.
 */
import {
  INSTALLMENT_SUPPORTED_FREQUENCIES,
  InstallmentFrequencySchema,
} from "@/schemas/installments";

describe("INSTALLMENT_SUPPORTED_FREQUENCIES", () => {
  it("matches backend schedule_engine.py's SUPPORTED_FREQUENCIES exactly", () => {
    expect(INSTALLMENT_SUPPORTED_FREQUENCIES).toEqual(["WEEKLY", "MONTHLY", "QUARTERLY"]);
  });

  it("does not include BIWEEKLY", () => {
    expect(INSTALLMENT_SUPPORTED_FREQUENCIES).not.toContain("BIWEEKLY");
  });
});

describe("InstallmentFrequencySchema", () => {
  it.each(INSTALLMENT_SUPPORTED_FREQUENCIES)("accepts %s", (value) => {
    expect(InstallmentFrequencySchema.safeParse(value).success).toBe(true);
  });

  it("rejects BIWEEKLY", () => {
    expect(InstallmentFrequencySchema.safeParse("BIWEEKLY").success).toBe(false);
  });

  it("rejects an arbitrary unsupported value", () => {
    expect(InstallmentFrequencySchema.safeParse("DAILY").success).toBe(false);
  });
});
