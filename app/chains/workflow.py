"""LangGraph-based workflow orchestration for case processing."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.chains.extraction import get_extraction_chain
from app.chains.intake import get_intake_chain
from app.chains.triage import get_triage_chain
from app.config import settings
from app.huawei.ocr import get_ocr_client
from app.observability.tracer import app_logger, log_trace
from app.rules.validations import get_validation_engine
from app.storage import CaseFile, storage

class WorkflowState(TypedDict, total=False):
    """Typed state for workflow execution."""

    case_id: str
    case: CaseFile
    message: str
    steps: dict[str, bool]
    intake_result: dict[str, Any]
    ocr_results: list[dict[str, Any]]
    extractions: list[dict[str, Any]]
    validations: list[dict[str, Any]]
    risk: dict[str, Any]


def _next_step(state: WorkflowState) -> str:
    """Route to the next step based on requested flags."""
    steps = state.get("steps", {})
    if steps.get("intake"):
        return "intake"
    if steps.get("ocr"):
        return "ocr"
    if steps.get("extract_validate"):
        return "extract_validate"
    if steps.get("risk"):
        return "risk"
    return END


async def _load_case(state: WorkflowState) -> WorkflowState:
    case_id = state["case_id"]
    case = storage.load(case_id)
    if not case:
        raise ValueError("Case not found")
    state["case"] = case
    return state


async def _intake(state: WorkflowState) -> WorkflowState:
    case = state["case"]
    message = state.get("message", "")
    if not message:
        state["steps"]["intake"] = False
        return state

    case.add_message("user", message)

    intake_chain = get_intake_chain()
    result = await intake_chain.classify_and_collect(case, message)

    if result.get("procedure"):
        case.procedure = result["procedure"]

    if result.get("detected_fields"):
        collected = case.citizen_intake.get("collected_fields", {})
        collected.update(result.get("detected_fields", {}))
        case.citizen_intake["collected_fields"] = collected

    if result.get("missing_fields") is not None:
        case.citizen_intake["missing_fields"] = result["missing_fields"]

    assistant_message = result.get("response", "I'm sorry, I couldn't process that request.")
    case.add_message("assistant", assistant_message)

    case.add_trace(
        stage="citizen_intake",
        model_used=settings.maas_model_reasoner,
        inputs_summary=f"message_length={len(message)}",
        outputs_summary=(
            f"procedure={case.procedure.get('id')}, "
            f"missing_fields={len(case.citizen_intake.get('missing_fields', []))}"
        ),
    )

    storage.save(case)

    log_trace(
        app_logger,
        case.case_id,
        "citizen_intake",
        settings.maas_model_reasoner,
        f"message_length={len(message)}",
        f"procedure={result.get('procedure', {}).get('id')}",
    )

    state["intake_result"] = result
    state["case"] = case
    state["steps"]["intake"] = False
    return state


async def _ocr(state: WorkflowState) -> WorkflowState:
    case = state["case"]
    case.initialize_documents()
    ocr_client = get_ocr_client()

    ocr_results: list[dict[str, Any]] = []

    for file_info in case.documents.get("files", []):
        doc_id = file_info["doc_id"]
        from pathlib import Path

        file_path = Path(settings.app_env).joinpath("runs", case.case_id, file_info["path"])

        if not file_path.exists():
            continue

        with file_path.open("rb") as f:
            file_bytes = f.read()

        result = await ocr_client.extract_text(
            file_bytes=file_bytes,
            filename=file_info["filename"],
            mime_type=file_info["mime"],
        )

        result["doc_id"] = doc_id
        case.documents["ocr"].append(result)
        ocr_results.append(result)

    storage.save(case)

    app_logger.info(f"OCR completed for {len(ocr_results)} documents in case {case.case_id}")

    state["ocr_results"] = ocr_results
    state["case"] = case
    state["steps"]["ocr"] = False
    return state


async def _extract_validate(state: WorkflowState) -> WorkflowState:
    case = state["case"]
    case.initialize_documents()
    extraction_chain = get_extraction_chain()
    procedure_id = case.procedure.get("id", "import-regular")

    case.documents["extractions"] = []
    case.documents["validations"] = []

    for ocr_result in case.documents.get("ocr", []):
        doc_id = ocr_result["doc_id"]
        ocr_text = ocr_result.get("text", "")

        filename = ocr_result.get("meta", {}).get("filename", "")
        classification = await extraction_chain.classify_document(ocr_text, filename)
        doc_type = classification.get("doc_type", "other")

        extraction = await extraction_chain.extract_by_type(ocr_text, doc_type, doc_id)
        extraction["doc_type"] = doc_type
        case.documents["extractions"].append(extraction)

    validation_engine = get_validation_engine()
    validations = await validation_engine.validate_all(
        case,
        case.documents.get("extractions", []),
        procedure_id,
    )
    case.documents["validations"] = validations

    storage.save(case)

    app_logger.info(
        f"Extraction and validation completed for case {case.case_id}: "
        f"{len(case.documents['extractions'])} extractions, "
        f"{len(validations)} validations"
    )

    state["extractions"] = case.documents.get("extractions", [])
    state["validations"] = validations
    state["case"] = case
    state["steps"]["extract_validate"] = False
    return state


async def _risk(state: WorkflowState) -> WorkflowState:
    case = state["case"]
    triage_chain = get_triage_chain()
    procedure_id = case.procedure.get("id", "import-regular")

    result = await triage_chain.process_risk_assessment(
        case=case,
        validations=case.documents.get("validations", []),
        extractions=case.documents.get("extractions", []),
        procedure_id=procedure_id,
    )

    case.initialize_risk()
    case.risk = {
        "score": result["score"],
        "level": result["level"],
        "factors": result["factors"],
        "explanation": result["explanation"],
        "confidence": result.get("confidence", "HIGH"),
        "review_required": result.get("review_required", False),
    }

    case.add_trace(
        stage="risk_assessment",
        model_used=settings.maas_model_writer,
        inputs_summary=(
            f"extractions={len(case.documents.get('extractions', []))}, "
            f"validations={len(case.documents.get('validations', []))}"
        ),
        outputs_summary=(
            f"score={result['score']}, level={result['level']}, "
            f"factors={len(result['factors'])}"
        ),
    )

    storage.save(case)

    app_logger.info(
        f"Risk assessment completed for case {case.case_id}: "
        f"score={case.risk.get('score')} level={case.risk.get('level')}"
    )

    log_trace(
        app_logger,
        case.case_id,
        "risk_assessment",
        settings.maas_model_writer,
        f"extractions={len(case.documents.get('extractions', []))}",
        f"score={result['score']}, level={result['level']}",
    )

    state["risk"] = case.risk
    state["case"] = case
    state["steps"]["risk"] = False
    return state


def _build_graph() -> StateGraph:
    graph = StateGraph(WorkflowState)
    graph.add_node("load_case", _load_case)
    graph.add_node("intake", _intake)
    graph.add_node("ocr", _ocr)
    graph.add_node("extract_validate", _extract_validate)
    graph.add_node("risk", _risk)

    graph.set_entry_point("load_case")
    graph.add_conditional_edges("load_case", _next_step)
    graph.add_conditional_edges("intake", _next_step)
    graph.add_conditional_edges("ocr", _next_step)
    graph.add_conditional_edges("extract_validate", _next_step)
    graph.add_conditional_edges("risk", _next_step)

    return graph


_workflow_graph = _build_graph().compile()


async def run_workflow(
    *,
    case_id: str,
    steps: dict[str, bool],
    message: str | None = None,
) -> WorkflowState:
    """Run the workflow for the requested steps."""
    initial_state: WorkflowState = {
        "case_id": case_id,
        "steps": steps,
    }
    if message:
        initial_state["message"] = message

    return await _workflow_graph.ainvoke(initial_state)
