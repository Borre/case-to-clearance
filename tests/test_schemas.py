"""Test JSON schema validation."""

import json
import pytest
from pathlib import Path
from jsonschema import validate, ValidationError


def load_schema(schema_name: str) -> dict:
    """Load a JSON schema from app/schemas."""
    schema_path = Path(__file__).parent.parent.joinpath("app", "schemas", schema_name)
    with schema_path.open() as f:
        return json.load(f)


def test_casefile_schema_exists():
    """Test that casefile schema exists and is valid JSON."""
    schema = load_schema("casefile.json")
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert schema["title"] == "CaseFile"


def test_casefile_schema_valid_structure():
    """Test that casefile schema has required properties."""
    schema = load_schema("casefile.json")

    required_properties = ["case_id", "created_at", "updated_at", "procedure", "citizen_intake", "documents", "risk", "audit"]
    for prop in required_properties:
        assert prop in schema["properties"], f"Missing property: {prop}"


def test_casefile_schema_validates_minimal_case():
    """Test that casefile schema validates minimal valid case."""
    schema = load_schema("casefile.json")

    minimal_case = {
        "case_id": "case-abc123def4",
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T10:00:00Z",
        "procedure": {},
        "citizen_intake": {},
        "documents": {},
        "risk": {},
        "audit": {}
    }

    # Should not raise ValidationError
    validate(instance=minimal_case, schema=schema)


def test_casefile_schema_requires_case_id():
    """Test that casefile schema requires case_id."""
    schema = load_schema("casefile.json")

    invalid_case = {
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T10:00:00Z",
    }

    with pytest.raises(ValidationError):
        validate(instance=invalid_case, schema=schema)


def test_casefile_schema_case_id_pattern():
    """Test that casefile schema validates case_id pattern."""
    schema = load_schema("casefile.json")

    invalid_cases = [
        {"case_id": "invalid", "created_at": "2025-01-15T10:00:00Z", "updated_at": "2025-01-15T10:00:00Z"},
        {"case_id": "CASE-123", "created_at": "2025-01-15T10:00:00Z", "updated_at": "2025-01-15T10:00:00Z"},
    ]

    for case in invalid_cases:
        with pytest.raises(ValidationError):
            validate(instance=case, schema=schema)


def test_casefile_schema_validates_risk_level():
    """Test that casefile schema validates risk level enum."""
    schema = load_schema("casefile.json")

    case = {
        "case_id": "case-abc123def4",
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T10:00:00Z",
        "procedure": {},
        "citizen_intake": {},
        "documents": {},
        "risk": {
            "level": "INVALID"
        },
        "audit": {}
    }

    with pytest.raises(ValidationError):
        validate(instance=case, schema=schema)


def test_casefile_schema_validates_doc_type_enum():
    """Test that casefile schema validates document type enum."""
    schema = load_schema("casefile.json")

    case = {
        "case_id": "case-abc123def4",
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T10:00:00Z",
        "procedure": {},
        "citizen_intake": {},
        "documents": {
            "extractions": [
                {
                    "doc_id": "doc-1",
                    "doc_type": "invalid_type",
                    "fields": {},
                    "confidence": 0.9
                }
            ]
        },
        "risk": {},
        "audit": {}
    }

    with pytest.raises(ValidationError):
        validate(instance=case, schema=schema)


def test_casefile_schema_validates_risk_score_range():
    """Test that casefile schema validates risk score 0-100."""
    schema = load_schema("casefile.json")

    invalid_scores = [-1, 101, 150]

    for score in invalid_scores:
        case = {
            "case_id": "case-abc123def4",
            "created_at": "2025-01-15T10:00:00Z",
            "updated_at": "2025-01-15T10:00:00Z",
            "procedure": {},
            "citizen_intake": {},
            "documents": {},
            "risk": {"score": score},
            "audit": {}
        }

        with pytest.raises(ValidationError):
            validate(instance=case, schema=schema)


def test_procedures_data_exists():
    """Test that procedures data exists and is valid."""
    from app.data import PROCEDURES

    assert "procedures" in PROCEDURES
    assert isinstance(PROCEDURES["procedures"], list)
    assert len(PROCEDURES["procedures"]) > 0


def test_procedures_have_required_fields():
    """Test that all procedures have required fields."""
    from app.data import PROCEDURES

    required_fields = ["id", "name", "description", "required_fields", "required_documents"]

    for proc in PROCEDURES["procedures"]:
        for field in required_fields:
            assert field in proc, f"Procedure {proc.get('id')} missing field: {field}"


def test_scoring_rules_exist():
    """Test that scoring rules data exists."""
    from app.data import SCORING_RULES

    assert "rules" in SCORING_RULES
    assert "thresholds" in SCORING_RULES
    assert isinstance(SCORING_RULES["rules"], list)


def test_scoring_rules_have_required_fields():
    """Test that all scoring rules have required fields."""
    from app.data import SCORING_RULES

    for rule in SCORING_RULES["rules"]:
        assert "id" in rule
        assert "points" in rule
        assert "severity" in rule
        assert "description" in rule
