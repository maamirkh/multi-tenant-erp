"""Installments module.

Epic 10 — Deferred-payment installment sale contracts: schedule
generation, contract lifecycle (draft -> approval -> activation ->
servicing -> completion/default/cancellation/write-off), collection and
allocation tracking, late charges, and early settlement — layered on top
of Accounting as the sole financial source of truth. No shadow financial
balances are ever stored here; every authoritative amount is read live
from Accounting (ADR-INST-01).

Spec ref: specs/010-installments/spec.md, specs/010-installments/plan.md
"""
