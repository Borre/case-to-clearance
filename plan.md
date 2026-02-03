# EVALUATED PLAN: Case-to-Clearance Single Window Copilot

## OVERALL ASSESSMENT

| Dimension | Rating | Notes |
|-----------|--------|-------|
| **Technical Stack** | 9/10 | Modern, pragmatic choices. uv + FastAPI + HTMX is excellent for demos |
| **Architecture** | 8/10 | Single CaseFile state is good; consider adding validation guardrails |
| **Risk Approach** | 9/10 | Deterministic scoring + LLM explanation is the right hybrid approach |
| **Demo Readiness** | 8/10 | Good narrative; needs polish on the wow factors |
| **Implementation Feasibility** | 7/10 | Scope is ambitious for single demo; may need prioritization |

---

## BEST PRACTICES RESEARCH FINDINGS

### 1. LangChain LCEL Orchestration (2025 Best Practices)

**Key Findings:**
- LangGraph is preferred over simple LCEL chains for stateful multi-stage workflows
- Use explicit state management with typed schemas
- Implement retry logic with exponential backoff for API calls
- Add observability hooks at each chain stage

**Recommendation:** Consider using `LangGraph` with a `StateGraph` instead of pure LCEL chains.

### 2. OCR + LLM Extraction Pipeline (2025 Best Practices)

**Key Findings:**
- Two-stage pattern: OCR extraction -> LLM structuring (not OCR alone)
- Include confidence scores at extraction stage
- Implement threshold-based routing for low-confidence results
- Add guardrails for empty/noisy output detection

**Recommendation:** Add confidence scores to each extraction field. If confidence < threshold, flag for manual review.

### 3. Deterministic Risk Scoring for Customs

**Key Findings:**
- Customs fraud detection uses: declared value mismatches, shipment ID inconsistencies, missing documentation, prior flags
- Risk scores should be 0-100 with clear thresholds (low < 25, medium 25-60, high > 60)
- Each rule must have: factor_id, description, points, evidence links
- Rule-based systems are preferred for regulatory transparency

**Recommendation:** Add risk level categories (LOW/MEDIUM/HIGH/CRITICAL) with color coding.

### 4. JSON Structured Extraction with DeepSeek

**Key Findings:**
- DeepSeek supports native JSON mode with `response_format: {"type": "json_object"}`
- For structured extraction, provide explicit JSON schema in system prompt
- Implement a "json_fix" retry chain when validation fails

**Recommendation:** Add a `JsonFixerChain` that takes failed JSON + error and repairs it, with max 3 retries.

### 5. FastAPI + HTMX Best Practices

**Key Findings:**
- Use Jinja fragments for partial HTML updates with HTMX
- Leverage `hx-swap-oob` for out-of-band updates (sidebar, notifications)
- Add loading states with `hx-indicator`
- Implement proper error handling with 422/500 status codes

---

## ENHANCED CASEFILE SCHEMA

```json
{
  "case_id": "string",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",

  "procedure": {
    "id": "string",
    "name": "string",
    "confidence": 0.0-1.0,
    "rationale": "string"
  },

  "citizen_intake": {
    "messages": [
      {"role": "user|assistant", "content": "string", "timestamp": "ISO-8601"}
    ],
    "collected_fields": {},
    "missing_fields": []
  },

  "documents": {
    "files": [
      {"filename": "string", "mime": "string", "size": int, "uploaded_at": "ISO-8601"}
    ],
    "ocr": [
      {"doc_id": "string", "text": "string", "meta": {}}
    ],
    "extractions": [
      {
        "doc_id": "string",
        "doc_type": "invoice|bl|packing_list|declaration|permit|other",
        "fields": {},
        "confidence": 0.0-1.0,
        "low_confidence_fields": [],
        "extraction_timestamp": "ISO-8601"
      }
    ],
    "validations": [
      {"rule_id": "string", "severity": "info|warn|high|critical", "message": "string", "evidence": {}}
    ],
    "missing_docs": []
  },

  "risk": {
    "score": 0-100,
    "level": "LOW|MEDIUM|HIGH|CRITICAL",
    "factors": [
      {"factor_id": "string", "description": "string", "input_value": "any", "points_added": int}
    ],
    "explanation": {
      "executive_summary": "string",
      "explanation_bullets": [],
      "recommended_next_actions": [],
      "risk_reduction_actions": []
    },
    "confidence": "HIGH|MEDIUM|LOW",
    "review_required": true/false
  },

  "audit": {
    "trace_id": "string",
    "trace": [
      {"timestamp": "ISO-8601", "stage": "string", "model_used": "string", "inputs_redacted": "string", "outputs_summary": "string"}
    ],
    "disclaimers": [],
    "redactions": [],
    "rule_version": "v1.0.0",
    "performance_metrics": {
      "ocr_duration_ms": 0,
      "llm_total_duration_ms": 0,
      "validation_duration_ms": 0
    }
  }
}
```

---

## VALIDATION RULES

```python
# Scoring Rules
{
  "rules": [
    {
      "id": "invoice_total_declared_mismatch",
      "points": 25,
      "severity": "HIGH",
      "description": "Invoice total differs from declared value by >10%"
    },
    {
      "id": "shipment_id_inconsistency",
      "points": 20,
      "severity": "HIGH",
      "description": "Shipment IDs inconsistent across documents"
    },
    {
      "id": "date_sequence_violation",
      "points": 10,
      "severity": "MEDIUM",
      "description": "Document dates violate logical sequence"
    },
    {
      "id": "missing_required_doc",
      "points": 15,
      "severity": "MEDIUM",
      "description": "Required document missing for procedure"
    },
    {
      "id": "currency_mismatch",
      "points": 10,
      "severity": "MEDIUM",
      "description": "Multiple currencies without conversion explanation"
    },
    {
      "id": "prior_flag_present",
      "points": 30,
      "severity": "CRITICAL",
      "description": "Entity has prior compliance flags"
    }
  ],
  "thresholds": {
    "low": 25,
    "medium": 50,
    "high": 75,
    "critical": 90
  }
}
```

---

## PROJECT STRUCTURE

```
case-to-clearance/
  pyproject.toml
  .env.example
  README.md
  plan.md

  app/
    main.py
    config.py
    storage.py
    schemas/
      casefile.json
      intake_output.json
      extraction_invoice.json
      extraction_bl.json
      extraction_packing_list.json
      extraction_declaration.json
      triage_explanation.json
    data/
      procedures.json
      agencies.json
      scoring_rules.json
      required_docs_by_procedure.json
    huawei/
      maas.py
      ocr.py
    chains/
      intake.py
      extraction.py
      checklist.py
      triage.py
      explain.py
      json_fix.py
      prompts.py
    rules/
      validations.py
      scoring.py
    middleware/
      rate_limiting.py
      error_handlers.py
    observability/
      tracer.py
      metrics.py
    guardrails/
      output_validator.py
      number_checker.py
    utils/
      retry.py
      json_repair.py
    ui/
      templates/
        base.html
        index.html
        citizen.html
        documents.html
        risk.html
        case_view.html
        components/
          chat_fragment.html
          docs_fragment.html
          risk_fragment.html
      static/
        styles.css
        app.js

  samples/
    docs_happy_path/
    docs_fraudish/
    docs_missing_docs/
    text_fallback/
    README.md

  demo/
    demo_script.md

  runs/  (generated)
  logs/  (generated)
  tests/
    test_schemas.py
    test_scoring.py
    test_validations.py
    test_mocks.py
```

---

## API ENDPOINTS

```
POST /api/case/new
POST /api/case/{case_id}/chat
POST /api/case/{case_id}/docs/upload
POST /api/case/{case_id}/docs/run_ocr
POST /api/case/{case_id}/docs/extract_validate
POST /api/case/{case_id}/risk/run
GET  /api/case/{case_id}
GET  /ui
GET  /ui/case/{case_id}
```

---

## IMPLEMENTATION PHASES

### Phase 1: Foundation ✅ COMPLETED
- [x] Scaffold repo with uv, FastAPI, directory structure
- [x] Implement CaseFile state storage with JSON schemas
- [x] Build Huawei MaaS client with retry logic
- [x] Build Huawei OCR client with SDK (Hong Kong region)
- [x] Set up observability (structured logging, tracing)

### Phase 2: Stage 1 - Citizen Intake ✅ COMPLETED
- [x] Implement intake chain for procedure classification
- [x] Build procedure classification chain (DeepSeek-v3.1)
- [x] Build slot-filling question generator
- [x] Add response system (writer model for citizen-facing)
- [x] UI: Chat interface with procedure display

### Phase 3: Stage 2 - Document Processing ✅ COMPLETED
- [x] File upload endpoint with validation
- [x] OCR pipeline with Huawei Cloud SDK
- [x] Document type classifier (invoice/BL/packing/declaration)
- [x] Field extraction chains per document type
- [x] Validation rules engine (6 validation rules)
- [x] UI: Document table + extraction results + findings

### Phase 4: Stage 3 - Risk & Explanation ✅ COMPLETED
- [x] Deterministic scoring engine with rules
- [x] Risk level categorization (LOW/MEDIUM/HIGH/CRITICAL)
- [x] Explanation generation chain (Qwen3-32b)
- [x] Number verification guardrail
- [x] UI: Risk gauge + factors table + explanation blocks

### Phase 5: Demo Polish ✅ COMPLETED
- [x] Create 3 sample document sets (10 PNG documents)
- [x] Write demo script with expected outputs
- [x] Add loading states and animations
- [x] Test run-through (comprehensive workflow tests)
- [x] Document README

## IMPLEMENTATION STATUS: 100% COMPLETE

All planned features have been implemented and tested. The system is production-ready for demo purposes.

---

## DISCLAIMER

```
⚠️ ADVISORY ONLY - This system provides decision support and does NOT make
final legal determinations. All risk scores and recommendations must be
reviewed by qualified customs officials. The authority assumes full
responsibility for all final decisions.
```

---

## SOURCES

- LangGraph Agent Orchestration Framework
- Document Ingestion Guide 2025
- AI Explainability Scorecard - CSA
- AI-Automated Document Validation for Customs
- DeepSeek JSON Output Guide
- FastAPI + HTMX Best Practices
- uv Package Manager Documentation
