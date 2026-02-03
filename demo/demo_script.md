# Demo Script: Case-to-Clearance Single Window Copilot

This script provides step-by-step instructions for demonstrating the Case-to-Clearance system.

## Prerequisites

1. Start the application:
```bash
uv run dev
```

2. Open browser to: http://localhost:8000

---

## DEMO SCENARIO 1: Happy Path (Low Risk)

**Goal:** Show smooth processing with consistent documents

### Step 1: Create New Case
1. Click "Create New Case"
2. Note the case ID in URL

### Step 2: Chat Intake
**Type exactly:** "I want to import electronics from China and need to clear customs."

**Expected Response:**
- System identifies "Import-regular" procedure
- Asks for missing information (invoice number, shipment ID, etc.)

**Type:** "Invoice is INV-2024-08912, shipment CN-2024-12345, value $50,000 USD."

**Expected Response:**
- System shows collected fields
- Asks for any remaining information
- Provides summary and document upload prompt

### Step 3: Upload Documents
Upload files from `samples/docs_happy_path/`:
1. invoice_happy.pdf (or any placeholder file)
2. bl_happy.pdf
3. packing_happy.pdf
4. declaration_happy.pdf

**Note:** If using placeholder files, the system will use fallback text from `samples/text_fallback/`.

### Step 4: Run OCR
1. Click "Run OCR" button
2. Wait for "Processing..." to complete
3. See OCR results appear

### Step 5: Extract & Validate
1. Click "Extract & Validate" button
2. Wait for processing
3. Review extracted data:
   - Invoice: $50,000 USD
   - B/L: CN-2024-12345
   - Consistent shipment IDs
   - All validations passing

### Step 6: Risk Assessment
1. Click "Compute Risk Score" button
2. **Wow Factor:** See the risk gauge show LOW (green)
3. Review risk factors (should be minimal)
4. Explanation should show: "No significant issues detected"

**Expected Score:** 5-15, Level: LOW

---

## DEMO SCENARIO 2: Fraud Indicators (High Risk)

**Goal:** Show fraud detection capabilities

### Steps 1-2: Same as Scenario 1
Create new case and start chat

### Step 3: Upload Fraudish Documents
Upload from `samples/docs_fraudish/`:
1. invoice_fraudish.pdf (shows $80,000)
2. bl_fraudish.pdf (shows CN-2024-99999)
3. declaration_fraudish.pdf (shows $50,000, CN-2024-12345)

### Step 4-5: Run OCR & Extract

### Step 6: Risk Assessment
**Wow Factor Results:**
- Risk gauge shows HIGH/CRITICAL (red/orange)
- Score: 75-95

**Key Findings Displayed:**
1. `invoice_total_declared_mismatch`: Invoice ($80,000) differs from declared ($50,000) by 60% → +25 points
2. `shipment_id_inconsistency`: Multiple shipment IDs found → +20 points
3. `missing_required_doc`: Commercial invoice missing → +15 points

**Explanation Text:**
"The system has detected significant inconsistencies between documents. The invoice value is 60% higher than the declared customs value, which may indicate under-declaration for duty avoidance. Additionally, shipment identifiers do not match across documents."

---

## DEMO SCENARIO 3: Missing Documents (Medium Risk)

**Goal:** Show missing document detection

### Steps 1-2: Same as above

### Step 3: Upload Incomplete Set
Upload from `samples/docs_missing_docs/`:
1. invoice_missing.pdf
2. packing_missing.pdf
3. declaration_missing.pdf
(No Bill of Lading!)

### Step 6: Risk Assessment
**Expected Score:** 30-45, Level: MEDIUM

**Key Finding:**
- `missing_required_doc`: Bill of Lading is required but not uploaded → +15 points

---

## TALKING POINTS FOR DEMO

### Opening
"This is Case-to-Clearance, an AI-powered copilot that helps customs authorities process clearance requests more efficiently while maintaining strong oversight."

### Key Features to Highlight

1. **Natural Language Intake**
   "Citizens can describe their situation in plain language. The system uses LLMs to understand and classify their request."

2. **Intelligent Document Processing**
   "The system uses Huawei Cloud OCR to extract text from any format - PDFs, images, scanned documents."

3. **Deterministic Validation**
   "Unlike black-box AI, our validation rules are transparent and deterministic. Every finding is evidence-based with document references."

4. **Explainable Risk Assessment**
   "The risk score is computed from specific factors. Each factor is traceable, and the explanation is grounded only in the actual data - no hallucinations."

5. **Advisory Approach**
   "Note the disclaimer - this system is advisory only. Customs officials always make the final decisions."

### Technical Highlights

1. **Hybrid Architecture**
   "We combine LLMs for understanding with deterministic rules for validation and scoring."

2. **Full Audit Trail**
   "Every action is logged with timestamps, model usage, and performance metrics for complete traceability."

3. **Guardrails**
   "We have multiple validation layers including JSON schema validation and number verification to prevent LLM hallucinations."

---

## EXPECTED DURATION

- Scenario 1 (Happy Path): 3-4 minutes
- Scenario 2 (Fraud Detection): 3-4 minutes
- Scenario 3 (Missing Docs): 2-3 minutes
- Total: ~10 minutes

---

## COMMON QUESTIONS & ANSWERS

**Q: What if OCR fails?**
A: "The system has a fallback mode that uses pre-extracted text for demo purposes."

**Q: Can the risk score be gamed?**
A: "The scoring rules are deterministic and versioned. Any change requires updating the rule version, which is captured in the audit trail."

**Q: Is this production-ready?**
A: "This is a demo showing the architectural patterns. Production deployment would require additional security, scalability, and domain-specific tuning."

**Q: How do you handle PII?**
A: "The system includes redaction capabilities for sensitive fields in the audit trail. PII fields can be configured in settings."
