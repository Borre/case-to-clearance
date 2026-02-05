"""Risk triage and explanation generation chains."""

import json
import logging
import re
from typing import Any

from app.chains.prompts import RISK_EXPLANATION_SYSTEM
from app.chains.json_fix import get_json_fix_chain
from app.config import settings
from app.guardrails import NumberChecker, OutputValidator
from app.huawei.maas import get_maas_client
from app.rules.scoring import RiskScoreResult

logger = logging.getLogger(__name__)


class TriageChain:
    """Chain for risk assessment and explanation generation."""

    def __init__(self) -> None:
        """Initialize the triage chain."""
        self.maas = get_maas_client()
        self.output_validator = OutputValidator()
        self.json_fixer = get_json_fix_chain()
        self.number_checker = NumberChecker()

    async def generate_explanation(
        self,
        score_result: RiskScoreResult,
        language: str = "es",
    ) -> dict[str, Any]:
        """Generate a risk explanation for the citizen.

        Args:
            score_result: Risk score result from scoring engine
            language: Response language (es/en)

        Returns:
            Dict with explanation components
        """
        # Build factors table
        factors_table = "\n".join(
            f"- [{f['factor_id']}] {f['description']}: +{f['points_added']} points"
            for f in score_result.factors
        )

        system_prompt = RISK_EXPLANATION_SYSTEM.format(
            score=score_result.score,
            level=score_result.level,
            factors_table=factors_table,
            language=language,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate the risk explanation."},
        ]

        response = await self.maas.chat(
            messages=messages,
            model=settings.maas_model_writer,
            json_mode=True,
            temperature=0.7,
        )

        explanation = await self._parse_explanation(response["content"])
        if explanation is None:
            logger.error("Failed to parse explanation JSON after guardrails")
            explanation = self._get_fallback_explanation(score_result)

        # Verify numbers in explanation (fallback if mismatch)
        score_dict = score_result.to_dict()
        score_dict["factors"] = score_result.factors
        numbers_ok, issues = self.number_checker.verify_risk_score_numbers(
            explanation, score_dict
        )
        if not numbers_ok:
            logger.warning(f"Number audit failed for explanation: {issues}")
            explanation = self._get_fallback_explanation(score_result)

        return explanation

    async def _parse_explanation(self, raw_output: str) -> dict[str, Any] | None:
        """Parse and validate explanation output with guardrails."""
        is_valid, data, error = self.output_validator.validate_json(
            raw_output, schema_name="triage_explanation"
        )
        if is_valid and data is not None:
            return data

        if error:
            try:
                fixed = await self.json_fixer.fix_json(
                    invalid_json=raw_output,
                    error_message=error,
                    expected_schema=self.output_validator.schemas.get("triage_explanation"),
                )
                is_valid, data, error = self.output_validator.validate_json(
                    fixed, schema_name="triage_explanation"
                )
                if is_valid and data is not None:
                    return data
            except Exception as e:
                logger.error(f"Failed to repair triage JSON: {e}")

        return None

    def _verify_numbers(
        self, explanation: dict[str, Any], score_result: RiskScoreResult
    ) -> dict[str, Any]:
        """Verify that numbers in explanation are from allowed set.

        Args:
            explanation: Generated explanation dict
            score_result: Risk score result

        Returns:
            Verified explanation dict
        """
        # Build allowed numbers set
        allowed = {score_result.score}

        for factor in score_result.factors:
            allowed.add(factor["points_added"])
            if isinstance(factor.get("input_value"), (int, float)):
                allowed.add(factor["input_value"])

        # Extract all numbers from explanation
        explanation_text = json.dumps(explanation)
        found_numbers = set(map(float, re.findall(r"\d+\.?\d*", explanation_text)))

        # Check if any found number is not in allowed
        disallowed = found_numbers - allowed

        if disallowed:
            logger.warning(f"Found disallowed numbers in explanation: {disallowed}")
            # Remove or replace disallowed numbers
            explanation = self._sanitize_numbers(explanation, allowed)

        return explanation

    def _sanitize_numbers(
        self, explanation: dict[str, Any], allowed: set[float]
    ) -> dict[str, Any]:
        """Remove or replace disallowed numbers.

        Args:
            explanation: Explanation dict
            allowed: Set of allowed numbers

        Returns:
            Sanitized explanation dict
        """
        # For now, just return the explanation as-is
        # In production, you might want to regenerate or fix specific fields
        return explanation

    def _get_fallback_explanation(self, score_result: RiskScoreResult) -> dict[str, Any]:
        """Get a fallback explanation when LLM fails.

        Args:
            score_result: Risk score result

        Returns:
            Fallback explanation dict
        """
        factor_bullets = [
            f"[{f['factor_id']}] {f['description']}" for f in score_result.factors
        ]

        return {
            "executive_summary": f"Risk assessment complete. Score: {score_result.score}/100 ({score_result.level}). "
            + settings.disclaimer,
            "explanation_bullets": factor_bullets,
            "recommended_next_actions": [
                "Review all documents for accuracy",
                "Ensure all required fields are complete",
                "Address any flagged inconsistencies",
            ],
            "risk_reduction_actions": [
                "Correct any data mismatches",
                "Provide missing documentation",
                "Add explanatory notes for any discrepancies",
            ],
        }

    async def process_risk_assessment(
        self,
        case: Any,
        validations: list[dict],
        extractions: list[dict],
        procedure_id: str,
    ) -> dict[str, Any]:
        """Run the full risk assessment pipeline.

        Args:
            case: CaseFile object
            validations: List of validation results
            extractions: List of document extractions
            procedure_id: Procedure ID

        Returns:
            Dict with score, level, factors, explanation
        """
        from app.rules.scoring import get_scoring_engine

        # Compute score
        scoring_engine = get_scoring_engine()
        score_result = scoring_engine.compute_score(case, validations, extractions, procedure_id)

        # Generate explanation
        explanation = await self.generate_explanation(score_result)

        # Combine results
        return {
            "score": score_result.score,
            "level": score_result.level,
            "factors": score_result.factors,
            "explanation": explanation,
            "confidence": "HIGH",
            "review_required": score_result.level in ("HIGH", "CRITICAL"),
        }


# Global chain instance
_triage_chain: TriageChain | None = None


def get_triage_chain() -> TriageChain:
    """Get or create the global triage chain."""
    global _triage_chain
    if _triage_chain is None:
        _triage_chain = TriageChain()
    return _triage_chain
