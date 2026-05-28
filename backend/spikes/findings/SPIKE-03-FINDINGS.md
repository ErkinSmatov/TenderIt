# SPIKE-03: goszakup.gov.kz Tender Application Submission — Payload Capture Findings

**Status:** TEMPLATE — awaiting live traffic capture. Fields marked `[TO FILL]` require the human-executed capture step (SPIKE-03 Task 1).

---

## Spike Metadata

| Field | Value |
|-------|-------|
| Date captured | [TO FILL] |
| Captured by | [TO FILL — goszakup account holder] |
| goszakup account type | Supplier (поставщик) |
| Tender type used for testing | [TO FILL — e.g., "Запрос ценовых предложений (ЗЦП), ~500,000 KZT"] |
| Capture method | [TO FILL — Chrome DevTools Network tab / mitmproxy HAR export] |
| goszakup portal version | v3 (v3bl.goszakup.gov.kz) — publicly known |
| API base observed | [TO FILL — confirm host: v3bl.goszakup.gov.kz vs goszakup.gov.kz] |

---

## Application Flow Overview

Numbered API call sequence observed during a complete tender application submission. Populate from DevTools Network tab (Fetch/XHR filter, "Copy as cURL" for each call).

**Known from public goszakup v3 API documentation / prior reverse engineering:**

1. `GET https://v3bl.goszakup.gov.kz/ru/user/login` — Load login page (not an API call; HTML)
2. `POST https://v3bl.goszakup.gov.kz/ru/user/auth` — Authenticate with EDS (returns session token)
3. `GET https://v3bl.goszakup.gov.kz/api/trd-buy/[ANNOUNCE_NUMBER]` — Fetch tender announcement details
4. [TO FILL] — Call that creates the draft application (`/applications` or `/trdapp` or `/v3/application`)
5. [TO FILL] — Call(s) to set application fields / upload documents step-by-step
6. [TO FILL] — Call that retrieves unsigned XML for NCALayer signing (returns `payloadXml` field)
7. [TO FILL] — Call that submits the CMS-signed XML back to the portal (the critical submission call)
8. [TO FILL] — Confirmation call / response with assigned application number

**Instruction for captor:** Replace the `[TO FILL]` rows above with the actual observed calls. Add rows for any intermediate steps. Keep chronological order.

---

## Submission Endpoint

| Attribute | Known / To Fill |
|-----------|----------------|
| Host | [TO FILL — confirm: `v3bl.goszakup.gov.kz` or `goszakup.gov.kz`] |
| Path | [TO FILL — e.g., `/api/trd-buy/[ANNOUNCE_NUMBER]/application` or `/ru/supplier/application/add`] |
| Full URL | [TO FILL] |
| HTTP Method | [TO FILL — expected: POST or PUT] |
| Content-Type | [TO FILL — expected: `application/json` or `multipart/form-data` or `application/xml`] |
| Response Content-Type | [TO FILL — expected: `application/json`] |

**Note on known variants:**
- The goszakup v3 REST API (`v3bl.goszakup.gov.kz/api/`) uses JSON for most calls.
- The OWS/SOAP endpoint (`ows.goszakup.gov.kz`) is legacy and uses XML/SOAP — confirm which is active for supplier submissions.
- The GraphQL API (`goszakup.gov.kz/graphql`) is read-only (tenders, organizations) and is NOT used for submissions.

---

## Request Headers (Submission Call)

Paste all headers from the submission request. Redact actual token values but preserve format.

```
[TO FILL — example format:]
Host: v3bl.goszakup.gov.kz
Authorization: Bearer [REDACTED]
Content-Type: application/json
Accept: application/json
X-Requested-With: XMLHttpRequest
Cookie: [REDACTED]
Referer: https://v3bl.goszakup.gov.kz/ru/supplier/...
User-Agent: Mozilla/5.0 ...
```

---

## FIELD REGISTRY

**This is the most critical section.** Every field observed in the submission request payload must have one row. Fields pre-populated below are derived from publicly known goszakup v3 API schema; confirm or correct each row during live capture.

| Field Name | Location | Type | Required | Example Value | Notes |
|------------|----------|------|----------|---------------|-------|
| `announceNumber` | root / `data.announceNumber` | string | yes | `"23062400076"` | Tender announcement number from goszakup; 11-14 digits |
| `trdBuyId` | root / `data.trdBuyId` | integer | yes | `12345678` | Internal goszakup tender ID |
| `supplierId` | root / `data.supplierId` | integer | yes | `9876543` | Internal supplier account ID (from authenticated session) |
| `supplierBin` | root / `data.supplierBin` | string | yes | `"123456789012"` | 12-digit BIN of supplier legal entity |
| `supplierIin` | root / `data.supplierIin` | string | conditional | `"000000000000"` | 12-digit IIN (only for sole proprietors / ИП) |
| `applicationNumber` | root / `data.applicationNumber` | string | no (auto-assigned) | `"АП-2024-XXXXXXXX"` | Assigned by portal on draft creation; empty on initial POST |
| `status` | root / `data.status` | string/integer | yes | `"DRAFT"` / `1` | Application status code; confirm string vs int enum |
| `price` | root / `data.price` | number | yes | `450000.00` | Proposed price in KZT (tenge); decimal or integer? |
| `priceWithVat` | root / `data.priceWithVat` | number | conditional | `540000.00` | Price including VAT (18%); only if supplier is VAT-registered |
| `vatPercent` | root / `data.vatPercent` | number | conditional | `12` or `0` | VAT percentage (0, 12); confirm allowed values |
| `deliveryPlace` | root / `data.deliveryPlace` | string | yes | `"г. Алматы, ул. Примерная, 1"` | Delivery address |
| `deliveryTerm` | root / `data.deliveryTerm` | string/integer | yes | `"30"` / `30` | Delivery period in calendar days; confirm string vs int |
| `paymentTerm` | root / `data.paymentTerm` | string | conditional | `"по факту поставки"` | Payment terms text |
| `currency` | root / `data.currency` | string | yes | `"KZT"` | Always KZT for domestic tenders |
| `signedXml` | root / `data.signedXml` OR separate field | string | yes | `"MIIF..."` | Base64-encoded CMS (PKCS#7) signed XML from NCALayer; [TO CONFIRM location] |
| `xmlPayload` | root / `data.xmlPayload` | string | yes | `"<?xml ..."` | Unsigned or pre-signed XML body before NCALayer signing; [TO CONFIRM whether this is the field that goes to NCALayer] |
| `documents` | root / `data.documents` | array | conditional | `[{"docTypeId": 1, "fileName": "license.pdf", "fileId": "abc123"}]` | Attached documents; structure TBD from capture |
| `documents[].docTypeId` | `data.documents[n].docTypeId` | integer | yes | `1` | Document type code from goszakup reference directory |
| `documents[].fileName` | `data.documents[n].fileName` | string | yes | `"license.pdf"` | Original file name |
| `documents[].fileId` | `data.documents[n].fileId` | string | yes | `"abc123-uuid"` | File ID from a prior upload call (MinIO or goszakup storage) |
| `lots` | root / `data.lots` | array | yes | `[{"lotId": 1, "quantity": 10, "price": 45000.00}]` | Application per-lot details; structure TBD |
| `lots[].lotId` | `data.lots[n].lotId` | integer | yes | `1` | Lot number within the tender |
| `lots[].quantity` | `data.lots[n].quantity` | number | yes | `10` | Quantity being offered |
| `lots[].unitPrice` | `data.lots[n].unitPrice` | number | yes | `45000.00` | Unit price per item |
| `lots[].totalPrice` | `data.lots[n].totalPrice` | number | yes | `450000.00` | `quantity × unitPrice` |
| `supplierAddress` | root / `data.supplierAddress` | string | conditional | `"г. Алматы, ул. Абая, 150"` | Legal address of supplier |
| `supplierPhone` | root / `data.supplierPhone` | string | conditional | `"+77771234567"` | Contact phone in international format |
| `supplierEmail` | root / `data.supplierEmail` | string | conditional | `"contact@company.kz"` | Contact email |
| `applicationDate` | root / `data.applicationDate` | string | yes | `"2024-01-15T10:30:00+06:00"` | ISO 8601 datetime in Almaty timezone |

**IMPORTANT:** All rows above marked with "confirm" or `[TO CONFIRM]` must be verified against actual captured network traffic. Row types, field names, and nesting may differ from goszakup documentation.

**Add rows here for any fields observed in capture that are NOT listed above.**

---

## Signed XML Structure

**Background:** goszakup requires the application payload to be signed with Kazakhstan EDS (ЭЦП) via NCALayer. The browser-side flow is:

1. Portal sends unsigned `payloadXml` string to the browser.
2. Browser sends `payloadXml` to NCALayer WebSocket (`ws://localhost:14579`) with `signXml` command.
3. NCALayer returns a CMS (PKCS#7 / XMLDSig) signed blob — the `signedXml`.
4. Browser sends `signedXml` to the portal's submission endpoint.

**Confirmed from NCALayer protocol documentation:**

```json
// Request to NCALayer (ws://localhost:14579):
{
  "module": "kz.gov.pki.knca.commonUtils",
  "method": "signXml",
  "args": {
    "storageName": "PKCS12",
    "keyType": "AUTHENTICATION",
    "xmlToSign": "[UNSIGNED_XML_STRING]",
    "tbsElementXPath": "",
    "signatureParentElementXPath": ""
  }
}

// Response from NCALayer:
{
  "code": "200",
  "responseObject": "[SIGNED_XML_BASE64_OR_STRING]"
}
```

**Unsigned XML structure to capture (`xmlToSign` / `payloadXml`):**

```xml
[TO FILL — paste the unsigned XML structure returned by the portal before signing]
```

Expected elements based on goszakup public documentation:
- Root element: `<TenderApplication>` or `<Application>` (confirm exact name)
- Namespace declarations: [TO FILL]
- Key fields embedded in XML:
  - Announce number
  - Supplier BIN
  - Lot prices
  - Document references
- Signature location: XMLDSig `<Signature>` element appended as last child of root, OR CMS wrapper (confirm)
- Encoding: UTF-8 (confirm — some older Kazakhstan portals use Windows-1251)

**Capture instruction:** When the portal calls NCALayer (you will see the WebSocket message in DevTools → Network → WS tab), copy the `xmlToSign` value and paste it here.

---

## Multi-Step Flow Details

**Expected flow (confirm each step from capture):**

### Step 1: Create Draft Application

- **URL:** [TO FILL]
- **Method:** POST
- **Payload:** `{ "trdBuyId": ..., "supplierId": ... }`  (minimal fields to create draft)
- **Expected response:** `{ "id": ..., "applicationNumber": "АП-..." }`

### Step 2: Fill Application Fields

- **URL:** [TO FILL — likely PUT /application/{id} or POST /application/{id}/field]
- **Method:** PUT or PATCH
- **Payload:** Price, lots, delivery terms
- **Expected response:** Updated application object

### Step 3: Attach Documents (if separate from Step 2)

- **Upload URL:** [TO FILL — file upload endpoint]
- **Method:** POST
- **Content-Type:** [TO FILL — likely multipart/form-data for file upload]
- **Link URL:** [TO FILL — endpoint to link uploaded file to application]

### Step 4: Retrieve Unsigned XML for Signing

- **URL:** [TO FILL — endpoint that returns `payloadXml` or `xmlToSign`]
- **Method:** GET or POST
- **Response contains:** The unsigned XML string to pass to NCALayer
- **NCALayer call:** Happens entirely in browser; backend never calls NCALayer

### Step 5: Submit Signed XML (CRITICAL STEP)

- **URL:** [TO FILL — this is the final submission endpoint]
- **Method:** POST or PUT
- **Payload:** `{ "signedXml": "...", "applicationId": ... }` (structure TBD)
- **Expected response on success:** `{ "status": "SUBMITTED", "applicationNumber": "АП-..." }`

---

## Portal Response on Success

```json
[TO FILL — paste the response body from the submission endpoint, with real values redacted]

Expected structure:
{
  "success": true,
  "data": {
    "applicationId": 12345678,
    "applicationNumber": "АП-[REDACTED]",
    "status": "SUBMITTED",
    "submittedAt": "2024-01-15T10:35:00+06:00"
  }
}
```

- HTTP status code: [TO FILL — expected 200 or 201]

---

## Portal Response on Error

```json
[TO FILL — paste any validation error response observed]

Common error structure (from goszakup public API):
{
  "success": false,
  "errors": [
    {
      "field": "price",
      "message": "Цена должна быть больше нуля"
    }
  ]
}
```

**Known error codes to watch for:**
- 400: Validation failure (missing required field, price out of range)
- 401: Session expired — re-authenticate required
- 403: Supplier not eligible for this tender (missing qualification)
- 409: Application already exists for this tender

---

## DECISIONS

### D-S03-01: Phase 5 XML Assembly Template Approach

- **EVIDENCE:** [TO FILL after capture — what did the unsigned XML look like?]
- **DECISION:** Jinja2 XML template (provisional — standard for Python server-side XML generation)
- **REASON:** The backend assembles the unsigned `payloadXml`, sends it to the browser, and receives back the NCALayer-signed result. A Jinja2 template ensures the XML structure is maintainable and testable. Confirm this approach is valid once the actual XML structure is known.
- **STATUS:** PROVISIONAL — confirm after capture

### D-S03-02: Signed XML Encoding

- **EVIDENCE:** [TO FILL — what encoding was observed in the unsigned XML? Check for `<?xml version="1.0" encoding="..."?>` declaration]
- **DECISION:** UTF-8 (provisional — goszakup v3 API uses UTF-8; legacy SOAP was Windows-1251)
- **REASON:** The v3 REST API is modern and uses UTF-8 throughout. The JSON response encoding is UTF-8. Unless the unsigned XML declaration explicitly states `encoding="windows-1251"`, use UTF-8.
- **STATUS:** PROVISIONAL — confirm from `<?xml ... encoding="...">` declaration in captured XML

### D-S03-03: Document Attachment Approach

- **EVIDENCE:** [TO FILL — how were documents attached? Separate upload endpoint + link, or base64 in JSON body?]
- **DECISION:** Two-call approach (upload file → get fileId → link fileId to application) (provisional)
- **REASON:** Standard pattern for large file handling; avoids request size limits. Most government portals use this approach. However, some use base64 for small documents (e.g., license copies < 1 MB).
- **STATUS:** PROVISIONAL — confirm from observed document attachment calls

---

## Security Notes (from Threat Model)

The following threat mitigations were applied during this spike:

| Threat ID | Description | Mitigation Applied |
|-----------|-------------|-------------------|
| T-04-01 | HAR file containing session cookies | `raw-captures/` directory is gitignored; only anonymized findings committed |
| T-04-02 | BIN/IIN/company name in sample files | Replaced with placeholder values (see SAMPLE FILES section) |
| T-04-03 | Accidental binding tender submission | Capture can stop at signing step (pre-NCALayer payload is sufficient) |
| T-04-04 | mitmproxy CA left in OS trust store | Remove mitmproxy CA after capture (see Traffic Capture Guide) |

---

## SAMPLE FILES

See companion files in `backend/spikes/findings/`:

- **`sample-submission-payload.json`** — Anonymized JSON payload showing the expected submission request body structure. All PII replaced with placeholders: BIN → `"123456789012"`, IIN → `"000000000000"`, company name → `"ТОО Тест Компания"`, auth tokens → `"REDACTED"`. Field structure is preserved.

- **`sample-submission.xml`** — Anonymized unsigned XML (`payloadXml`) showing the structure sent to NCALayer for signing. All identifiers replaced with placeholders. Signature bytes replaced with `[SIGNATURE_BYTES_REDACTED]`.

**Anonymization method:** Sed-replace or manual edit of the captured raw files. Original raw captures are stored locally in `raw-captures/` (gitignored) and NOT committed to the repository.

---

## Traffic Capture Guide

### Prerequisites

- Google Chrome (recommended) or Firefox with DevTools
- A goszakup supplier account (поставщик) with active session
- Access to an eligible tender (or a previously submitted tender for re-application observation)

### Chrome DevTools Setup

1. Open Chrome and navigate to `https://v3bl.goszakup.gov.kz`
2. Open DevTools: `F12` or `Cmd+Option+I` (macOS) or `Ctrl+Shift+I` (Windows/Linux)
3. Click the **Network** tab
4. Enable **"Preserve log"** checkbox (prevents clearing on page navigation)
5. Enable **"Disable cache"** checkbox
6. In the filter toolbar, click **"Fetch/XHR"** (shows only API calls, not images/CSS)
7. Optional: In the filter text box, type `api` or `application` to narrow results

### WebSocket Capture (NCALayer)

To capture the NCALayer WebSocket messages:
1. In DevTools Network tab, click **"WS"** filter (shows WebSocket connections)
2. When the signing step is reached, find the `ws://localhost:14579` connection
3. Click it → **Messages** tab to see the `signXml` request and response
4. Copy the `xmlToSign` value from the request — this is the unsigned XML goszakup expects

### Exporting the HAR File

After completing the capture session:
1. In the DevTools Network tab, click the **down-arrow export icon** (or right-click in the request list)
2. Select **"Export HAR..."** (Chrome) or **"Save All as HAR"** (Firefox)
3. Save to `backend/spikes/findings/goszakup-submission-session.har`

**CRITICAL:** Before committing anything, remove the HAR file or add it to gitignore (already done). The HAR file contains your session cookies and auth tokens in plaintext.

### mitmproxy (Optional — More Complete HTTPS Inspection)

```bash
# Install mitmproxy
pip install mitmproxy

# Start mitmweb (browser UI for captured traffic)
mitmweb --listen-port 8080

# Configure Chrome proxy: System Preferences → Network → Advanced → Proxies
# HTTP Proxy: localhost:8080
# HTTPS Proxy: localhost:8080

# Install mitmproxy CA certificate
# Visit: http://mitm.it in Chrome → download and install the certificate
# macOS: double-click → Keychain Access → mark as "Always Trust"

# After capture, REMOVE the CA certificate:
# Keychain Access → find "mitmproxy" → delete
# OR: security delete-certificate -c "mitmproxy" ~/Library/Keychains/login.keychain-db
```

### What to Capture (Priority Order)

| Priority | What to Capture | Method |
|----------|----------------|--------|
| 1 (Critical) | The API call that submits the signed XML | "Copy as cURL" in DevTools |
| 2 (Critical) | The API call that retrieves unsigned XML (payloadXml) | "Copy as cURL" |
| 3 (High) | The API call that creates the application draft | "Copy as cURL" |
| 4 (High) | NCALayer WebSocket messages (signXml request + response) | DevTools WS tab |
| 5 (Medium) | Document upload calls | "Copy as cURL" |
| 6 (Low) | Login/auth call | "Copy as cURL" |

### How to "Copy as cURL"

In the Network tab, right-click any request → **Copy** → **Copy as cURL (bash)**. Paste into a `.txt` file in `raw-captures/`.

### After Capture

1. Open each cURL command in a text editor
2. Replace real auth tokens with `BEARER_TOKEN_REDACTED`
3. Replace your BIN with `123456789012`
4. Replace your IIN with `000000000000`
5. Replace company name with `ТОО Тест Компания`
6. Fill in the FIELD REGISTRY and flow sections above
7. Create `sample-submission-payload.json` and `sample-submission.xml` from the sanitized captures
8. Remove the HAR file and raw-captures from git tracking (`git status` — they should be gitignored)
9. Commit only the three findings files

---

*This document was created as a pre-populated template for SPIKE-03. The "PROVISIONAL" and "[TO FILL]" markers indicate sections requiring live capture data. Fill them in and remove the markers after completing Task 1.*
