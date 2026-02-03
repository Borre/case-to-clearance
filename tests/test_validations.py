"""Test validation rules."""

import pytest
from app.rules.validations import ValidationEngine, ValidationResult
from app.storage import CaseFile


@pytest.fixture
def case() -> CaseFile:
    """Create a test case."""
    case = CaseFile()
    case.procedure = {"id": "import-regular", "name": "Regular Import"}
    case.initialize_documents()
    return case


@pytest.fixture
def validation_engine() -> ValidationEngine:
    """Create validation engine."""
    return ValidationEngine()


def test_validation_result_to_dict():
    """Test ValidationResult.to_dict() method."""
    result = ValidationResult(
        rule_id="test_rule",
        severity="high",
        message="Test message",
        evidence={"test": "data"},
        passed=False,
    )

    result_dict = result.to_dict()

    assert result_dict["rule_id"] == "test_rule"
    assert result_dict["severity"] == "high"
    assert result_dict["message"] == "Test message"
    assert result_dict["evidence"] == {"test": "data"}
    assert result_dict["passed"] is False


def test_validate_invoice_vs_declared_value_match(validation_engine: ValidationEngine, case: CaseFile):
    """Test invoice vs declared value validation when values match."""
    extractions = [
        {
            "doc_id": "invoice-1",
            "doc_type": "invoice",
            "fields": {"total_amount": "50000"},
        },
        {
            "doc_id": "decl-1",
            "doc_type": "declaration",
            "fields": {"declared_value": "50000"},
        },
    ]

    result = validation_engine._validate_invoice_vs_declared(case, extractions, "import-regular")

    assert result is not None
    assert result.rule_id == "invoice_total_vs_declared_value"
    assert result.passed is True
    assert result.severity == "info"


def test_validate_invoice_vs_declared_value_mismatch(validation_engine: ValidationEngine, case: CaseFile):
    """Test invoice vs declared value validation when values mismatch."""
    extractions = [
        {
            "doc_id": "invoice-1",
            "doc_type": "invoice",
            "fields": {"total_amount": "80000"},
        },
        {
            "doc_id": "decl-1",
            "doc_type": "declaration",
            "fields": {"declared_value": "50000"},
        },
    ]

    result = validation_engine._validate_invoice_vs_declared(case, extractions, "import-regular")

    assert result is not None
    assert result.rule_id == "invoice_total_vs_declared_value"
    assert result.passed is False
    assert result.severity == "high"
    assert "60%" in result.message  # 60% difference


def test_validate_shipment_id_consistent(validation_engine: ValidationEngine, case: CaseFile):
    """Test shipment ID consistency when IDs match."""
    extractions = [
        {
            "doc_id": "doc-1",
            "doc_type": "invoice",
            "fields": {"shipment_id": "CN-2024-12345"},
        },
        {
            "doc_id": "doc-2",
            "doc_type": "bill_of_lading",
            "fields": {"bl_number": "CN-2024-12345"},
        },
    ]

    result = validation_engine._validate_shipment_id_consistency(case, extractions, "import-regular")

    assert result is not None
    assert result.passed is True
    assert result.severity == "info"


def test_validate_shipment_id_inconsistent(validation_engine: ValidationEngine, case: CaseFile):
    """Test shipment ID consistency when IDs don't match."""
    extractions = [
        {
            "doc_id": "doc-1",
            "doc_type": "invoice",
            "fields": {"shipment_id": "CN-2024-12345"},
        },
        {
            "doc_id": "doc-2",
            "doc_type": "bill_of_lading",
            "fields": {"bl_number": "CN-2024-99999"},
        },
    ]

    result = validation_engine._validate_shipment_id_consistency(case, extractions, "import-regular")

    assert result is not None
    assert result.passed is False
    assert result.severity == "high"
    assert "inconsistent" in result.message.lower()


def test_validate_currency_consistent(validation_engine: ValidationEngine, case: CaseFile):
    """Test currency consistency when same currency."""
    extractions = [
        {
            "doc_id": "doc-1",
            "doc_type": "invoice",
            "fields": {"currency": "USD"},
        },
        {
            "doc_id": "doc-2",
            "doc_type": "declaration",
            "fields": {"currency": "USD"},
        },
    ]

    result = validation_engine._validate_currency_consistency(case, extractions, "import-regular")

    assert result is not None
    assert result.passed is True
    assert result.severity == "info"


def test_validate_currency_inconsistent(validation_engine: ValidationEngine, case: CaseFile):
    """Test currency consistency when different currencies."""
    extractions = [
        {
            "doc_id": "doc-1",
            "doc_type": "invoice",
            "fields": {"currency": "USD"},
        },
        {
            "doc_id": "doc-2",
            "doc_type": "declaration",
            "fields": {"currency": "EUR"},
        },
    ]

    result = validation_engine._validate_currency_consistency(case, extractions, "import-regular")

    assert result is not None
    assert result.passed is False
    assert result.severity == "warn"


def test_validate_required_docs_all_present(validation_engine: ValidationEngine, case: CaseFile):
    """Test required docs check when all present."""
    extractions = [
        {"doc_id": "doc-1", "doc_type": "invoice"},
        {"doc_id": "doc-2", "doc_type": "bill_of_lading"},
        {"doc_id": "doc-3", "doc_type": "packing_list"},
        {"doc_id": "doc-4", "doc_type": "customs_declaration"},
    ]

    result = validation_engine._validate_required_documents(case, extractions, "import-regular")

    assert result is not None
    assert result.passed is True
    assert result.severity == "info"


def test_validate_required_docs_missing(validation_engine: ValidationEngine, case: CaseFile):
    """Test required docs check when some missing."""
    extractions = [
        {"doc_id": "doc-1", "doc_type": "invoice"},
        {"doc_id": "doc-2", "doc_type": "packing_list"},
    ]

    result = validation_engine._validate_required_documents(case, extractions, "import-regular")

    assert result is not None
    assert result.passed is False
    assert result.severity == "high"
    assert "Missing" in result.message


def test_validate_all_returns_list(validation_engine: ValidationEngine, case: CaseFile):
    """Test validate_all returns list of validation dicts."""
    extractions = [
        {"doc_id": "doc-1", "doc_type": "invoice", "fields": {"shipment_id": "ABC", "currency": "USD"}},
        {"doc_id": "doc-2", "doc_type": "bill_of_lading", "fields": {"bl_number": "ABC"}},
        {"doc_id": "doc-3", "doc_type": "packing_list"},
        {"doc_id": "doc-4", "doc_type": "customs_declaration"},
    ]

    import asyncio

    results = asyncio.run(validation_engine.validate_all(case, extractions, "import-regular"))

    assert isinstance(results, list)
    assert len(results) > 0

    # Each result should have required keys
    for result in results:
        assert "rule_id" in result
        assert "severity" in result
        assert "message" in result
        assert "passed" in result


def test_parse_date_valid_formats(validation_engine: ValidationEngine):
    """Test date parsing with various formats."""
    valid_dates = [
        "2025-01-15",
        "15/01/2025",
        "01/15/2025",
    ]

    for date_str in valid_dates:
        result = validation_engine._parse_date(date_str)
        assert result is not None


def test_parse_date_invalid_format(validation_engine: ValidationEngine):
    """Test date parsing with invalid format."""
    result = validation_engine._parse_date("invalid-date")
    assert result is None
