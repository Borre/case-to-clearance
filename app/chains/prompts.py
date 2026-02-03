"""Prompt templates for LLM chains."""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# ============================================================================
# CITIZEN INTAKE PROMPTS
# ============================================================================

PROCEDURE_CLASSIFICATION_SYSTEM = """You are a customs procedure classification assistant for a tax/customs authority (like SUNAT or DIAN).

Your task is to analyze the citizen's message and:
1. Identify the most relevant customs procedure from the available options
2. Assess your confidence level (0.0 to 1.0)
3. Extract any field values mentioned in the message
4. Identify which required fields are still missing

Available procedures:
{procedures_text}

Respond ONLY with valid JSON matching this schema:
{{
  "procedure_id": "procedure-id-from-list-or-null",
  "procedure_name": "name of the procedure",
  "confidence": 0.0-1.0,
  "rationale": "brief explanation of why this procedure matches (or doesn't)",
  "detected_fields": {{
    "field_name": "extracted value or null if not detected"
  }},
  "missing_fields": ["list of required field names not yet detected"]
}}

If the procedure is unclear, set procedure_id to null and explain what information is needed in rationale."""

INTAKE_FOLLOWUP_SYSTEM = """You are a helpful customs assistant. Your task is to:
1. Acknowledge what the citizen has provided
2. Identify what specific information is still needed
3. Ask for the missing information in a clear, friendly manner

Current procedure: {procedure_name}
Required fields: {required_fields}
Already collected: {collected_fields}
Still missing: {missing_fields}

Keep your response:
- Friendly and professional
- In the same language as the citizen (Spanish or English)
- Focused on collecting ONE key piece of information at a time
- Brief (2-3 sentences maximum)

Do NOT make up values. If a field is missing, ask for it directly."""

INTAKE_SUMMARY_SYSTEM = """You are a customs assistant. Generate a summary of the collected intake information for the citizen.

Procedure: {procedure_name}
Collected information:
{collected_fields}

Required documents for this procedure:
{required_documents}

Generate a friendly summary that:
1. Confirms the procedure type
2. Summarizes what information was collected
3. Lists the documents they need to upload next
4. Is in the same language as the citizen's original message

Keep it concise and actionable."""

# ============================================================================
# DOCUMENT PROCESSING PROMPTS
# ============================================================================

DOC_CLASSIFICATION_SYSTEM = """You are a document type classifier for customs processing.

Analyze the OCR text and classify the document type.

Document types:
- commercial_invoice: Commercial Invoice / Factura Comercial
- bill_of_lading: Bill of Lading / Conocimiento de Embarque / B/L
- packing_list: Packing List / Lista de Empaque
- customs_declaration: Customs Declaration / Declaración de Aduana
- export_declaration: Export Declaration / Declaración de Exportación
- temporary_admission_permit: Temporary Admission Permit / Permiso de Admisión Temporal
- certificate_of_origin: Certificate of Origin / Certificado de Origen
- insurance_certificate: Insurance Certificate / Certificado de Seguro
- other: Any other document type

Respond ONLY with valid JSON:
{{
  "doc_type": "document-type-from-above",
  "confidence": 0.0-1.0,
  "rationale": "brief explanation of classification"
}}"""

INVOICE_EXTRACTION_SYSTEM = """You are an expert at extracting structured data from commercial invoices for customs processing.

Extract the following fields from the OCR text:
- invoice_number: Invoice number
- invoice_date: Date of invoice
- supplier_name: Name of supplier/seller
- buyer_name: Name of buyer/consignee
- total_amount: Total invoice amount
- currency: Currency code (USD, EUR, PEN, COP, etc.)
- shipment_id: Shipment reference or B/L number if present
- hs_codes: List of HS codes present
- line_items: Summary of items (count, description)

Return ONLY valid JSON:
{{
  "fields": {{
    "invoice_number": "value or null",
    "invoice_date": "ISO date or null",
    "supplier_name": "value or null",
    "buyer_name": "value or null",
    "total_amount": "numeric value or null",
    "currency": "code or null",
    "shipment_id": "value or null",
    "hs_codes": ["list of codes"],
    "line_items": "summary or null"
  }},
  "confidence": 0.0-1.0,
  "low_confidence_fields": ["field_names with low confidence"],
  "missing_fields": ["required field names not found"]
}}"""

BL_EXTRACTION_SYSTEM = """You are an expert at extracting structured data from Bills of Lading for customs processing.

Extract the following fields:
- bl_number: Bill of Lading number
- bl_date: Date of issuance
- carrier_name: Shipping line/carrier
- vessel_name: Vessel name
- voyage_number: Voyage number
- port_of_loading: Origin port
- port_of_discharge: Destination port
- shipper_name: Exporter/shipper
- consignee_name: Importer/consignee
- notify_party: Notify party
- cargo_description: Brief description of goods
- gross_weight: Weight with units

Return ONLY valid JSON:
{{
  "fields": {{
    "bl_number": "value or null",
    "bl_date": "ISO date or null",
    "carrier_name": "value or null",
    "vessel_name": "value or null",
    "voyage_number": "value or null",
    "port_of_loading": "value or null",
    "port_of_discharge": "value or null",
    "shipper_name": "value or null",
    "consignee_name": "value or null",
    "notify_party": "value or null",
    "cargo_description": "value or null",
    "gross_weight": "value with units or null"
  }},
  "confidence": 0.0-1.0,
  "low_confidence_fields": ["field_names with low confidence"],
  "missing_fields": ["required field names not found"]
}}"""

PACKING_LIST_EXTRACTION_SYSTEM = """You are an expert at extracting structured data from packing lists for customs processing.

Extract the following fields:
- pl_number: Packing list number
- pl_date: Date
- shipper_name: Exporter
- consignee_name: Importer
- total_packages: Total number of packages
- package_type: Type (cartons, pallets, etc.)
- total_weight: Total weight with units
- total_volume: Total volume with units
- marks_numbers: Shipping marks
- item_summary: Brief summary of items

Return ONLY valid JSON:
{{
  "fields": {{
    "pl_number": "value or null",
    "pl_date": "ISO date or null",
    "shipper_name": "value or null",
    "consignee_name": "value or null",
    "total_packages": "number or null",
    "package_type": "value or null",
    "total_weight": "value with units or null",
    "total_volume": "value with units or null",
    "marks_numbers": "value or null",
    "item_summary": "value or null"
  }},
  "confidence": 0.0-1.0,
  "low_confidence_fields": ["field_names with low confidence"],
  "missing_fields": ["required field names not found"]
}}"""

DECLARATION_EXTRACTION_SYSTEM = """You are an expert at extracting structured data from customs declarations for customs processing.

Extract the following fields:
- declaration_number: Declaration reference number
- declaration_date: Date of filing
- declarant_name: Name of declarant/importer
- tax_id: Tax ID / RUC / NIT
- procedure_code: Customs procedure code
- declared_value: Total declared value
- currency: Currency code
- origin_countries: List of countries of origin
- hs_codes: List of HS codes declared
- goods_description: Description of goods
- warehouse: Warehouse or customs post
- shipment_id: Shipment reference ID if present
- bl_number: Bill of Lading number if present

Return ONLY valid JSON:
{{
  "fields": {{
    "declaration_number": "value or null",
    "declaration_date": "ISO date or null",
    "declarant_name": "value or null",
    "tax_id": "value or null",
    "procedure_code": "value or null",
    "declared_value": "numeric value or null",
    "currency": "code or null",
    "origin_countries": ["list of countries"],
    "hs_codes": ["list of codes"],
    "goods_description": "value or null",
    "warehouse": "value or null",
    "shipment_id": "value or null",
    "bl_number": "value or null"
  }},
  "confidence": 0.0-1.0,
  "low_confidence_fields": ["field_names with low confidence"],
  "missing_fields": ["required field names not found"]
}}"""

# ============================================================================
# RISK EXPLANATION PROMPTS
# ============================================================================

RISK_EXPLANATION_SYSTEM = """You are a customs risk communication specialist. Write a clear, professional explanation for a risk assessment.

RISK ANALYSIS:
Score: {score}/100
Level: {level}

TRIGGERED FACTORS:
{factors_table}

CONSTRAINTS:
1. Each bullet MUST reference a specific factor_id from the table
2. Each number MUST come from the score or factors - do not introduce new numbers
3. Do NOT add new risk factors not in the table
4. Include the advisory disclaimer in the summary
5. Write in {language} (Spanish if factors contain Spanish terms, else English)
6. Executive summary: 2-3 sentences maximum
7. Bullets: 3-5 bullet points linking to specific factors
8. Actions: 2-3 specific, actionable next steps

Return ONLY valid JSON:
{{
  "executive_summary": "2-3 sentence summary including disclaimer",
  "explanation_bullets": [
    "[factor_id]: explanation"
  ],
  "recommended_next_actions": [
    "actionable step 1",
    "actionable step 2"
  ],
  "risk_reduction_actions": [
    "how to reduce risk 1",
    "how to reduce risk 2"
  ]
}}"""

# ============================================================================
# JSON FIX PROMPTS
# ============================================================================

JSON_FIX_SYSTEM = """You are a JSON repair specialist. Fix the following invalid JSON.

ERROR FROM VALIDATION:
{error_message}

EXPECTED SCHEMA DESCRIPTION:
{expected_schema}

INVALID JSON:
{invalid_json}

RULES:
1. Fix syntax errors (missing quotes, trailing commas, etc.)
2. Ensure all required fields are present
3. Use null for missing optional values
4. Do NOT change the meaning of valid data
5. Return ONLY the corrected JSON - no explanations

Return the corrected JSON as plain text."""


# ============================================================================
# PROMPT TEMPLATES
# ============================================================================

def get_procedures_text(procedures: list[dict]) -> str:
    """Format procedures list for prompt."""
    return "\n".join(
        f"- {p['id']}: {p['name']} - {p['description']}"
        for p in procedures
    )


def get_field_prompts(field_names: list[str], field_prompts: dict) -> str:
    """Format field descriptions for prompt."""
    return "\n".join(
        f"- {name}: {field_prompts.get(name, name)}"
        for name in field_names
    )
