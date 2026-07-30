"""Purchase Management module — Epic 6.

The Purchase domain is DevSphere ERP's Procurement Command Centre. It provides
the complete lifecycle management for all supplier-facing procurement activities.

Sub-domains:
  - Supplier Master: Authoritative supplier catalogue, contacts, addresses, ratings
  - Procurement Foundation: Approval engine, purchase policies, number sequencing
  - Purchase Requests: Formal requisition workflow with approval routing
  - Purchase Orders: Legal commitment to supplier with amendment governance
  - Goods Receiving: Immutable goods receipt with Epic 5 stock integration
  - Vendor Returns: Supplier return management and credit note readiness
  - Purchase Costing: PPV tracking, additional charges, landed cost readiness
  - Purchase Intelligence: Reporting, KPIs, supplier performance analytics

Spec ref: specs/006-purchase-management/spec.md (v1.0)
Plan ref: specs/006-purchase-management/plan.md
"""
