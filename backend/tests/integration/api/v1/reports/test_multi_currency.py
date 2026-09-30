"""FR-RPT-152 end to end (Phase 12, T305): a tenant trading in USD and PKR.

No report, dashboard widget or Customer 360 section may add a USD amount
to a PKR amount. Every money aggregate comes back per currency; a single
value field is ``null`` when several currencies are present.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.crm.models.opportunity import Opportunity
from modules.crm.models.pipeline import Pipeline
from modules.crm.models.pipeline_stage import PipelineStage
from modules.crm.repositories.opportunity import OpportunityRepository
from modules.crm.repositories.pipeline import PipelineRepository
from modules.crm.repositories.pipeline_stage import PipelineStageRepository
from modules.purchase.models.cost import PurchaseCostEntry
from tests.integration.api.v1.reports.conftest import (
    create_sales_customer,
    enable_crm_and_installments,
    reports_url,
    seed_sales_invoice,
    setup_company,
)

USD, PKR = Decimal("100.00"), Decimal("5000.00")
CROSS_SUM = USD + PKR


def _seed(db: Session, company_id: uuid.UUID) -> uuid.UUID:
    today = date.today().isoformat()
    customer = create_sales_customer(db, company_id)
    seed_sales_invoice(
        db,
        company_id,
        amount=str(USD),
        customer_id=customer.id,
        invoice_date=today,
        currency_code="USD",
    )
    seed_sales_invoice(
        db,
        company_id,
        amount=str(PKR),
        customer_id=customer.id,
        invoice_date=today,
        currency_code="PKR",
    )
    supplier = str(uuid.uuid4())
    for amount, currency in ((USD, "USD"), (PKR, "PKR")):
        db.add(
            PurchaseCostEntry(
                company_id=company_id,
                gr_id=str(uuid.uuid4()),
                po_id=str(uuid.uuid4()),
                supplier_id=supplier,
                cost_date=date.today(),
                subtotal=amount,
                total_charges=Decimal("0"),
                total_discounts=Decimal("0"),
                tax_amount=Decimal("0"),
                total=amount,
                currency_code=currency,
            )
        )
    pipeline = PipelineRepository(db).create(
        Pipeline(company_id=company_id, name="P", is_default=True)
    )
    stage = PipelineStageRepository(db).create(
        PipelineStage(
            company_id=company_id,
            pipeline_id=pipeline.id,
            name="Open",
            sequence=1,
            probability=50,
        )
    )
    for amount, currency in ((USD, "USD"), (PKR, "PKR")):
        OpportunityRepository(db).create(
            Opportunity(
                company_id=company_id,
                name=f"Opp {currency}",
                customer_id=str(customer.id),
                owner_id=str(uuid.uuid4()),
                pipeline_id=pipeline.id,
                stage_id=stage.id,
                value=amount,
                currency_code=currency,
                probability=50,
                status="OPEN",
            )
        )
    db.commit()
    return customer.id


def _amounts(items: list[dict[str, str]]) -> dict[str | None, Decimal]:
    return {i["currency_code"]: Decimal(i["amount"]) for i in items}


def _get(client: TestClient, token: str, url: str) -> dict[str, Any]:
    resp = client.get(url, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    data: dict[str, Any] = resp.json()["data"]
    return data


def test_no_money_figure_sums_usd_and_pkr(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    enable_crm_and_installments(db_session, company_id)
    customer_id = _seed(db_session, company_id)
    expected = {"USD": USD, "PKR": PKR}

    # Executive Dashboard — money widgets are per currency, single value null.
    dash = _get(test_client, token, reports_url(company_id, "/dashboard"))
    for key in ("net_sales", "gross_sales", "purchase_spend"):
        assert dash[key]["value"] is None, key
        assert _amounts(dash[key]["by_currency"]) == expected, key
    crm = dash["crm_pipeline"]
    assert crm["pipeline_value"] is None
    assert _amounts(crm["pipeline_value_by_currency"]) == expected

    # Sales list aggregate — one row per currency.
    summary = _get(test_client, token, reports_url(company_id, "/sales.summary"))
    assert {r["currency_code"]: Decimal(r["revenue"]) for r in summary["items"]} == (
        expected
    )

    # Sales KPIs — the revenue KPI per currency, in that currency's unit.
    kpis = _get(test_client, token, reports_url(company_id, "/sales.kpis"))
    revenue = {
        block["currency_code"]: next(
            Decimal(k["value"]) for k in block["kpis"] if k["kpi_id"] == "KPI-01"
        )
        for block in kpis["by_currency"]
    }
    assert revenue == expected

    # Purchase by supplier and KPIs.
    by_supplier = _get(
        test_client, token, reports_url(company_id, "/purchase.by_supplier")
    )
    assert {
        r["currency_code"]: Decimal(r["total_spend"]) for r in by_supplier["items"]
    } == expected
    purchase_kpis = _get(test_client, token, reports_url(company_id, "/purchase.kpis"))
    assert "kpi_07_total_purchase_value" not in purchase_kpis
    assert {
        b["currency_code"]: Decimal(b["total_purchase_value"])
        for b in purchase_kpis["by_currency"]
    } == expected

    # CRM pipeline — CRM's report per currency.
    pipeline = _get(test_client, token, reports_url(company_id, "/crm.pipeline"))
    assert {
        b["currency_code"]: sum(
            (Decimal(v["value"]) for v in b["report"]["value_by_stage"]), Decimal("0")
        )
        for b in pipeline["by_currency"]
    } == expected

    # Customer 360 — sales revenue and CRM open value per currency.
    c360 = _get(
        test_client, token, reports_url(company_id, f"/customer-360/{customer_id}")
    )
    assert c360["sales"]["total_revenue"] is None
    assert _amounts(c360["sales"]["total_revenue_by_currency"]) == expected
    assert c360["crm"]["open_opportunity_value"] is None
    assert _amounts(c360["crm"]["open_opportunity_value_by_currency"]) == expected

    # Nowhere does the cross-currency sum appear.
    for payload in (dash, summary, kpis, by_supplier, purchase_kpis, pipeline, c360):
        assert str(CROSS_SUM) not in str(payload)
        assert "5100" not in str(payload)
