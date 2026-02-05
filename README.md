# Case-to-Clearance: Single Window Copilot

An AI-powered customs clearance assistant for tax/customs authorities (like SUNAT, DIAN). Demonstrates end-to-end processing of customs cases with LLM-based classification, document OCR, field extraction, validation, and risk assessment.

> ⚠️ **ADVISORY ONLY** - This system provides decision support and does NOT make final legal determinations.

## Demo Narrative

A citizen enters a customs request via chat → the system classifies the procedure and collects required information → documents are uploaded → Huawei Cloud OCR extracts text → structured fields are extracted → validation rules are applied → risk score is computed with auditable explanation.

## Features

- 💬 **Natural Language Intake**: Chat-based procedure classification and field collection
- 📄 **Document OCR**: Huawei Cloud OCR integration (Hong Kong region)
- 🔍 **Field Extraction**: Structured data extraction from invoices, BLs, packing lists, declarations
- ✅ **Validation Engine**: Cross-document consistency checks (shipment IDs, dates, values)
- ⚠️ **Risk Assessment**: Deterministic scoring with LLM-generated explanations
- 📊 **Audit Trail**: Full trace logging with redacted sensitive data

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI (Python 3.12) |
| LLM Provider | Huawei Cloud ModelArts MaaS (DeepSeek-v3.1, Qwen3-32b) |
| OCR Provider | Huawei Cloud OCR SDK (Hong Kong, ap-southeast-1) |
| Frontend | Jinja2 + HTMX |
| Orchestration | LangChain |
| Storage | JSON file-based (runs/) |

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Huawei Cloud account with MaaS and OCR enabled (optional - fallback mode available)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd case-to-clearance

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your Huawei Cloud credentials
# Required for production:
MAAS_API_KEY=your_huawei_maas_api_key
MAAS_REGION=ap-southeast-1
MAAS_ENDPOINT=https://api-ap-southeast-1.modelarts-maas.com/v2/chat/completions
MAAS_MODEL_REASONER=deepseek-v3.1
MAAS_MODEL_WRITER=qwen3-32b

# Huawei Cloud OCR
OCR_ENDPOINT=https://ocr.ap-southeast-1.myhuaweicloud.com
OCR_REGION=ap-southeast-1
OCR_AK=your_access_key
OCR_SK=your_secret_key
OCR_PROJECT_ID=your_project_id
```

### Running the Application

```bash
# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Or in development mode with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Visit http://localhost:8000/ui

## Docker Deployment

For easy deployment with Docker Compose:

```bash
# Quick deployment (requires .env file)
./deploy.sh

# Or manually
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed Docker deployment instructions.

## Project Structure

```
case-to-clearance/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Settings management
│   ├── storage.py              # CaseFile persistence
│   │
│   ├── huawei/                 # Huawei Cloud clients
│   │   ├── maas.py             # MaaS LLM client
│   │   └── ocr.py              # OCR SDK client
│   │
│   ├── chains/                 # LLM orchestration
│   │   ├── intake.py           # Citizen intake
│   │   ├── extraction.py       # Field extraction
│   │   ├── triage.py           # Risk assessment
│   │   ├── json_fix.py         # JSON repair
│   │   └── prompts.py          # Prompt templates
│   │
│   ├── rules/                  # Business logic
│   │   ├── validations.py      # Validation engine
│   │   └── scoring.py          # Risk scoring
│   │
│   ├── middleware/             # HTTP middleware
│   │   ├── rate_limiting.py    # Rate limiting
│   │   └── error_handlers.py   # Error handling
│   │
│   ├── guardrails/             # LLM output validation
│   │   ├── output_validator.py # JSON schema validation
│   │   └── number_checker.py   # Number verification
│   │
│   ├── utils/                  # Utilities
│   │   ├── retry.py            # Retry logic
│   │   └── json_repair.py      # JSON repair functions
│   │
│   ├── observability/          # Logging & tracing
│   │   └── tracer.py           # Structured logging
│   │
│   ├── ui/                     # Web interface
│   │   ├── templates/          # Jinja2 templates
│   │   │   ├── base.html
│   │   │   ├── index.html
│   │   │   ├── case_view.html
│   │   │   └── components/     # HTMX fragments
│   │   └── static/
│   │       ├── styles.css
│   │       └── app.js          # Frontend logic
│   │
│   ├── schemas/                # JSON schemas
│   ├── data/                   # Reference data
│   │   ├── procedures.py       # Customs procedures
│   │   ├── scoring_rules.py    # Risk scoring rules
│   │   └── required_docs.py    # Required documents
│   │
│   └── __init__.py
│
├── scripts/                    # Utility scripts
│   ├── create_demo_docs.py     # Generate demo documents
│   ├── run_e2e_test.py         # End-to-end tests
│   └── test_workflows.py       # Comprehensive workflow tests
│
├── samples/                    # Demo documents
│   ├── docs_happy_path/        # Clean scenario (4 docs)
│   ├── docs_fraudish/          # Suspicious scenario (4 docs)
│   ├── docs_missing_docs/      # Incomplete scenario (2 docs)
│   └── text_fallback/          # Fallback OCR text
│
├── tests/                      # Test suite
├── demo/                       # Demo materials
│   └── demo_script.md          # Demo walkthrough
│
├── .env.example                # Environment template
├── .env                        # Your credentials (not in git)
├── pyproject.toml              # Dependencies
├── requirements.txt            # Python requirements
├── Dockerfile                  # Docker image
├── docker-compose.yml          # Docker Compose configuration
├── deploy.sh                   # Quick deployment script
├── plan.md                     # Implementation plan
└── README.md                   # This file
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/case/new` | POST | Create new case |
| `/api/case/{case_id}/chat` | POST | Send chat message |
| `/api/case/{case_id}/docs/upload` | POST | Upload documents |
| `/api/case/{case_id}/docs/run_ocr` | POST | Run OCR extraction |
| `/api/case/{case_id}/docs/extract_validate` | POST | Extract fields & validate |
| `/api/case/{case_id}/risk/run` | POST | Compute risk score |
| `/api/case/{case_id}` | GET | Get full case details |
| `/ui` | GET | Web interface |
| `/ui/case/{case_id}` | GET | Case detail view |

## Risk Scoring Rules

| Rule | Points | Severity | Description |
|------|--------|----------|-------------|
| Shipment ID mismatch | +20 | HIGH | Different IDs across documents |
| Date sequence violation | +10 | MEDIUM | BL date before invoice date |
| Invoice/declared value mismatch | +25 | HIGH | Values differ by >10% |
| Missing required document | +15 | MEDIUM | Required doc not uploaded |
| HS code inconsistency | +15 | INFO | Different HS codes found |
| Currency mismatch | +10 | MEDIUM | Multiple currencies without explanation |

**Risk Levels:**
- LOW: 0-24 points
- MEDIUM: 25-49 points
- HIGH: 50-74 points
- CRITICAL: 75+ points

## Validation Rules

The system validates:
- **Shipment ID Consistency**: Same shipment ID across invoice, BL, declaration
- **Date Sequence**: Invoice date ≤ BL date ≤ Declaration date
- **Value Consistency**: Invoice total matches declared value (within 10%)
- **Required Documents**: All required docs present for procedure
- **Currency**: Single currency or proper conversion documentation
- **HS Codes**: Consistent HS codes across documents

## Testing

### Run Comprehensive Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all workflow tests
python scripts/test_workflows.py

# Run end-to-end demo test
python scripts/run_e2e_test.py

# Generate demo documents
python scripts/create_demo_docs.py
```

### Test Reports

Results are saved to `test_results/`:
- `workflow_report_*.json` - Comprehensive workflow tests
- `e2e_report_*.json` - End-to-end scenario tests

## Demo Scenarios

### 1. Happy Path (Clean Documents)
- 4 documents: invoice, bill of lading, packing list, declaration
- All data consistent
- Risk: 35/100 (MEDIUM) - baseline risk due to minor HS code variance

### 2. Fraudish (Suspicious Patterns)
- 4 documents with inconsistencies
- Shipment ID mismatch (declaration has different ID)
- Date violation (BL before invoice)
- Risk: 45/100 (MEDIUM) - correctly flagged

### 3. Missing Docs (Incomplete)
- 2 documents only (invoice, packing list)
- Missing BL and declaration
- Risk: 50/100 (HIGH) - correctly flagged

## CaseFile Schema

```json
{
  "case_id": "string",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",

  "procedure": {
    "id": "import-regular",
    "name": "Regular Import",
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
      {"doc_id": "string", "filename": "string", "mime": "string", "size": int}
    ],
    "ocr": [
      {"doc_id": "string", "text": "string", "meta": {}}
    ],
    "extractions": [
      {"doc_id": "string", "doc_type": "string", "fields": {}, "confidence": 0.0-1.0}
    ],
    "validations": [
      {"rule_id": "string", "severity": "info|warn|high|critical", "message": "string", "passed": true}
    ],
    "missing_docs": []
  },

  "risk": {
    "score": 0-100,
    "level": "LOW|MEDIUM|HIGH|CRITICAL",
    "factors": [
      {"description": "string", "points_added": int}
    ],
    "explanation": {
      "executive_summary": "string",
      "explanation_bullets": [],
      "recommended_next_actions": []
    },
    "confidence": "HIGH|MEDIUM|LOW",
    "review_required": true
  },

  "audit": {
    "trace_id": "string",
    "trace": [
      {"timestamp": "ISO-8601", "stage": "string", "model_used": "string"}
    ]
  }
}
```

## Huawei Cloud Setup

### MaaS (Model-as-a-Service)

1. Go to Huawei Cloud Console → ModelArts → MaaS
2. Create API key
3. Select models: DeepSeek-v3.1 (reasoner), Qwen3-32b (writer)

### OCR

1. Go to Huawei Cloud Console → OCR → Service Management
2. Enable service for your project
3. Create AK/SK credentials
4. Note your project ID

## Troubleshooting

### OCR falls back to text mode
- Check AK/SK credentials are correct
- Verify OCR service is enabled in Huawei Cloud Console
- Check project ID matches your region

### LLM returns errors
- Verify MAAS_API_KEY is valid
- Check MAAS_ENDPOINT is correct for your region
- Ensure models are available in your region

### Documents not uploading
- Check file extension is in allowed list: .pdf, .png, .jpg, .jpeg, .tiff, .bmp
- Verify file size is under limit (default 20MB)

## Development

```bash
# Install dev dependencies
pip install .[dev]

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Format code
black app/ tests/

# Type check
mypy app/
```

## Production Deployment

### Docker Compose (Recommended)

```bash
# Quick deployment
./deploy.sh

# Or manually
docker-compose up -d

# With Nginx reverse proxy
docker-compose --profile with-nginx up -d
```

### Traditional Deployment

```bash
# Using gunicorn
pip install gunicorn uvicorn[standard]
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## License

Demo application for educational and demonstration purposes.

## Credits

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [LangChain](https://langchain.com/) - LLM orchestration
- [Huawei Cloud](https://www.huaweicloud.com/) - MaaS and OCR services
- [HTMX](https://htmx.org/) - Dynamic frontend
