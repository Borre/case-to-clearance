"""Output validation guardrails for LLM responses."""

import json
import logging
import re
from typing import Any

from jsonschema import validate, ValidationError as JsonSchemaValidationError
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class OutputValidator:
    """Validates LLM outputs against schemas and business rules."""

    def __init__(self) -> None:
        """Initialize the output validator."""
        # Load JSON schemas
        self.schemas: dict[str, dict] = {}
        self._load_schemas()

    def _load_schemas(self) -> None:
        """Load JSON schemas from the schemas directory."""
        from pathlib import Path

        schema_dir = Path(__file__).parent.parent.joinpath("schemas")

        for schema_file in schema_dir.glob("*.json"):
            try:
                with schema_file.open() as f:
                    schema = json.load(f)
                    # Use filename (without .json) as schema name
                    schema_name = schema_file.stem
                    self.schemas[schema_name] = schema
                    logger.debug(f"Loaded schema: {schema_name}")
            except Exception as e:
                logger.warning(f"Failed to load schema {schema_file}: {e}")

    def validate_json(
        self, output: str, schema_name: str | None = None
    ) -> tuple[bool, dict[str, Any] | None, str | None]:
        """Validate JSON output against a schema.

        Args:
            output: JSON string to validate
            schema_name: Name of the schema to validate against

        Returns:
            Tuple of (is_valid, parsed_data, error_message)
        """
        # First, try to parse JSON
        try:
            data = json.loads(output)
        except json.JSONDecodeError as e:
            return False, None, f"Invalid JSON: {e.msg}"

        # If no schema specified, just return the parsed data
        if not schema_name:
            return True, data, None

        # Validate against schema if specified
        schema = self.schemas.get(schema_name)
        if not schema:
            logger.warning(f"Schema not found: {schema_name}")
            return True, data, None  # Allow if schema not found

        try:
            validate(instance=data, schema=schema)
            return True, data, None
        except JsonSchemaValidationError as e:
            error_path = " -> ".join(str(p) for p in e.path)
            return False, data, f"Schema validation failed at {error_path}: {e.message}"

    def sanitize_output(self, output: str, allowed_patterns: list[str] | None = None) -> str:
        """Sanitize LLM output to remove potentially harmful content.

        Args:
            output: Raw LLM output
            allowed_patterns: List of regex patterns to allow

        Returns:
            Sanitized output string
        """
        # Remove common injection patterns
        dangerous_patterns = [
            r"<script[^>]*>.*?</script>",  # Script tags
            r"javascript:",  # JavaScript protocol
            r"data:",  # Data URI (can be used for injection)
            r"vbscript:",  # VBScript protocol
            r"on\w+\s*=",  # Event handlers (onclick=, etc.)
        ]

        sanitized = output
        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE | re.DOTALL)

        # If allowed patterns specified, only keep those
        if allowed_patterns:
            combined_pattern = "|".join(f"({p})" for p in allowed_patterns)
            matches = re.findall(combined_pattern, sanitized, flags=re.DOTALL)
            sanitized = "\n".join(m[0] if isinstance(m, tuple) else m for m in matches)

        return sanitized

    def validate_procedure_classification(
        self, output: dict[str, Any], valid_procedures: list[str]
    ) -> tuple[bool, str | None]:
        """Validate procedure classification output.

        Args:
            output: Parsed classification output
            valid_procedures: List of valid procedure IDs

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        required_fields = ["procedure_id", "confidence", "rationale"]
        for field in required_fields:
            if field not in output:
                return False, f"Missing required field: {field}"

        # Validate procedure_id is in allowed list
        procedure_id = output.get("procedure_id")
        if procedure_id and procedure_id not in valid_procedures:
            return False, f"Invalid procedure_id: {procedure_id}"

        # Validate confidence is between 0 and 1
        confidence = output.get("confidence")
        if confidence is not None and not (0 <= confidence <= 1):
            return False, f"Confidence must be between 0 and 1, got {confidence}"

        return True, None

    def validate_extraction_output(
        self, output: dict[str, Any], doc_type: str
    ) -> tuple[bool, str | None]:
        """Validate field extraction output.

        Args:
            output: Parsed extraction output
            doc_type: Document type

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        required_fields = ["fields", "confidence"]
        for field in required_fields:
            if field not in output:
                return False, f"Missing required field: {field}"

        # Validate confidence
        confidence = output.get("confidence")
        if confidence is not None and not (0 <= confidence <= 1):
            return False, f"Confidence must be between 0 and 1, got {confidence}"

        # Validate fields is a dict
        if not isinstance(output.get("fields"), dict):
            return False, "Fields must be a dictionary"

        # Check for low_confidence_fields and missing_fields lists
        for list_field in ["low_confidence_fields", "missing_fields"]:
            if list_field in output and not isinstance(output[list_field], list):
                return False, f"{list_field} must be a list"

        return True, None

    def validate_risk_explanation(
        self, output: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """Validate risk explanation output.

        Args:
            output: Parsed explanation output

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        required_fields = [
            "executive_summary",
            "explanation_bullets",
            "recommended_next_actions",
        ]
        for field in required_fields:
            if field not in output:
                return False, f"Missing required field: {field}"

        # Validate list fields
        for list_field in ["explanation_bullets", "recommended_next_actions"]:
            if not isinstance(output.get(list_field), list):
                return False, f"{list_field} must be a list"

        # Check that executive_summary is a non-empty string
        summary = output.get("executive_summary", "")
        if not isinstance(summary, str) or len(summary) < 10:
            return False, "Executive summary must be a string with at least 10 characters"

        # Check for disclaimer presence
        disclaimer_keywords = ["advisory", "review", "qualified", "responsibility"]
        summary_lower = summary.lower()
        if not any(kw in summary_lower for kw in disclaimer_keywords):
            logger.warning("Disclaimer may be missing from executive summary")

        return True, None

    def check_for_hallucinations(
        self, output: dict[str, Any], source_data: dict[str, Any]
    ) -> list[str]:
        """Check for potential hallucinations in LLM output.

        Args:
            output: LLM output dict
            source_data: Source data that was provided to the LLM

        Returns:
            List of potential hallucination warnings
        """
        warnings = []

        # Check for numbers that don't appear in source
        output_numbers = self._extract_numbers(json.dumps(output))
        source_numbers = self._extract_numbers(json.dumps(source_data))

        hallucinated_numbers = output_numbers - source_numbers
        if hallucinated_numbers:
            warnings.append(f"Numbers in output not found in source: {hallucinated_numbers}")

        # Check for entity names that don't appear in source
        output_text = json.dumps(output).lower()
        source_text = json.dumps(source_data).lower()

        # Common entity patterns (names, IDs, etc.)
        entity_pattern = r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b"
        output_entities = set(re.findall(entity_pattern, output))
        source_entities = set(re.findall(entity_pattern, source_text))

        hallucinated_entities = output_entities - source_entities
        if hallucinated_entities:
            warnings.append(f"Entities in output not found in source: {hallucinated_entities}")

        return warnings

    def _extract_numbers(self, text: str) -> set[float]:
        """Extract all numbers from text.

        Args:
            text: Text to extract numbers from

        Returns:
            Set of numbers found
        """
        # Match integers, decimals, percentages
        numbers = re.findall(r"\d+\.?\d*%", text)  # Percentages
        numbers += re.findall(r"\d+\.?\d*", text)  # Regular numbers

        result = set()
        for num in numbers:
            try:
                if "%" in num:
                    result.add(float(num.strip("%")))
                else:
                    result.add(float(num))
            except ValueError:
                pass

        return result


class SafetyValidator:
    """Validates outputs for safety and policy compliance."""

    # Blocked content patterns
    BLOCKED_PATTERNS = [
        r"ignore\s+(all\s+)?(previous\s+)?instructions",
        r"override\s+safety",
        r"bypass\s+security",
        r"execute\s+code",
        r"run\s+command",
        r"system\s*:\s*\S*\s*<<<",  # System prompt injection attempt
    ]

    # PII patterns (basic)
    PII_PATTERNS = [
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN format
        r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",  # Credit card
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
    ]

    def __init__(self) -> None:
        """Initialize the safety validator."""
        self.blocked_regex = re.compile(
            "|".join(f"({p})" for p in self.BLOCKED_PATTERNS), re.IGNORECASE
        )
        self.pii_regex = re.compile(
            "|".join(f"({p})" for p in self.PII_PATTERNS), re.IGNORECASE
        )

    def check_safety(self, output: str) -> tuple[bool, list[str]]:
        """Check output for safety violations.

        Args:
            output: Output text to check

        Returns:
            Tuple of (is_safe, list of violations)
        """
        violations = []

        # Check for blocked patterns
        blocked_matches = self.blocked_regex.findall(output)
        if blocked_matches:
            violations.append("Blocked content patterns detected")
            violations.extend(m[0] for m in blocked_matches[:3])  # First 3 matches

        # Check for PII (warning only, not blocking)
        pii_matches = self.pii_regex.findall(output)
        if pii_matches:
            violations.append(f"Potential PII detected: {len(pii_matches)} instances")

        # Check for excessively long output (potential infinite loop)
        if len(output) > 50000:  # 50k characters
            violations.append("Output exceeds maximum length")

        return len(violations) == 0, violations

    def redact_pii(self, text: str) -> tuple[str, int]:
        """Redact PII from text.

        Args:
            text: Text to redact

        Returns:
            Tuple of (redacted_text, count_of_redactions)
        """
        redacted = text
        count = 0

        # Redact emails
        def redact_email(match):
            nonlocal count
            count += 1
            return "[EMAIL_REDACTED]"

        redacted = re.sub(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            redact_email,
            redacted,
        )

        # Redact SSN-like patterns
        def redact_ssn(match):
            nonlocal count
            count += 1
            return "***-**-****"

        redacted = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", redact_ssn, redacted)

        # Redact credit card-like patterns
        def redact_cc(match):
            nonlocal count
            count += 1
            return "****-****-****-****"

        redacted = re.sub(
            r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", redact_cc, redacted
        )

        return redacted, count
