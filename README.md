# Case-to-Clearance: Single Window Copilot

A demo product for tax/customs authorities (DIAN/SUNAT-like) that showcases an AI-powered copilot for processing customs clearance requests.

## Demo Narrative

A citizen enters a request in chat -> the system classifies the procedure and collects missing info -> the user uploads mixed PDFs/images -> Huawei Cloud OCR extracts text -> the agent extracts structured fields + runs deterministic validations -> the system computes a deterministic risk score and generates an auditable explanation + recommended next actions.

**Important:** The system is advisory only and never makes final legal decisions.

## Tech Stack

- **Python 3.11+** with `uv` for dependency management
- **FastAPI** backend with async support
- **LangChain** for orchestration
- **Huawei Cloud ModelArts MaaS** for LLM calls (DeepSeek + Qwen)
- **Huawei Cloud OCR** for document text extraction
- **Jinja2 + HTMX** for minimal, functional frontend

## Quick Start

### Prerequisites

- Python 3.11 or higher
- uv package manager (install with: `curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd case-to-clearance

# Install dependencies with uv
uv sync

# Copy and configure environment
cp .env.example .env
# Edit .env with your Huawei Cloud credentials (optional - fallback mode works without)
```

### Running the Application

```bash
# Development mode with auto-reload
uv run dev

# Or with uvicorn directly
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Visit http://localhost:8000/ui

### Without uv (alternative)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install fastapi uvicorn jinja2 python-multipart httpx langchain langchain-core pydantic jsonschema python-dotenv

# Run the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Configuration

The application works in **fallback mode** without any Huawei Cloud credentials. To enable real LLM and OCR:

```bash
# Edit .env file
MAAS_API_KEY=your_huawei_maas_api_key
MAAS_REGION=cn-north-4
OCR_AK=your_ocr_access_key
OCR_SK=your_ocr_secret_key
```

## Project Structure

```
case-to-clearance/
  pyproject.toml          # Project dependencies
  .env.example            # Environment variables template
  README.md               # This file
  plan.md                 # Detailed implementation plan

  app/
    main.py               # FastAPI application entry point
    config.py             # Configuration with environment variables
    storage.py            # CaseFile state persistence
    schemas/              # JSON schemas for validation
      casefile.json       # Main CaseFile schema
    data/                 # Reference data
      procedures.json     # Available customs procedures
      scoring_rules.json  # Risk scoring rules
      required_docs_by_procedure.json
      agencies.json
    huawei/               # Huawei Cloud clients
      maas.py             # ModelArts MaaS LLM client
      ocr.py              # OCR client with fallback
    chains/               # LangChain orchestration
      intake.py           # Citizen intake (procedure classification)
      extraction.py       # Document field extraction
      triage.py           # Risk assessment and explanation
      json_fix.py         # JSON repair for LLM outputs
      prompts.py          # Prompt templates
    rules/                # Business rules
      validations.py      # Document validation engine
      scoring.py          # Risk scoring engine
    utils/                # Utilities
      retry.py            # Exponential backoff retry
    observability/        # Logging and tracing
      tracer.py           # Structured logging
    ui/                   # Web interface
      templates/          # Jinja2 templates
        base.html
        index.html
        case_view.html
      static/
        styles.css

  samples/                # Sample documents for demo
    docs_happy_path/      # Low risk scenario
    docs_fraudish/        # High risk scenario
    docs_missing_docs/    # Medium risk scenario
    text_fallback/        # Pre-extracted OCR text

  demo/
    demo_script.md        # Step-by-step demo instructions

  tests/                  # Test suite
    test_schemas.py       # JSON schema validation tests
    test_scoring.py       # Risk scoring tests
    test_validations.py   # Validation rule tests

  runs/                   # Generated case data
  logs/                   # Application logs
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/case/new` | POST | Create new case |
| `/api/case/{case_id}/chat` | POST | Send chat message |
| `/api/case/{case_id}/docs/upload` | POST | Upload documents |
| `/api/case/{case_id}/docs/run_ocr` | POST | Run OCR extraction |
| `/api/case/{case_id}/docs/extract_validate` | POST | Extract fields and validate |
| `/api/case/{case_id}/risk/run` | POST | Compute risk score |
| `/api/case/{case_id}` | GET | Get full CaseFile |
| `/ui` | GET | Web interface |
| `/ui/case/{case_id}` | GET | Case view |

## Running Tests

```bash
# Run all tests
uv run test
# Or: uv run pytest tests/

# Run with coverage
uv run test-cov
# Or: uv run pytest tests/ --cov=app --cov-report=html
```

## Demo Script

See `demo/demo_script.md` for step-by-step demo instructions including:
- Happy path (low risk) scenario
- Fraud indicators (high risk) scenario
- Missing documents (medium risk) scenario

## Architecture Highlights

### Single State Object (CaseFile)
All case data is stored in a single JSON state object that persists after each stage:
- `procedure`: Selected procedure with confidence
- `citizen_intake`: Chat messages, collected fields
- `documents`: Files, OCR results, extractions, validations
- `risk`: Score, level, factors, explanation
- `audit`: Trace, disclaimers, redactions

### Deterministic Risk Scoring
Risk scores are computed from explicit rules:
- Invoice vs declared value mismatch: +25 points
- Shipment ID inconsistency: +20 points
- Date sequence violation: +10 points
- Missing required document: +15 points each
- Currency mismatch: +10 points
- Prior flags: +30 points

Risk levels: LOW (<25), MEDIUM (25-50), HIGH (50-75), CRITICAL (75+)

### Guardrails
- JSON schema validation on all LLM outputs
- Number verification to prevent hallucinated statistics
- Audit trail with redacted PII
- Explicit advisory disclaimers

## Disclaimer

⚠️ **ADVISORY ONLY** - This system provides decision support and does NOT make final legal determinations. All risk scores and recommendations must be reviewed by qualified customs officials.

## License

Demo application for educational and demonstration purposes.
