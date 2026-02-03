"""FastAPI application for Case-to-Clearance demo."""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, UploadFile, Form, File, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.chains.extraction import get_extraction_chain
from app.chains.intake import get_intake_chain
from app.chains.triage import get_triage_chain
from app.config import settings
from app.huawei.ocr import get_ocr_client
from app.observability.tracer import app_logger, log_trace
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
    case = storage.load(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Add user message
    case.add_message("user", message)

    # Process with intake chain
    intake_chain = get_intake_chain()
    result = await intake_chain.classify_and_collect(case, message)

    # Update case with results
    if result.get("procedure"):
        case.procedure = result["procedure"]

    if result.get("detected_fields"):
        collected = case.citizen_intake.get("collected_fields", {})
        collected.update(result.get("detected_fields", {}))
        case.citizen_intake["collected_fields"] = collected

    if result.get("missing_fields") is not None:
        case.citizen_intake["missing_fields"] = result["missing_fields"]

    # Add assistant response
    assistant_message = result.get("response", "I'm sorry, I couldn't process that request.")
    case.add_message("assistant", assistant_message)

    # Add trace
    case.add_trace(
        stage="citizen_intake",
        model_used=settings.maas_model_reasoner,
        inputs_summary=f"message_length={len(message)}",
        outputs_summary=f"procedure={case.procedure.get('id')}, missing_fields={len(case.citizen_intake.get('missing_fields', []))}",
    )

    # Save case
    storage.save(case)

    log_trace(
        app_logger,
        case_id,
        "citizen_intake",
        settings.maas_model_reasoner,
        f"message_length={len(message)}",
        f"procedure={result.get('procedure', {}).get('id')}",
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
    case = storage.load(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    ocr_client = get_ocr_client()
    case_dir = Path(settings.app_env).joinpath("runs", case_id)

    ocr_results = []

    for file_info in case.documents.get("files", []):
        doc_id = file_info["doc_id"]
        file_path = case_dir.joinpath(file_info["path"])

        if not file_path.exists():
            continue

        # Read file
        with file_path.open("rb") as f:
            file_bytes = f.read()

        # Run OCR
        result = await ocr_client.extract_text(
            file_bytes=file_bytes,
            filename=file_info["filename"],
            mime_type=file_info["mime"],
        )

        # Ensure doc_id matches
        result["doc_id"] = doc_id
        case.documents["ocr"].append(result)
        ocr_results.append(result)

    storage.save(case)

    app_logger.info(f"OCR completed for {len(ocr_results)} documents in case {case_id}")

    return {
        "case_id": case_id,
        "ocr_results": ocr_results,
        "total_docs": len(ocr_results),
    }


@app.post("/api/case/{case_id}/docs/extract_validate")
async def extract_and_validate(case_id: str) -> dict[str, Any]:
    """Extract fields and run validations."""
    case = storage.load(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    extraction_chain = get_extraction_chain()
    procedure_id = case.procedure.get("id", "import-regular")

    # Clear previous extractions and validations
    case.documents["extractions"] = []
    case.documents["validations"] = []

    # Extract from each OCR result
    for ocr_result in case.documents.get("ocr", []):
        doc_id = ocr_result["doc_id"]
        ocr_text = ocr_result.get("text", "")

        # Classify document type
        filename = ocr_result.get("meta", {}).get("filename", "")
        classification = await extraction_chain.classify_document(ocr_text, filename)
        doc_type = classification.get("doc_type", "other")

        # Extract fields
        extraction = await extraction_chain.extract_by_type(ocr_text, doc_type, doc_id)
        extraction["doc_type"] = doc_type  # Ensure doc_type is set
        case.documents["extractions"].append(extraction)

    # Run validations
    from app.rules.validations import get_validation_engine

    validation_engine = get_validation_engine()
    validations = await validation_engine.validate_all(
        case,
        case.documents.get("extractions", []),
        procedure_id,
    )
    case.documents["validations"] = validations

    storage.save(case)

    app_logger.info(
        f"Extraction and validation completed for case {case_id}: "
        f"{len(case.documents['extractions'])} extractions, "
        f"{len(validations)} validations"
    )

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
    case = storage.load(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    triage_chain = get_triage_chain()
    procedure_id = case.procedure.get("id", "import-regular")

    result = await triage_chain.process_risk_assessment(
        case=case,
        validations=case.documents.get("validations", []),
        extractions=case.documents.get("extractions", []),
        procedure_id=procedure_id,
    )

    # Update case with risk results
    case.initialize_risk()
    case.risk = {
        "score": result["score"],
        "level": result["level"],
        "factors": result["factors"],
        "explanation": result["explanation"],
        "confidence": result.get("confidence", "HIGH"),
        "review_required": result.get("review_required", False),
    }

    # Add trace
    case.add_trace(
        stage="risk_assessment",
        model_used=settings.maas_model_writer,
        inputs_summary=f"extractions={len(case.documents.get('extractions', []))}, validations={len(case.documents.get('validations', []))}",
        outputs_summary=f"score={result['score']}, level={result['level']}, factors={len(result['factors'])}",
    )

    storage.save(case)

    log_trace(
        app_logger,
        case_id,
        "risk_assessment",
        settings.maas_model_writer,
        f"extractions={len(case.documents.get('extractions', []))}",
        f"score={result['score']}, level={result['level']}",
    )

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
