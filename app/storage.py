"""CaseFile state storage and management."""

import datetime
import json
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.config import settings


def generate_case_id() -> str:
    """Generate a unique case ID."""
    return f"case-{uuid.uuid4().hex[:12]}"


def get_case_dir(case_id: str) -> Path:
    """Get the directory for a case."""
    return Path(settings.app_env).joinpath("runs", case_id)


class CaseFile(BaseModel):
    """The core state object for a customs clearance case."""

    # Metadata
    case_id: str = Field(default_factory=generate_case_id)
    created_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    # Stage 1: Citizen Intake
    procedure: dict[str, Any] = Field(
        default_factory=dict,
        description="Selected procedure with id, name, confidence, rationale",
    )
    citizen_intake: dict[str, Any] = Field(
        default_factory=dict,
        description="Chat messages, collected fields, missing fields",
    )

    # Stage 2: Documents
    documents: dict[str, Any] = Field(
        default_factory=dict,
        description="Files, OCR results, extractions, validations, missing docs",
    )

    # Stage 3: Risk Assessment
    risk: dict[str, Any] = Field(
        default_factory=dict,
        description="Score, level, factors, explanation",
    )

    # Audit trail
    audit: dict[str, Any] = Field(
        default_factory=dict,
        description="Trace, disclaimers, redactions, metrics",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "case_id": "case-abc123",
                "created_at": "2025-01-15T10:30:00Z",
                "procedure": {"id": "import-01", "confidence": 0.95},
                "citizen_intake": {"messages": [], "collected_fields": {}, "missing_fields": []},
                "documents": {
                    "files": [],
                    "ocr": [],
                    "extractions": [],
                    "validations": [],
                    "missing_docs": [],
                },
                "risk": {"score": 0, "level": "LOW", "factors": []},
                "audit": {"trace": [], "disclaimers": []},
            }
        }

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def add_trace(
        self, stage: str, model_used: str, inputs_summary: str, outputs_summary: str
    ) -> None:
        """Add an entry to the audit trace."""
        if "trace" not in self.audit:
            self.audit["trace"] = []
            self.audit["trace_id"] = f"trace-{uuid.uuid4().hex[:16]}"

        self.audit["trace"].append(
            {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "stage": stage,
                "model_used": model_used,
                "inputs_redacted": inputs_summary,
                "outputs_summary": outputs_summary,
            }
        )

    def initialize_citizen_intake(self) -> None:
        """Initialize the citizen_intake structure."""
        if not self.citizen_intake:
            self.citizen_intake = {"messages": [], "collected_fields": {}, "missing_fields": []}

    def initialize_documents(self) -> None:
        """Initialize the documents structure."""
        if not self.documents:
            self.documents = {
                "files": [],
                "ocr": [],
                "extractions": [],
                "validations": [],
                "missing_docs": [],
            }

    def initialize_risk(self) -> None:
        """Initialize the risk structure."""
        if not self.risk:
            self.risk = {
                "score": 0,
                "level": "LOW",
                "factors": [],
                "explanation": {},
                "confidence": "HIGH",
                "review_required": False,
            }

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the chat history."""
        self.initialize_citizen_intake()
        self.citizen_intake["messages"].append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
        )


class CaseStorage:
    """Storage manager for CaseFile objects."""

    def __init__(self) -> None:
        """Initialize storage."""
        self.base_dir = Path(settings.app_env).joinpath("runs")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, case: CaseFile) -> Path:
        """Save a CaseFile to disk."""
        case_dir = self.base_dir.joinpath(case.case_id)
        case_dir.mkdir(parents=True, exist_ok=True)

        case_file = case_dir.joinpath("case.json")
        with case_file.open("w") as f:
            f.write(case.model_dump_json(indent=2))

        # Save trace separately if it exists
        if case.audit.get("trace"):
            trace_file = case_dir.joinpath("trace.json")
            with trace_file.open("w") as f:
                json.dump(case.audit["trace"], f, indent=2)

        return case_file

    def load(self, case_id: str) -> CaseFile | None:
        """Load a CaseFile from disk."""
        case_file = self.base_dir.joinpath(case_id, "case.json")
        if not case_file.exists():
            return None

        with case_file.open() as f:
            data = json.load(f)

        return CaseFile(**data)

    def exists(self, case_id: str) -> bool:
        """Check if a case exists."""
        return self.base_dir.joinpath(case_id, "case.json").exists()

    def list_cases(self) -> list[str]:
        """List all case IDs."""
        if not self.base_dir.exists():
            return []
        return [d.name for d in self.base_dir.iterdir() if d.is_dir()]

    def delete(self, case_id: str) -> bool:
        """Delete a case directory."""
        case_dir = self.base_dir.joinpath(case_id)
        if not case_dir.exists():
            return False

        import shutil

        shutil.rmtree(case_dir)
        return True


# Global storage instance
storage = CaseStorage()
