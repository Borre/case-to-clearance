"""FastAPI application for Case-to-Clearance demo."""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, UploadFile, Form, File, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.chains.workflow import run_workflow
from app.config import settings
from app.observability.tracer import app_logger
from app.storage import CaseFile, storage

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Case-to-Clearance: Single Window Copilot",
    description="AI-powered customs clearance assistant for tax/customs authorities",
    version="0.1.0",
)

# ============================================================================
# MIDDLEWARE AND ERROR HANDLERS
# ============================================================================

from app.middleware.error_handlers import add_error_handlers
from app.middleware.rate_limiting import SlidingWindowRateLimiter

# Add error handlers
add_error_handlers(app)

# Add rate limiting (only in production, or if enabled)
if settings.app_env == "production":
    app.add_middleware(SlidingWindowRateLimiter)

# ============================================================================
# MOUNT STATIC AND TEMPLATES
# ============================================================================

ui_dir = Path(__file__).parent.joinpath("ui")
templates = Jinja2Templates(directory=ui_dir.joinpath("templates"))

app.mount("/static", StaticFiles(directory=ui_dir.joinpath("static")), name="static")

# ============================================================================
# HEALTH CHECK
# ============================================================================


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


# ============================================================================
# UI ROUTES
# ============================================================================


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    """Redirect to UI."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/ui")


@app.get("/ui", response_class=HTMLResponse)
async def ui_index(request: Request) -> HTMLResponse:
    """Main UI page."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "case_id": None,
            "disclaimer": settings.disclaimer,
        },
    )


@app.get("/ui/case/{case_id}", response_class=HTMLResponse)
async def ui_case(request: Request, case_id: str) -> HTMLResponse:
    """Case detail UI page."""
    case = storage.load(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    return templates.TemplateResponse(
        request=request,
        name="case_view.html",
        context={
            "case": case.model_dump(),
            "case_id": case_id,
            "disclaimer": settings.disclaimer,
        },
    )


# ============================================================================
# API ROUTES: CASE MANAGEMENT
# ============================================================================


@app.post("/api/case/new")
async def create_case() -> dict[str, str]:
    """Create a new case."""
    case = CaseFile()
    storage.save(case)

    app_logger.info(f"Created new case: {case.case_id}")

    return {"case_id": case.case_id}


@app.get("/api/case/{case_id}")
async def get_case(case_id: str) -> dict[str, Any]:
    """Get case details."""
    case = storage.load(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    return case.model_dump()


# ============================================================================
# API ROUTES: CITIZEN INTAKE (CHAT)
# ============================================================================


@app.post("/api/case/{case_id}/chat")
async def chat(case_id: str, message: str = Form(...)) -> dict[str, Any]:
    """Send a chat message and get response."""
    if not storage.exists(case_id):
        raise HTTPException(status_code=404, detail="Case not found")

    state = await run_workflow(
        case_id=case_id,
        steps={"intake": True},
        message=message,
    )
    case = state["case"]
    result = state.get("intake_result", {})
    assistant_message = result.get(
        "response", "I'm sorry, I couldn't process that request."
    )

    return {
        "case_id": case_id,
        "procedure": case.procedure,
        "collected_fields": case.citizen_intake.get("collected_fields", {}),
        "missing_fields": case.citizen_intake.get("missing_fields", []),
        "response": assistant_message,
        "messages": case.citizen_intake.get("messages", []),
    }


# ============================================================================
# API ROUTES: DOCUMENT PROCESSING
# ============================================================================


@app.post("/api/case/{case_id}/docs/upload")
async def upload_documents(case_id: str, files: list[UploadFile] = File(...)) -> dict[str, Any]:
    """Upload documents for a case."""
    case = storage.load(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.initialize_documents()

    uploaded_files = []
    case_dir = Path(settings.app_env).joinpath("runs", case_id)
    case_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        # Validate file
        if not file.filename:
            continue

        ext = Path(file.filename).suffix.lower()
        if ext not in settings.allowed_extensions_set:
            continue

        # Read file
        content = await file.read()

        # Save to disk
        doc_id = f"doc-{uuid.uuid4().hex[:12]}"
        file_path = case_dir.joinpath(f"{doc_id}_{file.filename}")
        with file_path.open("wb") as f:
            f.write(content)

        # Add to case
        file_info = {
            "doc_id": doc_id,
            "filename": file.filename,
            "mime": file.content_type or "application/octet-stream",
            "size": len(content),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "path": f"{doc_id}_{file.filename}",  # Store just the filename, not full path
        }
        case.documents["files"].append(file_info)
        uploaded_files.append(file_info)

    storage.save(case)

    app_logger.info(f"Uploaded {len(uploaded_files)} files for case {case_id}")

    return {
        "case_id": case_id,
        "uploaded": uploaded_files,
        "total_files": len(case.documents.get("files", [])),
    }


@app.post("/api/case/{case_id}/docs/run_ocr")
async def run_ocr(case_id: str) -> dict[str, Any]:
    """Run OCR on uploaded documents."""
    if not storage.exists(case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    state = await run_workflow(case_id=case_id, steps={"ocr": True})
    ocr_results = state.get("ocr_results", [])

    return {
        "case_id": case_id,
        "ocr_results": ocr_results,
        "total_docs": len(ocr_results),
    }


@app.post("/api/case/{case_id}/docs/extract_validate")
async def extract_and_validate(case_id: str) -> dict[str, Any]:
    """Extract fields and run validations."""
    if not storage.exists(case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    state = await run_workflow(case_id=case_id, steps={"extract_validate": True})
    case = state["case"]
    validations = state.get("validations", [])

    return {
        "case_id": case_id,
        "extractions": case.documents.get("extractions", []),
        "validations": validations,
        "summary": {
            "total_docs": len(case.documents.get("ocr", [])),
            "extractions": len(case.documents.get("extractions", [])),
            "validations_failed": sum(1 for v in validations if not v.get("passed", True)),
            "validations_passed": sum(1 for v in validations if v.get("passed", True)),
        },
    }


# ============================================================================
# API ROUTES: RISK ASSESSMENT
# ============================================================================


@app.post("/api/case/{case_id}/risk/run")
async def run_risk_assessment(case_id: str) -> dict[str, Any]:
    """Compute risk score and generate explanation."""
    if not storage.exists(case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    state = await run_workflow(case_id=case_id, steps={"risk": True})
    result = state["case"].risk

    return {
        "case_id": case_id,
        **result,
    }


# ============================================================================
# STARTUP AND SHUTDOWN
# ============================================================================


@app.on_event("startup")
async def startup() -> None:
    """Initialize application on startup."""
    # Create necessary directories
    for env in ["development", "production"]:
        Path(env).joinpath("runs").mkdir(parents=True, exist_ok=True)
        Path(env).joinpath("logs").mkdir(parents=True, exist_ok=True)

    app_logger.info("Case-to-Clearance application started")


@app.on_event("shutdown")
async def shutdown() -> None:
    """Clean up on shutdown."""
    # Close any open connections
    from app.huawei.maas import get_maas_client
    from app.huawei.ocr import get_ocr_client

    try:
        await get_maas_client().close()
        await get_ocr_client().close()
    except Exception as e:
        app_logger.warning(f"Error closing connections: {e}")

    app_logger.info("Case-to-Clearance application shut down")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
