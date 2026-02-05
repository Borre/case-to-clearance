"""Test fixtures for API and workflow tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.config import settings
from app.main import app
from app.storage import storage


class FakeMaaSClient:
    """Fake MaaS client for deterministic test responses."""

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        system = messages[0]["content"] if messages else ""

        if "procedure_id" in system:
            content = (
                '{"procedure_id":"import-regular","procedure_name":"Regular Import",'
                '"confidence":0.9,"rationale":"Matched import intent.",'
                '"detected_fields":{},"missing_fields":["tax_id"]}'
            )
        elif "document type classifier" in system.lower():
            content = (
                '{"doc_type":"invoice","confidence":0.9,"rationale":"Invoice keywords found."}'
            )
        elif "commercial invoices" in system.lower():
            content = (
                '{"fields":{"invoice_number":"INV-1","invoice_date":"2025-01-15",'
                '"supplier_name":"ACME","buyer_name":"Buyer","total_amount":"1000",'
                '"currency":"USD","shipment_id":"S-1","hs_codes":["8471.30"],'
                '"line_items":"1 item"},"confidence":0.8,'
                '"low_confidence_fields":[],"missing_fields":[]}'
            )
        elif "bills of lading" in system.lower():
            content = (
                '{"fields":{"bl_number":"BL-1","bl_date":"2025-01-16","carrier_name":"Carrier",'
                '"vessel_name":"Vessel","voyage_number":"V-1","port_of_loading":"Lima",'
                '"port_of_discharge":"Callao","shipper_name":"Shipper","consignee_name":"Consignee",'
                '"notify_party":"Notify","cargo_description":"Electronics","gross_weight":"1000 kg"},'
                '"confidence":0.8,"low_confidence_fields":[],"missing_fields":[]}'
            )
        elif "packing lists" in system.lower():
            content = (
                '{"fields":{"pl_number":"PL-1","pl_date":"2025-01-16","shipper_name":"Shipper",'
                '"consignee_name":"Consignee","total_packages":"10","package_type":"Cartons",'
                '"total_weight":"100 kg","total_volume":"1 cbm","marks_numbers":"MARKS",'
                '"item_summary":"10 cartons"},"confidence":0.8,'
                '"low_confidence_fields":[],"missing_fields":[]}'
            )
        elif "customs declarations" in system.lower():
            content = (
                '{"fields":{"declaration_number":"DEC-1","declaration_date":"2025-01-17",'
                '"declarant_name":"Declarant","tax_id":"20601234567","procedure_code":"IMP",'
                '"declared_value":"1000","currency":"USD","origin_countries":["CN"],'
                '"hs_codes":["8471.30"],"goods_description":"Electronics","warehouse":"WH-1",'
                '"shipment_id":"S-1","bl_number":"BL-1"},"confidence":0.8,'
                '"low_confidence_fields":[],"missing_fields":[]}'
            )
        elif "risk communication specialist" in system.lower() or "risk analysis" in system.lower():
            content = (
                '{"executive_summary":"Risk assessment complete. Please review the case carefully. '
                'This is advisory only and requires official review.","explanation_bullets":'
                '["[no_factors]: No risk factors were triggered."],'
                '"recommended_next_actions":["Review submitted documents for completeness."],'
                '"risk_reduction_actions":["Provide any missing documents."]}'
            )
        else:
            content = '{"fields":{},"confidence":0.5,"low_confidence_fields":[],"missing_fields":[]}'

        return {
            "content": content,
            "model": model or "fake",
            "usage": {},
            "finish_reason": "stop",
            "duration_ms": 0,
        }

    async def close(self) -> None:
        return None


@pytest.fixture(autouse=True)
def configure_test_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings.app_env = str(tmp_path / "test_env")
    Path(settings.app_env).joinpath("runs").mkdir(parents=True, exist_ok=True)
    Path(settings.app_env).joinpath("logs").mkdir(parents=True, exist_ok=True)
    storage.base_dir = Path(settings.app_env).joinpath("runs")

    # Monkeypatch MaaS client
    import app.huawei.maas as maas_mod
    import app.chains.intake as intake_mod
    import app.chains.extraction as extraction_mod
    import app.chains.triage as triage_mod
    import app.chains.json_fix as json_fix_mod

    fake_client = FakeMaaSClient()

    def _fake_get_client() -> FakeMaaSClient:
        return fake_client

    monkeypatch.setattr(maas_mod, "get_maas_client", _fake_get_client)
    maas_mod._maas_client = fake_client

    # Reset chain singletons to pick up patched MaaS client
    intake_mod._intake_chain = None
    extraction_mod._extraction_chain = None
    triage_mod._triage_chain = None
    json_fix_mod._json_fix_chain = None


@pytest.fixture
async def async_client() -> AsyncClient:
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
