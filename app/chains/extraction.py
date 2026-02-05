"""Document extraction chains for OCR text to structured fields."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.chains.prompts import (
    BL_EXTRACTION_SYSTEM,
    DECLARATION_EXTRACTION_SYSTEM,
    DOC_CLASSIFICATION_SYSTEM,
    INVOICE_EXTRACTION_SYSTEM,
    PACKING_LIST_EXTRACTION_SYSTEM,
)
from app.config import settings
from app.chains.json_fix import get_json_fix_chain
from app.guardrails import NumberChecker, OutputValidator
from app.huawei.maas import get_maas_client

logger = logging.getLogger(__name__)


class ExtractionChain:
    """Chain for extracting structured data from documents."""

    def __init__(self) -> None:
        """Initialize the extraction chain."""
        self.maas = get_maas_client()
        self.output_validator = OutputValidator()
        self.json_fixer = get_json_fix_chain()
        self.number_checker = NumberChecker()

    def _schema_name_for_doc_type(self, doc_type: str) -> str | None:
        """Map document type to schema name."""
        doc_type_key = doc_type.lower().replace("-", "_").replace("/", "_")
        return {
            "invoice": "extraction_invoice",
            "commercial_invoice": "extraction_invoice",
            "bill_of_lading": "extraction_bl",
            "bl": "extraction_bl",
            "packing_list": "extraction_packing_list",
            "pl": "extraction_packing_list",
            "declaration": "extraction_declaration",
            "customs_declaration": "extraction_declaration",
            "export_declaration": "extraction_declaration",
        }.get(doc_type_key)

    async def _parse_extraction(
        self, raw_output: str, schema_name: str | None
    ) -> dict[str, Any] | None:
        """Parse and validate extraction output with guardrails."""
        if not schema_name:
            try:
                return json.loads(raw_output)
            except json.JSONDecodeError:
                return None

        is_valid, data, error = self.output_validator.validate_json(
            raw_output, schema_name=schema_name
        )
        if is_valid and data is not None:
            return data

        if error:
            try:
                fixed = await self.json_fixer.fix_json(
                    invalid_json=raw_output,
                    error_message=error,
                    expected_schema=self.output_validator.schemas.get(schema_name),
                )
                is_valid, data, error = self.output_validator.validate_json(
                    fixed, schema_name=schema_name
                )
                if is_valid and data is not None:
                    return data
            except Exception as e:
                logger.error(f"Failed to repair extraction JSON: {e}")

        return None

    async def classify_document(self, ocr_text: str, filename: str) -> dict[str, Any]:
        """Classify the document type from OCR text.

        Args:
            ocr_text: Extracted text from OCR
            filename: Original filename

        Returns:
            Dict with doc_type, confidence, rationale
        """
        system_prompt = DOC_CLASSIFICATION_SYSTEM

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Filename: {filename}\n\nOCR Text:\n{ocr_text[:5000]}",
            },
        ]

        response = await self.maas.chat(
            messages=messages,
            model=settings.maas_model_reasoner,
            json_mode=True,
            temperature=0.2,
        )

        try:
            result = json.loads(response["content"])
        except json.JSONDecodeError:
            logger.error("Failed to parse doc classification JSON")
            result = {
                "doc_type": "other",
                "confidence": 0.0,
                "rationale": "Error parsing response",
            }

        return result

    async def extract_invoice(self, ocr_text: str, doc_id: str) -> dict[str, Any]:
        """Extract fields from a commercial invoice.

        Args:
            ocr_text: Extracted text from OCR
            doc_id: Document identifier

        Returns:
            Extraction result with fields, confidence
        """
        return await self._extract_with_template(
            ocr_text, INVOICE_EXTRACTION_SYSTEM, "invoice", doc_id
        )

    async def extract_bill_of_lading(self, ocr_text: str, doc_id: str) -> dict[str, Any]:
        """Extract fields from a bill of lading.

        Args:
            ocr_text: Extracted text from OCR
            doc_id: Document identifier

        Returns:
            Extraction result with fields, confidence
        """
        return await self._extract_with_template(
            ocr_text, BL_EXTRACTION_SYSTEM, "bill_of_lading", doc_id
        )

    async def extract_packing_list(self, ocr_text: str, doc_id: str) -> dict[str, Any]:
        """Extract fields from a packing list.

        Args:
            ocr_text: Extracted text from OCR
            doc_id: Document identifier

        Returns:
            Extraction result with fields, confidence
        """
        return await self._extract_with_template(
            ocr_text, PACKING_LIST_EXTRACTION_SYSTEM, "packing_list", doc_id
        )

    async def extract_declaration(self, ocr_text: str, doc_id: str) -> dict[str, Any]:
        """Extract fields from a customs declaration.

        Args:
            ocr_text: Extracted text from OCR
            doc_id: Document identifier

        Returns:
            Extraction result with fields, confidence
        """
        return await self._extract_with_template(
            ocr_text, DECLARATION_EXTRACTION_SYSTEM, "declaration", doc_id
        )

    async def _extract_with_template(
        self, ocr_text: str, system_template: str, doc_type: str, doc_id: str
    ) -> dict[str, Any]:
        """Extract fields using a specific template.

        Args:
            ocr_text: Extracted text from OCR
            system_template: System prompt template
            doc_type: Document type name
            doc_id: Document identifier

        Returns:
            Extraction result with fields, confidence
        """
        messages = [
            {"role": "system", "content": system_template},
            {"role": "user", "content": ocr_text[:8000]},  # Limit length
        ]

        response = await self.maas.chat(
            messages=messages,
            model=settings.maas_model_reasoner,
            json_mode=True,
            temperature=0.1,
        )

        schema_name = self._schema_name_for_doc_type(doc_type)
        data = await self._parse_extraction(response["content"], schema_name)
        if data is None:
            logger.error(f"Failed to parse {doc_type} extraction JSON after guardrails")
            data = {
                "fields": {},
                "confidence": 0.0,
                "low_confidence_fields": [],
                "missing_fields": [],
            }

        # Number audit against OCR text
        is_valid, issues = self.number_checker.verify_extraction_numbers(data, ocr_text)
        if not is_valid:
            logger.warning(f"Number audit failed for {doc_type}: {issues}")
            low_conf = data.get("low_confidence_fields", [])
            if "number_audit_mismatch" not in low_conf:
                low_conf.append("number_audit_mismatch")
            data["low_confidence_fields"] = low_conf
            data["confidence"] = min(float(data.get("confidence", 0.0)), 0.3)

        return {
            "doc_id": doc_id,
            "doc_type": doc_type,
            "fields": data.get("fields", {}),
            "confidence": data.get("confidence", 0.0),
            "low_confidence_fields": data.get("low_confidence_fields", []),
            "missing_fields": data.get("missing_fields", []),
            "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def extract_by_type(
        self, ocr_text: str, doc_type: str, doc_id: str
    ) -> dict[str, Any]:
        """Route to the appropriate extraction based on doc type.

        Args:
            ocr_text: Extracted text from OCR
            doc_type: Document type
            doc_id: Document identifier

        Returns:
            Extraction result with fields, confidence
        """
        # Map all possible doc type names to extractors
        type_extractor_map = {
            # Invoice types
            "invoice": self.extract_invoice,
            "commercial_invoice": self.extract_invoice,
            "invoice-commercial": self.extract_invoice,
            # Bill of Lading types
            "bl": self.extract_bill_of_lading,
            "bill_of_lading": self.extract_bill_of_lading,
            "bill-of-lading": self.extract_bill_of_lading,
            "b/l": self.extract_bill_of_lading,
            # Packing List types
            "packing_list": self.extract_packing_list,
            "packing-list": self.extract_packing_list,
            "pl": self.extract_packing_list,
            # Declaration types
            "declaration": self.extract_declaration,
            "customs_declaration": self.extract_declaration,
            "customs-declaration": self.extract_declaration,
            "export_declaration": self.extract_declaration,
        }

        extractor = type_extractor_map.get(doc_type.lower().replace("-", "_").replace("/", "_"))

        if extractor:
            return await extractor(ocr_text, doc_id)
        else:
            # For unknown types, do generic extraction
            logger.warning(f"No extractor found for doc_type '{doc_type}', using raw_text fallback")
            return {
                "doc_id": doc_id,
                "doc_type": doc_type,
                "fields": {"raw_text": ocr_text[:1000]},
                "confidence": 0.5,
                "low_confidence_fields": [],
                "missing_fields": [],
                "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
            }


# Global chain instance
_extraction_chain: ExtractionChain | None = None


def get_extraction_chain() -> ExtractionChain:
    """Get or create the global extraction chain."""
    global _extraction_chain
    if _extraction_chain is None:
        _extraction_chain = ExtractionChain()
    return _extraction_chain
