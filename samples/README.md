# Sample Documents for Demo

This directory contains sample documents organized into three scenarios:

## docs_happy_path (Low Risk)
A complete, consistent set of documents for a standard import.

**Expected Result:** Score 5-15, Level LOW

**Documents:**
- Commercial Invoice: $50,000 USD
- Bill of Lading: Shipment ID CN-2024-12345
- Packing List: 100 cartons, electronics
- Customs Declaration: Declared value $50,000 USD

**Consistencies:**
- All shipment IDs match
- Invoice total equals declared value
- Date sequence is logical
- All required documents present

## docs_fraudish (High Risk)
Documents with inconsistencies that may indicate fraud.

**Expected Result:** Score 75-95, Level HIGH/CRITICAL

**Issues:**
- Invoice total: $80,000 USD
- Declaration: $50,000 USD (60% under-declaration)
- Shipment ID mismatch: BL says CN-2024-99999, Declaration says CN-2024-12345
- Missing: Commercial Invoice (different one provided)

**Expected Findings:**
- `invoice_total_declared_mismatch`: +25 points
- `shipment_id_inconsistency`: +20 points
- `missing_required_doc`: +15 points

## docs_missing_docs (Medium Risk)
A complete set missing one required document.

**Expected Result:** Score 30-45, Level MEDIUM

**Issues:**
- Missing: Bill of Lading
- Values consistent across docs

**Expected Findings:**
- `missing_required_doc`: +15 points

## text_fallback
Pre-extracted text files used when OCR is not configured.
These files contain the text content that would be extracted from documents.
