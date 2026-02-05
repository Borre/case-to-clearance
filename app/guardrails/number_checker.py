"""Number verification guardrail to prevent LLM hallucinations."""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class NumberChecker:
    """Verifies that numbers in LLM outputs match allowed source numbers."""

    def __init__(self, tolerance: float = 0.01) -> None:
        """Initialize the number checker.

        Args:
            tolerance: Tolerance for floating point comparisons (default 1%)
        """
        self.tolerance = tolerance

    def extract_numbers(self, text: str) -> set[tuple[float, str]]:
        """Extract all numbers from text with their context.

        Args:
            text: Text to extract numbers from

        Returns:
            Set of (number, context) tuples
        """
        # Match various number formats:
        # - Integers: 123
        # - Decimals: 123.45
        # - Percentages: 45%
        # - Currency: $123.45, USD 123.45
        # - Dates: 2025-01-15
        patterns = [
            (r"\$?(\d+\.?\d*)%?", "number"),  # Basic number with optional $ and %
            (r"(\d{4})-\d{2}-\d{2}", "year"),  # Year from date
        ]

        results = set()

        for pattern, context in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                try:
                    num_str = match.group(1)
                    num = float(num_str)
                    results.add((num, context))
                except ValueError:
                    continue

        return results

    def verify_numbers(
        self, output: str, allowed_numbers: set[float], allowed_context: dict[str, Any] | None = None
    ) -> tuple[bool, list[dict[str, Any]]]:
        """Verify that all numbers in output are from the allowed set.

        Args:
            output: LLM output text
            allowed_numbers: Set of numbers that are allowed to appear
            allowed_context: Optional dict with field names and their values

        Returns:
            Tuple of (is_valid, list_of_discrepancies)
        """
        discrepancies = []
        output_numbers = self.extract_numbers(output)

        for num, context in output_numbers:
            # Check if this number is allowed
            is_allowed = self._is_number_allowed(num, allowed_numbers, allowed_context)

            if not is_allowed:
                discrepancies.append({
                    "number": num,
                    "context": context,
                    "type": "disallowed_number"
                })
                logger.warning(f"Disallowed number found in output: {num} ({context})")

        return len(discrepancies) == 0, discrepancies

    def _is_number_allowed(
        self, num: float, allowed_numbers: set[float], allowed_context: dict[str, Any] | None
    ) -> bool:
        """Check if a number is allowed.

        Args:
            num: Number to check
            allowed_numbers: Set of allowed numbers
            allowed_context: Optional context dict

        Returns:
            True if number is allowed
        """
        # Direct match
        if num in allowed_numbers:
            return True

        # Check for close match (within tolerance)
        for allowed in allowed_numbers:
            if self._numbers_close(num, allowed):
                return True

        # Check context-specific numbers (e.g., score thresholds)
        if allowed_context:
            for field_name, field_value in allowed_context.items():
                if isinstance(field_value, (int, float)):
                    if self._numbers_close(num, field_value):
                        return True

        # Common numbers that are always allowed
        always_allowed = {0, 1, 2, 3, 4, 5, 10, 25, 50, 75, 100}  # Common thresholds
        if num in always_allowed:
            return True

        return False

    def _numbers_close(self, a: float, b: float) -> bool:
        """Check if two numbers are close within tolerance.

        Args:
            a: First number
            b: Second number

        Returns:
            True if numbers are close
        """
        if a == b:
            return True

        # Use relative tolerance for non-zero values
        if abs(a - b) <= max(abs(a), abs(b)) * self.tolerance:
            return True

        return False

    def verify_risk_score_numbers(
        self, explanation: dict[str, Any], score_result: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """Verify numbers in a risk explanation match the score result.

        Args:
            explanation: Generated explanation dict
            score_result: Original score result dict

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Build allowed numbers from score result
        allowed_numbers = {score_result.get("score", 0)}

        for factor in score_result.get("factors", []):
            points = factor.get("points_added", 0)
            allowed_numbers.add(points)

            input_value = factor.get("input_value")
            if isinstance(input_value, (int, float)):
                allowed_numbers.add(input_value)

        # Also add threshold values
        allowed_numbers.update([0, 25, 50, 75, 100])  # Risk level thresholds

        # Check all text in explanation
        explanation_text = json.dumps(explanation)
        is_valid, discrepancies = self.verify_numbers(explanation_text, allowed_numbers)

        if not is_valid:
            for d in discrepancies:
                issues.append(
                    f"Number {d['number']} ({d['context']}) not found in source data"
                )

        return is_valid, issues

    def verify_extraction_numbers(
        self, extraction: dict[str, Any], ocr_text: str
    ) -> tuple[bool, list[str]]:
        """Verify numbers in extraction match OCR text.

        Args:
            extraction: Extraction result dict
            ocr_text: Original OCR text

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Extract numbers from OCR text as allowed set
        ocr_numbers = {num for num, _ in self.extract_numbers(ocr_text)}

        # Check numbers in extraction fields
        fields = extraction.get("fields", {})
        for field_name, field_value in fields.items():
            if isinstance(field_value, (int, float)):
                if field_value not in ocr_numbers:
                    # Check if there's a close number in OCR
                    close_found = False
                    for ocr_num in ocr_numbers:
                        if self._numbers_close(field_value, ocr_num):
                            close_found = True
                            break

                    if not close_found:
                        issues.append(
                            f"Field {field_name}: value {field_value} not found in OCR text"
                        )

        return len(issues) == 0, issues

    def sanitize_disallowed_numbers(
        self, text: str, allowed_numbers: set[float], replacement: str = "[VALUE]"
    ) -> str:
        """Replace disallowed numbers in text with placeholder.

        Args:
            text: Text to sanitize
            allowed_numbers: Set of allowed numbers
            replacement: Replacement string

        Returns:
            Sanitized text
        """
        result = text

        # Find all numbers in text
        numbers_in_text = self.extract_numbers(text)

        # Replace disallowed numbers
        for num, context in sorted(numbers_in_text, key=lambda x: -len(str(x[0]))):
            if num not in allowed_numbers:
                # Replace this specific number
                num_pattern = r"\b" + re.escape(str(num)) + r"\b"
                result = re.sub(num_pattern, replacement, result)

        return result

    def check_percentage_values(self, text: str) -> list[dict[str, Any]]:
        """Check for percentage values that might be suspicious.

        Args:
            text: Text to check

        Returns:
            List of suspicious percentage findings
        """
        findings = []

        # Find all percentage values
        pct_pattern = r"(\d+\.?\d*)\s*%"
        matches = re.finditer(pct_pattern, text)

        for match in matches:
            value = float(match.group(1))

            # Check for suspicious values
            if value < 0:
                findings.append({
                    "value": value,
                    "issue": "negative_percentage",
                    "message": f"Negative percentage: {value}%"
                })
            elif value > 100:
                findings.append({
                    "value": value,
                    "issue": "excessive_percentage",
                    "message": f"Percentage over 100%: {value}%"
                })
            elif value == 0:
                findings.append({
                    "value": value,
                    "issue": "zero_percentage",
                    "message": f"Zero percentage may indicate missing data: {value}%"
                })

        return findings


import json  # For verify_risk_score_numbers
