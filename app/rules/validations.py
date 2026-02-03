"""Validation rules for customs document processing."""

import logging
from datetime import datetime
from typing import Any

from app.data import REQUIRED_DOCS

logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of a validation rule."""

    def __init__(
        self,
        rule_id: str,
        severity: str,
        message: str,
        evidence: dict[str, Any] | None = None,
        passed: bool = False,
    ) -> None:
        """Initialize validation result.

        Args:
            rule_id: Unique rule identifier
            severity: Severity level (info, warn, high, critical)
            message: Human-readable message
            evidence: Evidence dict with doc_ids, field names, etc.
            passed: Whether the validation passed
        """
        self.rule_id = rule_id
        self.severity = severity
        self.message = message
        self.evidence = evidence or {}
        self.passed = passed

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "message": self.message,
            "evidence": self.evidence,
            "passed": self.passed,
        }


class ValidationEngine:
    """Engine for running validation rules."""

    def __init__(self) -> None:
        """Initialize the validation engine."""
        self.validations = {
            "invoice_total_vs_declared_value": self._validate_invoice_vs_declared,
            "shipment_id_consistency": self._validate_shipment_id_consistency,
            "currency_sanity": self._validate_currency_consistency,
            "date_order_sanity": self._validate_date_sequence,
            "required_docs_check": self._validate_required_documents,
            "hs_code_consistency": self._validate_hs_code_consistency,
        }

    async def validate_all(
        self,
        case: Any,
        extractions: list[dict],
        procedure_id: str,
    ) -> list[dict]:
        """Run all validation rules.

        Args:
            case: CaseFile object
            extractions: List of document extractions
            procedure_id: Selected procedure ID

        Returns:
            List of validation results as dicts
        """
        results = []

        for rule_id, validator in self.validations.items():
            try:
                result = validator(case, extractions, procedure_id)
                if result:
                    results.append(result.to_dict())
            except Exception as e:
                logger.error(f"Validation {rule_id} failed: {e}")
                # Don't fail on validation errors, just log and continue

        return results

    def _validate_invoice_vs_declared(
        self, case: Any, extractions: list[dict], procedure_id: str
    ) -> ValidationResult | None:
        """Validate invoice total matches declared value.

        Args:
            case: CaseFile object
            extractions: List of document extractions
            procedure_id: Procedure ID

        Returns:
            ValidationResult or None if not applicable
        """
        # Extract invoice total
        invoice_total = None
        invoice_doc_id = None

        for ext in extractions:
            if ext.get("doc_type") == "invoice":
                invoice_total = ext.get("fields", {}).get("total_amount")
                invoice_doc_id = ext.get("doc_id")
                break

        # Extract declared value
        declared_value = None
        declaration_doc_id = None

        for ext in extractions:
            if ext.get("doc_type") in ("declaration", "customs_declaration"):
                declared_value = ext.get("fields", {}).get("declared_value")
                declaration_doc_id = ext.get("doc_id")
                break

        if invoice_total is None or declared_value is None:
            return None  # Can't validate without both values

        # Try to convert to float
        try:
            invoice_total_float = float(str(invoice_total).replace(",", "").replace("$", ""))
            declared_value_float = float(str(declared_value).replace(",", "").replace("$", ""))
        except (ValueError, AttributeError):
            return ValidationResult(
                rule_id="invoice_total_vs_declared_value",
                severity="warn",
                message="Could not compare invoice total to declared value due to format issues",
                evidence={"invoice_total": invoice_total, "declared_value": declared_value},
                passed=False,
            )

        # Calculate difference
        if declared_value_float > 0:
            diff_pct = abs(invoice_total_float - declared_value_float) / declared_value_float
        else:
            diff_pct = 0

        threshold = 0.10  # 10%

        if diff_pct > threshold:
            return ValidationResult(
                rule_id="invoice_total_vs_declared_value",
                severity="high",
                message=f"Invoice total ({invoice_total}) differs from declared value ({declared_value}) by {diff_pct*100:.1f}%",
                evidence={
                    "invoice_total": invoice_total,
                    "declared_value": declared_value,
                    "difference_percent": round(diff_pct * 100, 2),
                    "doc_ids": [invoice_doc_id, declaration_doc_id],
                },
                passed=False,
            )
        else:
            return ValidationResult(
                rule_id="invoice_total_vs_declared_value",
                severity="info",
                message=f"Invoice total matches declared value within threshold",
                evidence={
                    "invoice_total": invoice_total,
                    "declared_value": declared_value,
                    "difference_percent": round(diff_pct * 100, 2),
                },
                passed=True,
            )

    def _validate_shipment_id_consistency(
        self, case: Any, extractions: list[dict], procedure_id: str
    ) -> ValidationResult | None:
        """Validate shipment IDs are consistent across documents.

        Args:
            case: CaseFile object
            extractions: List of document extractions
            procedure_id: Procedure ID

        Returns:
            ValidationResult or None if not applicable
        """
        shipment_ids = {}

        for ext in extractions:
            doc_id = ext.get("doc_id")
            doc_type = ext.get("doc_type")
            fields = ext.get("fields", {})

            # Look for shipment_id in various field names
            for field_name in ["shipment_id", "bl_number", "pl_number"]:
                value = fields.get(field_name)
                if value:
                    if value not in shipment_ids:
                        shipment_ids[value] = []
                    shipment_ids[value].append({"doc_id": doc_id, "doc_type": doc_type, "field": field_name})

        if len(shipment_ids) <= 1:
            return ValidationResult(
                rule_id="shipment_id_consistency",
                severity="info",
                message="Shipment IDs are consistent across documents",
                evidence={"shipment_ids": list(shipment_ids.keys())},
                passed=True,
            )

        # Inconsistent IDs
        return ValidationResult(
            rule_id="shipment_id_consistency",
            severity="high",
            message=f"Multiple different shipment IDs found across documents: {list(shipment_ids.keys())}",
            evidence={"shipment_ids": shipment_ids},
            passed=False,
        )

    def _validate_currency_consistency(
        self, case: Any, extractions: list[dict], procedure_id: str
    ) -> ValidationResult | None:
        """Validate currency consistency.

        Args:
            case: CaseFile object
            extractions: List of document extractions
            procedure_id: Procedure ID

        Returns:
            ValidationResult or None if not applicable
        """
        currencies = set()

        for ext in extractions:
            fields = ext.get("fields", {})
            currency = fields.get("currency")
            if currency:
                currencies.add(str(currency).upper())

        if len(currencies) <= 1:
            return ValidationResult(
                rule_id="currency_sanity",
                severity="info",
                message="Currency is consistent across documents",
                evidence={"currencies": list(currencies)},
                passed=True,
            )

        return ValidationResult(
            rule_id="currency_sanity",
            severity="warn",
            message=f"Multiple currencies found: {list(currencies)} - verify conversion is documented",
            evidence={"currencies": list(currencies)},
            passed=False,
        )

    def _validate_date_sequence(
        self, case: Any, extractions: list[dict], procedure_id: str
    ) -> ValidationResult | None:
        """Validate logical date sequence.

        Args:
            case: CaseFile object
            extractions: List of document extractions
            procedure_id: Procedure ID

        Returns:
            ValidationResult or None if not applicable
        """
        dates = {}

        for ext in extractions:
            doc_id = ext.get("doc_id")
            doc_type = ext.get("doc_type")
            fields = ext.get("fields", {})

            # Look for dates in various field names
            for field_name in ["invoice_date", "bl_date", "pl_date", "declaration_date"]:
                value = fields.get(field_name)
                if value:
                    try:
                        # Try to parse date
                        date_obj = self._parse_date(value)
                        if date_obj:
                            dates[doc_type] = {
                                "date": date_obj,
                                "doc_id": doc_id,
                                "field": field_name,
                            }
                    except Exception:
                        pass

        if len(dates) < 2:
            return None  # Can't validate with fewer than 2 dates

        # Check sequence: invoice < bl < declaration (for imports)
        issues = []
        # Map various doc_type names to canonical names
        doc_type_map = {
            "commercial_invoice": "invoice",
            "invoice": "invoice",
            "bill_of_lading": "bill_of_lading",
            "bl": "bill_of_lading",
            "customs_declaration": "declaration",
            "declaration": "declaration",
        }

        # Remap dates with canonical names
        canonical_dates = {}
        for doc_type, date_info in dates.items():
            canonical = doc_type_map.get(doc_type, doc_type)
            if canonical not in canonical_dates:
                canonical_dates[canonical] = date_info

        date_order = ["invoice", "bill_of_lading", "declaration"]

        for i in range(len(date_order) - 1):
            first_type = date_order[i]
            second_type = date_order[i + 1]

            if first_type in canonical_dates and second_type in canonical_dates:
                if canonical_dates[first_type]["date"] > canonical_dates[second_type]["date"]:
                    issues.append(
                        f"{first_type} date ({canonical_dates[first_type]['date'].date()}) "
                        f"is after {second_type} date ({canonical_dates[second_type]['date'].date()})"
                    )

        if issues:
            return ValidationResult(
                rule_id="date_order_sanity",
                severity="warn",
                message="Document dates may be out of logical sequence: " + "; ".join(issues),
                evidence={"issues": issues, "dates": dates},
                passed=False,
            )

        return ValidationResult(
            rule_id="date_order_sanity",
            severity="info",
            message="Document dates follow logical sequence",
            evidence={"dates": {k: str(v["date"]) for k, v in dates.items()}},
            passed=True,
        )

    def _validate_required_documents(
        self, case: Any, extractions: list[dict], procedure_id: str
    ) -> ValidationResult | None:
        """Validate required documents are present.

        Args:
            case: CaseFile object
            extractions: List of document extractions
            procedure_id: Procedure ID

        Returns:
            ValidationResult or None if not applicable
        """
        from app.data import REQUIRED_DOCS

        procedure_docs = REQUIRED_DOCS.get(procedure_id, {})
        required_doc_types = procedure_docs.get("required", [])

        # Map document types
        doc_types_found = {ext.get("doc_type") for ext in extractions}

        missing = []
        for req in required_doc_types:
            req_type = req.get("doc_type")
            if req_type not in doc_types_found:
                missing.append(req.get("description", req_type))

        if missing:
            return ValidationResult(
                rule_id="required_docs_check",
                severity="high",
                message=f"Missing required documents: {', '.join(missing)}",
                evidence={
                    "missing": missing,
                    "found": list(doc_types_found),
                    "required": [r.get("doc_type") for r in required_doc_types],
                },
                passed=False,
            )

        return ValidationResult(
            rule_id="required_docs_check",
            severity="info",
            message="All required documents are present",
            evidence={"found": list(doc_types_found)},
            passed=True,
        )

    def _validate_hs_code_consistency(
        self, case: Any, extractions: list[dict], procedure_id: str
    ) -> ValidationResult | None:
        """Validate HS codes are consistent.

        Args:
            case: CaseFile object
            extractions: List of document extractions
            procedure_id: Procedure ID

        Returns:
            ValidationResult or None if not applicable
        """
        all_hs_codes = set()

        for ext in extractions:
            fields = ext.get("fields", {})
            hs_codes = fields.get("hs_codes", [])
            if isinstance(hs_codes, list):
                all_hs_codes.update(hs_codes)
            elif isinstance(hs_codes, str):
                all_hs_codes.add(hs_codes)

        if not all_hs_codes:
            return None  # No HS codes found

        if len(all_hs_codes) == 1:
            return ValidationResult(
                rule_id="hs_code_consistency",
                severity="info",
                message=f"HS code is consistent: {list(all_hs_codes)[0]}",
                evidence={"hs_codes": list(all_hs_codes)},
                passed=True,
            )

        return ValidationResult(
            rule_id="hs_code_consistency",
            severity="info",
            message=f"Multiple HS codes found: {list(all_hs_codes)}",
            evidence={"hs_codes": list(all_hs_codes)},
            passed=True,  # Multiple HS codes is not necessarily an error
        )

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse various date formats.

        Args:
            date_str: Date string

        Returns:
            Datetime object or None
        """
        if not date_str:
            return None

        # Common formats
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%d-%m-%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str[:10], fmt)
            except ValueError:
                continue

        return None


# Global engine instance
_validation_engine: ValidationEngine | None = None


def get_validation_engine() -> ValidationEngine:
    """Get or create the global validation engine."""
    global _validation_engine
    if _validation_engine is None:
        _validation_engine = ValidationEngine()
    return _validation_engine
