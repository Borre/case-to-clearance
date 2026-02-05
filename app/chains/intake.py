"""Citizen intake chain for procedure classification and slot-filling."""

import logging
from typing import Any

from app.chains.prompts import (
    get_field_prompts,
    get_procedures_text,
    INTAKE_FOLLOWUP_SYSTEM,
    INTAKE_SUMMARY_SYSTEM,
    PROCEDURE_CLASSIFICATION_SYSTEM,
)
from app.config import settings
from app.chains.json_fix import get_json_fix_chain
from app.guardrails import OutputValidator
from app.huawei.maas import get_maas_client
from app.storage import CaseFile
from app.data import PROCEDURES

logger = logging.getLogger(__name__)


class IntakeChain:
    """Chain for processing citizen chat intake."""

    def __init__(self) -> None:
        """Initialize the intake chain."""
        self.maas = get_maas_client()
        self.procedures = PROCEDURES["procedures"]
        self.field_prompts = PROCEDURES.get("field_prompts", {})
        self.output_validator = OutputValidator()
        self.json_fixer = get_json_fix_chain()

    def _get_procedure_by_id(self, procedure_id: str) -> dict | None:
        """Get procedure by ID."""
        for proc in self.procedures:
            if proc["id"] == procedure_id:
                return proc
        return None

    async def _parse_classification(
        self, raw_output: str
    ) -> dict[str, Any] | None:
        """Parse and validate classification output with guardrails."""
        is_valid, data, error = self.output_validator.validate_json(
            raw_output, schema_name="intake_output"
        )
        if is_valid and data is not None:
            return data

        if error:
            try:
                fixed = await self.json_fixer.fix_json(
                    invalid_json=raw_output,
                    error_message=error,
                    expected_schema=self.output_validator.schemas.get("intake_output"),
                )
                is_valid, data, error = self.output_validator.validate_json(
                    fixed, schema_name="intake_output"
                )
                if is_valid and data is not None:
                    return data
            except Exception as e:
                logger.error(f"Failed to repair intake JSON: {e}")

        return None

    async def classify_and_collect(
        self, case: CaseFile, user_message: str
    ) -> dict[str, Any]:
        """Classify procedure and collect fields from user message.

        Args:
            case: Current CaseFile state
            user_message: User's chat message

        Returns:
            Dict with procedure classification, collected fields, and response
        """
        case.initialize_citizen_intake()

        # Build procedure text for the prompt
        procedures_text = get_procedures_text(self.procedures)

        # Try to classify procedure
        if not case.procedure.get("id"):
            result = await self._classify_procedure(user_message, procedures_text)
        else:
            # Procedure already classified, just extract fields
            result = await self._extract_fields_for_procedure(
                case, user_message, procedures_text
            )

        # Update case with collected information
        case.update_timestamp()

        return result

    async def _classify_procedure(
        self, user_message: str, procedures_text: str
    ) -> dict[str, Any]:
        """Classify the procedure from user message.

        Args:
            user_message: User's message
            procedures_text: Formatted procedures list

        Returns:
            Classification result with response
        """
        system_prompt = PROCEDURE_CLASSIFICATION_SYSTEM.format(
            procedures_text=procedures_text
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        response = await self.maas.chat(
            messages=messages,
            model=settings.maas_model_reasoner,
            json_mode=True,
            temperature=0.3,
        )

        # Parse and validate the response
        classification = await self._parse_classification(response["content"])
        if classification is None:
            logger.error("Failed to parse classification JSON after guardrails")
            classification = {
                "procedure_id": None,
                "procedure_name": None,
                "confidence": 0.0,
                "rationale": "Error parsing response",
                "detected_fields": {},
                "missing_fields": [],
            }

        valid_ids = [p["id"] for p in self.procedures]
        is_valid, error_msg = self.output_validator.validate_procedure_classification(
            classification, valid_ids
        )
        if not is_valid:
            logger.warning(f"Invalid procedure classification: {error_msg}")
            classification["procedure_id"] = None

        # Generate response
        if classification.get("procedure_id"):
            procedure = self._get_procedure_by_id(classification["procedure_id"])
            procedure_name = (
                classification.get("procedure_name")
                or (procedure["name"] if procedure else classification["procedure_id"])
            )

            if classification.get("missing_fields"):
                # Need more info
                response_text = await self._generate_followup(
                    procedure_name,
                    procedure.get("required_fields", []) if procedure else [],
                    classification.get("detected_fields", {}),
                    classification.get("missing_fields", []),
                )
            else:
                # All collected, generate summary
                response_text = await self._generate_summary(
                    procedure_name,
                    classification.get("detected_fields", {}),
                    procedure.get("required_documents", []) if procedure else [],
                )
        else:
            # Procedure unclear
            response_text = (
                f"{classification.get('rationale', '')} "
                "Please describe your customs situation more specifically, "
                "such as whether you are importing, exporting, or returning goods."
            )

        return {
            "procedure": {
                "id": classification.get("procedure_id"),
                "name": procedure_name if classification.get("procedure_id") else None,
                "confidence": classification.get("confidence", 0.0),
                "rationale": classification.get("rationale", ""),
            },
            "detected_fields": classification.get("detected_fields", {}),
            "missing_fields": classification.get("missing_fields", []),
            "response": response_text,
        }

    async def _extract_fields_for_procedure(
        self, case: CaseFile, user_message: str, procedures_text: str
    ) -> dict[str, Any]:
        """Extract fields when procedure is already known.

        Args:
            case: Current CaseFile
            user_message: User's message
            procedures_text: Formatted procedures list

        Returns:
            Extraction result with response
        """
        procedure = self._get_procedure_by_id(case.procedure["id"])
        if not procedure:
            return {
                "error": "Procedure not found",
                "response": "Sorry, there was an error with your case. Please start a new case.",
            }

        required_fields = procedure.get("required_fields", [])
        collected = case.citizen_intake.get("collected_fields", {})
        missing = [f for f in required_fields if f not in collected or not collected[f]]

        # Simple field extraction from message
        # In production, this would use an LLM call
        detected = self._extract_fields_simple(user_message, missing)

        # Update collected fields
        for field, value in detected.items():
            if value:
                collected[field] = value

        # Re-check missing
        missing = [f for f in required_fields if f not in collected or not collected[f]]

        if missing:
            response_text = await self._generate_followup(
                procedure["name"], required_fields, collected, missing
            )
        else:
            response_text = await self._generate_summary(
                procedure["name"], collected, procedure.get("required_documents", [])
            )

        return {
            "procedure": case.procedure,
            "detected_fields": detected,
            "collected_fields": collected,
            "missing_fields": missing,
            "response": response_text,
        }

    def _extract_fields_simple(self, message: str, fields: list[str]) -> dict[str, str]:
        """Simple field extraction (placeholder for LLM-based extraction).

        Args:
            message: User's message
            fields: Fields to extract

        Returns:
            Dict of extracted field values
        """
        # This is a simplified version
        # In production, use an LLM to extract specific fields
        result = {}

        message_lower = message.lower()

        # Simple pattern matching for common fields
        for field in fields:
            prompt = self.field_prompts.get(field, field)

            # Check if the message seems to answer this field
            if any(word in message_lower for word in field.split("_")):
                # In production, use LLM to extract the actual value
                result[field] = message.strip()

        return result

    async def _generate_followup(
        self,
        procedure_name: str,
        required_fields: list[str],
        collected: dict[str, str],
        missing: list[str],
    ) -> str:
        """Generate a follow-up question for missing fields.

        Args:
            procedure_name: Name of the procedure
            required_fields: All required fields
            collected: Collected field values
            missing: Missing field names

        Returns:
            Follow-up question text
        """
        if not missing:
            return await self._generate_summary(procedure_name, collected, [])

        # Get the prompt for the first missing field
        first_missing = missing[0]
        field_prompt = self.field_prompts.get(
            first_missing, f"Please provide the {first_missing.replace('_', ' ')}"
        )

        response = f"You selected **{procedure_name}**.\n\n{field_prompt}"

        return response

    async def _generate_summary(
        self,
        procedure_name: str,
        collected: dict[str, str],
        required_documents: list[str],
    ) -> str:
        """Generate a summary of collected intake.

        Args:
            procedure_name: Name of the procedure
            collected: Collected field values
            required_documents: Required document names

        Returns:
            Summary text
        """
        doc_list = "\n".join(f"- {doc}" for doc in required_documents)

        summary = f"""**Procedure Confirmed: {procedure_name}**

Information collected:
{chr(10).join(f'- {k}: {v}' for k, v in collected.items() if v)}

**Next Step:** Please upload the following documents:
{doc_list}

Once uploaded, the system will process them and provide a risk assessment."""

        return summary


# Global chain instance
_intake_chain: IntakeChain | None = None


def get_intake_chain() -> IntakeChain:
    """Get or create the global intake chain."""
    global _intake_chain
    if _intake_chain is None:
        _intake_chain = IntakeChain()
    return _intake_chain
