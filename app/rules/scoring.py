"""Risk scoring engine for customs clearance."""

import logging
from typing import Any

from app.data import SCORING_RULES

logger = logging.getLogger(__name__)


class RiskScoreResult:
    """Result of risk scoring."""

    def __init__(
        self,
        score: int,
        level: str,
        factors: list[dict[str, Any]],
        threshold_config: dict[str, int],
    ) -> None:
        """Initialize risk score result.

        Args:
            score: Numeric risk score (0-100)
            level: Risk level (LOW/MEDIUM/HIGH/CRITICAL)
            factors: List of triggered risk factors
            threshold_config: Threshold configuration used
        """
        self.score = max(0, min(100, score))  # Clamp to 0-100
        self.level = level
        self.factors = factors
        self.threshold_config = threshold_config

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "score": self.score,
            "level": self.level,
            "factors": self.factors,
            "confidence": "HIGH",
            "review_required": self.level in ("HIGH", "CRITICAL"),
        }


class ScoringEngine:
    """Engine for computing risk scores."""

    def __init__(self) -> None:
        """Initialize the scoring engine."""
        self.rules = SCORING_RULES.get("rules", [])
        self.thresholds = SCORING_RULES.get("thresholds", {})

        # Set default thresholds
        if "low" not in self.thresholds:
            self.thresholds = {"low": 25, "medium": 50, "high": 75, "critical": 90}

    def get_risk_level(self, score: int) -> str:
        """Get risk level from score.

        Args:
            score: Numeric risk score

        Returns:
            Risk level string
        """
        if score < self.thresholds["low"]:
            return "LOW"
        elif score < self.thresholds["medium"]:
            return "MEDIUM"
        elif score < self.thresholds["high"]:
            return "HIGH"
        else:
            return "CRITICAL"

    def compute_score(
        self,
        case: Any,
        validations: list[dict],
        extractions: list[dict],
        procedure_id: str,
    ) -> RiskScoreResult:
        """Compute risk score from case data.

        Args:
            case: CaseFile object
            validations: List of validation results
            extractions: List of document extractions
            procedure_id: Procedure ID

        Returns:
            RiskScoreResult
        """
        factors = []
        total_score = 0

        # Rule 1: Invoice total vs declared value mismatch
        factor = self._score_invoice_vs_declared(validations)
        if factor:
            factors.append(factor)
            total_score += factor["points_added"]

        # Rule 2: Shipment ID inconsistency
        factor = self._score_shipment_id_consistency(validations)
        if factor:
            factors.append(factor)
            total_score += factor["points_added"]

        # Rule 3: Date sequence violation
        factor = self._score_date_sequence(validations)
        if factor:
            factors.append(factor)
            total_score += factor["points_added"]

        # Rule 4: Missing required documents
        factor = self._score_missing_docs(validations)
        if factor:
            factors.append(factor)
            total_score += factor["points_added"]

        # Rule 5: Currency mismatch
        factor = self._score_currency_mismatch(validations)
        if factor:
            factors.append(factor)
            total_score += factor["points_added"]

        # Rule 6: Prior flags (from intake)
        factor = self._score_prior_flags(case)
        if factor:
            factors.append(factor)
            total_score += factor["points_added"]

        # Rule 7: HS code mismatch
        factor = self._score_hs_code_mismatch(extractions)
        if factor:
            factors.append(factor)
            total_score += factor["points_added"]

        # Ensure score is within bounds
        total_score = max(0, min(100, total_score))

        # Determine risk level
        level = self.get_risk_level(total_score)

        return RiskScoreResult(
            score=total_score,
            level=level,
            factors=factors,
            threshold_config=self.thresholds,
        )

    def _score_invoice_vs_declared(self, validations: list[dict]) -> dict[str, Any] | None:
        """Score invoice vs declared value mismatch.

        Args:
            validations: List of validation results

        Returns:
            Factor dict or None
        """
        for v in validations:
            if v.get("rule_id") == "invoice_total_vs_declared_value" and not v.get("passed"):
                return {
                    "factor_id": "invoice_total_declared_mismatch",
                    "description": v.get("message", "Invoice total differs from declared value"),
                    "input_value": v.get("evidence", {}).get("difference_percent", 0),
                    "points_added": 25,
                }
        return None

    def _score_shipment_id_consistency(self, validations: list[dict]) -> dict[str, Any] | None:
        """Score shipment ID inconsistency.

        Args:
            validations: List of validation results

        Returns:
            Factor dict or None
        """
        for v in validations:
            if v.get("rule_id") == "shipment_id_consistency" and not v.get("passed"):
                return {
                    "factor_id": "shipment_id_inconsistency",
                    "description": v.get("message", "Shipment IDs are inconsistent"),
                    "input_value": v.get("evidence", {}).get("shipment_ids", []),
                    "points_added": 20,
                }
        return None

    def _score_date_sequence(self, validations: list[dict]) -> dict[str, Any] | None:
        """Score date sequence violations.

        Args:
            validations: List of validation results

        Returns:
            Factor dict or None
        """
        for v in validations:
            if v.get("rule_id") == "date_order_sanity" and not v.get("passed"):
                return {
                    "factor_id": "date_sequence_violation",
                    "description": v.get("message", "Document dates violate logical sequence"),
                    "input_value": v.get("evidence", {}).get("issues", []),
                    "points_added": 10,
                }
        return None

    def _score_missing_docs(self, validations: list[dict]) -> dict[str, Any] | None:
        """Score missing required documents.

        Args:
            validations: List of validation results

        Returns:
            Factor dict or None
        """
        for v in validations:
            if v.get("rule_id") == "required_docs_check" and not v.get("passed"):
                missing = v.get("evidence", {}).get("missing", [])
                count = len(missing)
                if count > 0:
                    return {
                        "factor_id": "missing_required_doc",
                        "description": f"Missing {count} required document(s): {', '.join(missing)}",
                        "input_value": missing,
                        "points_added": min(15 * count, 45),  # Cap at 45 points
                    }
        return None

    def _score_currency_mismatch(self, validations: list[dict]) -> dict[str, Any] | None:
        """Score currency inconsistencies.

        Args:
            validations: List of validation results

        Returns:
            Factor dict or None
        """
        for v in validations:
            if v.get("rule_id") == "currency_sanity" and not v.get("passed"):
                return {
                    "factor_id": "currency_mismatch",
                    "description": v.get("message", "Multiple currencies without conversion"),
                    "input_value": v.get("evidence", {}).get("currencies", []),
                    "points_added": 10,
                }
        return None

    def _score_prior_flags(self, case: Any) -> dict[str, Any] | None:
        """Score prior compliance flags.

        Args:
            case: CaseFile object

        Returns:
            Factor dict or None
        """
        intake = case.citizen_intake or {}
        collected = intake.get("collected_fields", {})

        if collected.get("prior_flags"):
            return {
                "factor_id": "prior_flag_present",
                "description": "Entity has prior compliance flags",
                "input_value": collected.get("prior_flags"),
                "points_added": 30,
            }
        return None

    def _score_hs_code_mismatch(self, extractions: list[dict]) -> dict[str, Any] | None:
        """Score HS code mismatches.

        Args:
            extractions: List of document extractions

        Returns:
            Factor dict or None
        """
        hs_codes_by_doc = {}

        for ext in extractions:
            doc_id = ext.get("doc_id")
            doc_type = ext.get("doc_type")
            fields = ext.get("fields", {})
            hs_codes = fields.get("hs_codes", [])

            if hs_codes:
                if isinstance(hs_codes, str):
                    hs_codes = [hs_codes]
                hs_codes_by_doc[doc_id] = {"doc_type": doc_type, "hs_codes": hs_codes}

        # Check for inconsistencies
        all_hs_codes = set()
        for doc_data in hs_codes_by_doc.values():
            all_hs_codes.update(doc_data["hs_codes"])

        if len(all_hs_codes) > 1:
            return {
                "factor_id": "hs_code_mismatch",
                "description": f"Different HS codes found across documents: {list(all_hs_codes)}",
                "input_value": list(all_hs_codes),
                "points_added": 15,
            }

        return None


# Global engine instance
_scoring_engine: ScoringEngine | None = None


def get_scoring_engine() -> ScoringEngine:
    """Get or create the global scoring engine."""
    global _scoring_engine
    if _scoring_engine is None:
        _scoring_engine = ScoringEngine()
    return _scoring_engine
