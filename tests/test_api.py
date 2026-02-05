"""API integration tests using mocked MaaS client."""

from __future__ import annotations

from httpx import AsyncClient


async def test_health(async_client: AsyncClient) -> None:
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


async def test_case_lifecycle(async_client: AsyncClient) -> None:
    create = await async_client.post("/api/case/new")
    assert create.status_code == 200
    case_id = create.json()["case_id"]

    fetched = await async_client.get(f"/api/case/{case_id}")
    assert fetched.status_code == 200
    assert fetched.json()["case_id"] == case_id


async def test_chat_flow(async_client: AsyncClient) -> None:
    create = await async_client.post("/api/case/new")
    case_id = create.json()["case_id"]

    chat = await async_client.post(
        f"/api/case/{case_id}/chat",
        data={"message": "I want to import electronics from China"},
    )
    assert chat.status_code == 200
    data = chat.json()
    assert data["procedure"]["id"] == "import-regular"
    assert isinstance(data["messages"], list)


async def test_document_pipeline(async_client: AsyncClient) -> None:
    create = await async_client.post("/api/case/new")
    case_id = create.json()["case_id"]

    files = {
        "files": ("test.png", b"fake-png-bytes", "image/png"),
    }
    uploaded = await async_client.post(
        f"/api/case/{case_id}/docs/upload",
        files=files,
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["total_files"] == 1

    ocr = await async_client.post(f"/api/case/{case_id}/docs/run_ocr")
    assert ocr.status_code == 200

    extracted = await async_client.post(f"/api/case/{case_id}/docs/extract_validate")
    assert extracted.status_code == 200
    assert "validations" in extracted.json()

    risk = await async_client.post(f"/api/case/{case_id}/risk/run")
    assert risk.status_code == 200
    assert "score" in risk.json()
