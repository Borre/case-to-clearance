"""Test risk scoring engine."""

import pytest
from app.rules.scoring import ScoringEngine, RiskScoreResult
from app.storage import CaseFile


@pytest.fixture
def case() -> CaseFile:
    """Create a test case."""
    case = CaseFile()
    case.procedure = {"id": "import-regular", "name": "Regular Import"}
    case.initialize_documents()
    case.initialize_citizen_intake()
    return case


@pytest.fixture
def scoring_engine() -> ScoringEngine:
    """Create scoring engine."""
    return ScoringEngine()


def test_scoring_engine_initialization(scoring_engine: ScoringEngine):
    """Test scoring engine initializes correctly."""
    assert scoring_engine.thresholds["low"] > 0
    assert scoring_engine.thresholds["medium"] > scoring_engine.thresholds["low"]
    assert scoring_engine.thresholds["high"] > scoring_engine.thresholds["medium"]


def test_get_risk_level_low(scoring_engine: ScoringEngine):
    """Test risk level LOW."""
    assert scoring_engine.get_risk_level(0) == "LOW"
    assert scoring_engine.get_risk_level(10) == "LOW"
    assert scoring_engine.get_risk_level(24) == "LOW"


def test_get_risk_level_medium(scoring_engine: ScoringEngine):
    """Test risk level MEDIUM."""
    assert scoring_engine.get_risk_level(25) == "MEDIUM"
    assert scoring_engine.get_risk_level(40) == "MEDIUM"
    assert scoring_engine.get_risk_level(49) == "MEDIUM"


def test_get_risk_level_high(scoring_engine: ScoringEngine):
    """Test risk level HIGH."""
    assert scoring_engine.get_risk_level(50) == "HIGH"
    assert scoring_engine.get_risk_level(70) == "HIGH"
    assert scoring_engine.get_risk_level(74) == "HIGH"


def test_get_risk_level_critical(scoring_engine: ScoringEngine):
    """Test risk level CRITICAL."""
    assert scoring_engine.get_risk_level(75) == "CRITICAL"
    assert scoring_engine.get_risk_level(90) == "CRITICAL"
    assert scoring_engine.get_risk_level(100) == "CRITICAL"


def test_compute_score_happy_path(scoring_engine: ScoringEngine, case: CaseFile):
    """Test score for happy path scenario (all validations passing)."""
    validations = [
        {
            "rule_id": "invoice_total_vs_declared_value",
            "passed": True,
            "severity": "info",
        },
        {
            "rule_id": "shipment_id_consistency",
            "passed": True,
            "severity": "info",
        },
        {
            "rule_id": "required_docs_check",
            "passed": True,
            "severity": "info",
        },
    ]

    extractions = [
        {
            "doc_id": "doc-1",
            "doc_type": "invoice",
            "fields": {"hs_codes": ["8471.30.00.00"]},
        }
    ]

    result = scoring_engine.compute_score(
        case=case,
        validations=validations,
        extractions=extractions,
        procedure_id="import-regular",
    )

    assert isinstance(result, RiskScoreResult)
    assert result.score < 25
    assert result.level == "LOW"
    assert result.factors == []


def test_compute_score_fraudish(scoring_engine: ScoringEngine, case: CaseFile):
    """Test score for fraudish scenario (mismatches)."""
    validations = [
        {
            "rule_id": "invoice_total_vs_declared_value",
            "passed": False,
            "severity": "high",
            "message": "Invoice total differs from declared value by 60%",
            "evidence": {"difference_percent": 60.0},
        },
        {
            "rule_id": "shipment_id_consistency",
            "passed": False,
            "severity": "high",
            "message": "Multiple shipment IDs found",
            "evidence": {"shipment_ids": ["CN-2024-12345", "CN-2024-99999"]},
        },
        {
            "rule_id": "required_docs_check",
            "passed": False,
            "severity": "high",
            "message": "Missing required documents",
            "evidence": {"missing": ["commercial_invoice"]},
        },
    ]

    extractions = [
        {
            "doc_id": "doc-1",
            "doc_type": "invoice",
            "fields": {"hs_codes": ["8471.30.00.00"]},
        }
    ]

    result = scoring_engine.compute_score(
        case=case,
        validations=validations,
        extractions=extractions,
        procedure_id="import-regular",
    )

    assert result.score >= 50  # At least medium-high
    assert result.level in ("HIGH", "CRITICAL")
    assert len(result.factors) >= 2

    # Check specific factors
    factor_ids = {f["factor_id"] for f in result.factors}
    assert "invoice_total_declared_mismatch" in factor_ids
    assert "shipment_id_inconsistency" in factor_ids


def test_compute_score_missing_docs(scoring_engine: ScoringEngine, case: CaseFile):
    """Test score for missing documents scenario."""
    validations = [
        {
            "rule_id": "required_docs_check",
            "passed": False,
            "severity": "high",
            "message": "Missing required documents",
            "evidence": {"missing": ["bill_of_lading", "commercial_invoice"]},
        },
    ]

    result = scoring_engine.compute_score(
        case=case,
        validations=validations,
        extractions=[],
        procedure_id="import-regular",
    )

    # Should get points for each missing doc (15 * 2 = 30, capped at 45)
    assert result.score >= 25
    assert len([f for f in result.factors if f["factor_id"] == "missing_required_doc"]) == 1


def test_compute_score_clamps_to_100(scoring_engine: ScoringEngine, case: CaseFile):
    """Test that score is clamped to maximum 100."""
    # Create many failing validations
    validations = [
        {
            "rule_id": "invoice_total_vs_declared_value",
            "passed": False,
            "severity": "high",
            "message": "Mismatch",
        },
        {
            "rule_id": "shipment_id_consistency",
            "passed": False,
            "severity": "high",
            "message": "Inconsistent IDs",
        },
    ] * 10  # Duplicate to exceed 100

    case.citizen_intake["collected_fields"] = {"prior_flags": ["fraud_2023"]}

    result = scoring_engine.compute_score(
        case=case,
        validations=validations,
        extractions=[],
        procedure_id="import-regular",
    )

    assert result.score <= 100


def test_score_result_to_dict(scoring_engine: ScoringEngine, case: CaseFile):
    """Test RiskScoreResult.to_dict() method."""
    result = scoring_engine.compute_score(
        case=case,
        validations=[],
        extractions=[],
        procedure_id="import-regular",
    )

    result_dict = result.to_dict()

    assert "score" in result_dict
    assert "level" in result_dict
    assert "factors" in result_dict
    assert "confidence" in result_dict
    assert "review_required" in result_dict


def test_prior_flags_adds_points(scoring_engine: ScoringEngine, case: CaseFile):
    """Test that prior flags add points to score."""
    case.citizen_intake["collected_fields"] = {"prior_flags": ["under_declaration_2023"]}

    result = scoring_engine.compute_score(
        case=case,
        validations=[],
        extractions=[],
        procedure_id="import-regular",
    )

    assert result.score >= 30  # Prior flags add 30 points
    factor_ids = {f["factor_id"] for f in result.factors}
    assert "prior_flag_present" in factor_ids
