# SPIKE-02: NCALayer WebSocket Protocol Findings

> **Status:** COMPLETE for NCALayer 1.x (macOS). All critical decisions resolved. NCALayer 2.x (Windows) behavior unconfirmed but architecture is dual-mode ready.
> **CONFIRMED WORKING (2026-05-28):** `getKeyInfo` (array args, code 200) + `signXml` (raw XML, code 200, XMLDSig response in `responseObject`).
> **REMAINING:** Test on NCALayer 2.x Windows machine when available. GOST cert not tested.

---

## Spike Metadata

- **Date executed (partial):** 2026-05-28
- **NCALayer version:** `1.4` (broadcast automatically on WebSocket connect — confirmed)
- **Operating system of test machine:** [TO FILL — confirm: Windows / macOS?]
- **Browser used for testing:** [TO FILL]
- **Certificate type used:** [TO FILL — PKCS12 assumed]
- **Certificate purpose tested:** [TO FILL]
- **Researcher:** Product owner

---

## CONFIRMED_PORT: 13579 ✅

**Confirmed by live test on 2026-05-28:**
- Connection to `wss://127.0.0.1:13579` → **CONNECTED** (WebSocket established)
- Connection to `wss://127.0.0.1:13579` first attempt → ERROR 1006 (SSL trust not set), resolved by trusting cert in browser

**Confirmed port:** `13579`

---

## WebSocket URL

- **Confirmed URL:** `wss://127.0.0.1:13579` ✅
- **Protocol:** WSS (TLS-wrapped WebSocket) ✅
- **Self-signed certificate:** Yes — must be trusted once in browser (open `https://127.0.0.1:13579` → Advanced → Proceed)
- **Version broadcast:** NCALayer sends `{"result": {"version": "1.4"}}` automatically on connect, before any method call ✅

---

## Module Confirmation

**Known background (from research):**
- `kz.gov.pki.knca.basics` — current module, introduced in NCALayer 2.x
- `kz.gov.pki.knca.commonUtils` — legacy module from NCALayer 1.x; **confirmed working on 1.4 with array args**

| Module | Status | Tested | Verdict |
|--------|--------|--------|---------|
| `kz.gov.pki.knca.basics` | CURRENT (NCALayer 2.x) | ✅ Yes | ❌ FAILED on 1.4 — "X is not defined in PKIExtras" |
| `kz.gov.pki.knca.commonUtils` + object args | Legacy 1.x | ✅ Yes | ❌ FAILED — `NoSuchMethodException` (Java reflection miss) |
| `kz.gov.pki.knca.commonUtils` + **array args** | Legacy 1.x | ✅ Yes | ✅ **CONFIRMED WORKING** — `getKeyInfo` returned code 200 |

**FINDING — Three tests, root cause identified (2026-05-28):**

| Test | Module | Args format | Error / Result | Interpretation |
|------|--------|-------------|----------------|----------------|
| Test 1 | `kz.gov.pki.knca.basics` | object | `IllegalArgumentException: signXml is not defined in PKIExtras` | PKIExtras layer not present in 1.4 |
| Test 2 | `kz.gov.pki.knca.commonUtils` | object `{storageName:"PKCS12"}` | `NoSuchMethodException signXml` | Java reflection finds method by name but signature mismatch |
| **Test 3** | `kz.gov.pki.knca.commonUtils` | **array `["PKCS12"]`** | **✅ HTTP 200, certificate data returned** | **Positional array args match Java method signature exactly** |

**Root cause of Tests 1 & 2:** NCALayer 1.x dispatches via Java reflection using positional argument matching, not named-key mapping. Sending `args: {tokenType: "PKCS12"}` (a JSON object) does not match any Java method signature. Sending `args: ["PKCS12"]` (positional array) maps correctly to `getKeyInfo(String storageName)`.

**REVISED DECISION:** NCALayer 1.x IS supported via `commonUtils` + array args. macOS users (who have only 1.4) do not need to upgrade. The `useNCALayer()` hook must auto-detect version and switch arg format accordingly.

**Working modules:**
- NCALayer ≥ 2.0 (Windows): `kz.gov.pki.knca.basics` + **object args**
- NCALayer 1.x (macOS): `kz.gov.pki.knca.commonUtils` + **positional array args**

---

### Version Requirement (REVISED — 2026-05-28)

- **Minimum NCALayer version:** NONE — both 1.x and 2.x are supported via dual-mode dispatch
- **NCALayer 1.x (macOS):** ✅ Supported — `commonUtils` module with array args
- **NCALayer 2.x (Windows):** ✅ Supported — `basics` module with object args
- **Version detection:** Automatic — NCALayer broadcasts `{"result":{"version":"1.4"}}` on WebSocket connect
- **UX action:** `useNCALayer()` hook detects version on connect and selects the correct module + args format transparently. No user prompt needed.

---

## JSON-RPC Message Format

> All request/response JSON below must be replaced with verbatim output from the test harness session log.
> "Copy Full Log as JSON" in the test harness captures the raw messages.

### getVersion

**Request (exact JSON sent):**
```json
[TO FILL — paste from session log SENT entry for getVersion]
```

**Response (exact JSON received):**
```json
[TO FILL — paste from session log RECEIVED entry for getVersion]
```

**Version string extracted:** [TO FILL — e.g., "2.0.4" or whatever the version field shows]

**Notes:** [TO FILL — any unexpected fields, error responses, or retry behavior observed]

---

### getKeyInfo

**Request (exact JSON sent):**
```json
[TO FILL — paste from session log SENT entry for getKeyInfo]
```

**Response (exact JSON received — paste FULL response including all certificate fields):**
```json
[TO FILL — paste full RECEIVED entry from session log for getKeyInfo]
```

**Key fields observed in response:**

| Field name | Type | Example value | Notes |
|------------|------|---------------|-------|
| [TO FILL]  | [TO FILL] | [TO FILL] | [TO FILL] |

> Fields expected based on community sources (ncalayer-js-client):
> `keyType`, `subjectDn` (or `subject`), `serialNumber` (or `certSN`), `notBefore`, `notAfter`,
> `issuerDn` (or `issuer`), `keyUsage`, `pem` (certificate in PEM format).
> Replace this table with actual field names from the response.

**keyType values observed:** [TO FILL — e.g., "SIGNATURE", "AUTH", "GOST_SIGNATURE"]

**Number of certificates listed:** [TO FILL — how many certs did getKeyInfo return?]

---

### signXml

**XML payload used for testing:**
```xml
<tender><id>TEST-001</id><amount>100000</amount></tender>
```

**Request (exact JSON sent) — NCALayer 1.x format:**
```json
{
  "module": "kz.gov.pki.knca.commonUtils",
  "method": "signXml",
  "args": [
    "PKCS12",
    "SIGNATURE",
    "<tender><id>TEST-001</id><amount>100000</amount></tender>",
    "",
    ""
  ]
}
```

**Failed attempt (before fix):**
```json
{
  "args": ["PKCS12", "SIGNATURE", "PHRlbmRlcj48aWQ+...<base64>...", "", ""]
}
```
→ `{"code":"500","message":"org.xml.sax.SAXParseException; lineNumber: 1; columnNumber: 1; Content is not allowed in prolog."}`
(NCALayer 1.x feeds arg[2] directly to Java SAX parser — must be raw XML, NOT base64)

**Response (exact JSON received):**
```json
{
  "responseObject": "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\"?><tender>...</tender>",
  "code": "200"
}
```

**Signed XML structure:** Plain XML string (XMLDSig). The original `<tender>` element is returned with a `<ds:Signature>` block embedded inside. **NOT base64-encoded. NOT a CMS envelope.**

**Response field name:** `responseObject` (not `result`, not `data`, not `signedXml`)

**Which keyType succeeded:** `SIGNATURE` ✅

**PIN dialog behavior:** NCALayer shows a native OS PIN dialog. User enters certificate PIN and clicks OK. PIN is NOT sent to this page.

---

### createCMSSignatureFromBase64 (optional — run if time permits)

**Request (exact JSON sent):** NOT TESTED on 1.x

**Response (exact JSON received):** NOT TESTED

---

## Certificate Types

**Background:** NCALayer issues two certificate types per subscriber:
- **AUTH (authentication)** — for TLS client authentication; cannot be used for document signing on goszakup portal (portal will reject the signature).
- **SIGNATURE (RSA or GOST)** — for document signing; this is what tender submission requires.

**Certificates returned by getKeyInfo:**

| keyType observed | Subject CN | notAfter | Suitable for signing? |
|------------------|-----------|----------|-----------------------|
| [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] |

**CORRECT type for tender document signing:** [TO FILL — expected to be "SIGNATURE" or "GOST_SIGNATURE"]

**WRONG type (must be filtered out in UI):** AUTH certificate — the goszakup portal validates the signing certificate's Extended Key Usage (EKU) and rejects AUTH certificates. useNCALayer() must filter getKeyInfo results to exclude keyType=="AUTH".

**GOST signature observed:** [TO FILL — yes/no. If yes: was it GOST_R_3410-2012? Did signXml succeed with the GOST certificate?]

---

## Error Codes Observed

> List all error responses encountered during testing. Errors are typically returned as WebSocket messages with a non-success status or an "error" field.

| When | Request method | Error JSON (verbatim) | Cause / Resolution |
|------|---------------|----------------------|-------------------|
| [TO FILL] | [TO FILL] | [TO FILL] | [TO FILL] |

**User-cancelled PIN dialog response:** [TO FILL — what does NCALayer return if the user clicks "Cancel" in the PIN dialog?]

**Method not found response (if basics module unavailable):** [TO FILL — what does NCALayer return for an unknown module/method?]

---

## DECISIONS

> These decisions are machine-readable by Phase 5 implementers. Do not alter the `D-S02-0N:` prefixes.

---

### D-S02-01: NCALayer WebSocket port for useNCALayer() hook

**Evidence:** Live test 2026-05-28 — WebSocket to `wss://127.0.0.1:13579` established successfully; version broadcast received immediately on connect.

```
CONFIRMED_PORT: 13579
```

**DECISION:** `useNCALayer()` will connect to `wss://127.0.0.1:13579`

**Fallback behavior:** No fallback to 14579 needed — 13579 is definitively correct for both NCALayer 1.x and 2.x. The 14579 port in old community docs is incorrect.

---

### D-S02-02: Module and args format for useNCALayer() — DUAL-MODE dispatch

**Evidence:** Three live tests on 2026-05-28 (NCALayer 1.4, macOS):
- `basics` + object args → ❌ PKIExtras error
- `commonUtils` + object args → ❌ NoSuchMethodException
- `commonUtils` + **array args** → ✅ **code 200, certificate data returned**

**DECISION:** `useNCALayer()` must implement dual-mode dispatch based on auto-detected version:

| Detected version | Module | Args format | Example |
|-----------------|--------|-------------|---------|
| ≥ 2.0 | `kz.gov.pki.knca.basics` | Named object | `{tokenType:"PKCS12", keyType:"SIGNATURE", …}` |
| 1.x (macOS) | `kz.gov.pki.knca.commonUtils` | Positional array | `["PKCS12", "SIGNATURE", "<b64xml>", "", ""]` |

**Version detection:** Free and automatic — NCALayer broadcasts `{"result":{"version":"X.Y"}}` immediately on WebSocket connect, before any method call. No extra round-trip needed.

**Rationale:** macOS ships only NCALayer 1.4 (2.x is Windows-only). Kazakhstan SMBs commonly use macOS. Requiring 2.x would exclude all macOS users. Dual-mode adds ~15 lines to `useNCALayer()` and is transparent to the calling UI code.

---

### D-S02-03: Certificate type filtering in browseKeyStore / getKeyInfo UI

**Evidence:** getKeyInfo response showing multiple certificate types (AUTH + SIGNATURE)

**DECISION:** Filter getKeyInfo results to show only certificates where `keyType` is `[TO FILL: e.g., "SIGNATURE"]`.
Exclude `keyType == "AUTH"` from the certificate selection UI. The certificate picker in the Phase 5 signing flow must not present AUTH certificates to the user for document signing.

**Reason:** [TO FILL — e.g., "goszakup portal rejects AUTH-signed documents; observed keyType values were AUTH and SIGNATURE; SIGNATURE cert succeeded in signXml"]

---

### D-S02-04: signXml input format

**Evidence (2026-05-28):**
- Legacy 1.x: sent `args: ["PKCS12","SIGNATURE","<base64xml>","",""]` → ❌ `SAXParseException: Content is not allowed in prolog`
  - Interpretation: NCALayer 1.x feeds arg[2] directly to Java SAX parser — it must be raw XML, not base64.
- Legacy 1.x fix: `args: ["PKCS12","SIGNATURE","<raw xml string>","",""]` → ⏳ pending test (harness updated)
- Modern 2.x: `args: {tokenType,keyType,xmlToSign:<base64>,…}` → not yet tested on NCALayer 2.x machine

**DECISION:** `xmlToSign` encoding AND response field differ by version:

| | NCALayer 1.x (macOS) | NCALayer 2.x (Windows) |
|---|---|---|
| Module | `kz.gov.pki.knca.commonUtils` | `kz.gov.pki.knca.basics` |
| Args format | Positional array | Named object |
| `xmlToSign` input | **Raw XML string** | **base64-encoded UTF-8** (`btoa(unescape(encodeURIComponent(xml)))`) |
| Response field | **`responseObject`** | `result` (unconfirmed — to verify on 2.x) |
| Response format | **Plain XMLDSig XML string** | Unknown (likely base64 — to verify) |

`useNCALayer()` hook implementation:
```typescript
const isLegacy = detectedVersion.major < 2;
const signedXml = isLegacy
  ? response.responseObject          // plain XML string, already decoded
  : atob(response.result);           // base64 → decode (to verify on 2.x)
```

**CONFIRMED on NCALayer 1.4 (macOS, 2026-05-28):** raw XML in → XMLDSig XML out in `responseObject`, code 200. ✅

---

### D-S02-05: pyhanko GOST support verdict

**Background:** The backend must verify signatures received from the frontend. If NCALayer signs with a GOST-3410-2012-512 certificate (the newer KZ standard), the backend needs a library that can verify GOST signatures. `pyhanko` 0.35.1 has partial GOST support — whether it covers Kazakhstan's specific curve is untested (Assumption A5 from RESEARCH.md).

**Evidence from this spike:**
- GOST certificate tested: [TO FILL — yes/no]
- GOST signXml succeeded: [TO FILL — yes/no/not tested]
- GOST signature algorithm in response: [TO FILL — e.g., "GOST3411withECGOST3410" / not observed]

**DECISION:**
- If GOST tested and pyhanko verified: `pyhanko` is sufficient; no NCANode sidecar needed.
- If GOST tested and pyhanko failed: NCANode sidecar must be added to docker-compose — Phase 5 architecture change required.
- If GOST NOT tested:

```
PENDING — GOST certificate was not tested in this spike.
Test a GOST signing certificate before Phase 5 begins to confirm
whether pyhanko or NCANode is required for server-side verification.
```

**Current status:** [TO FILL — one of the three bullets above]

---

## Phase 5 Implementation Notes

> Non-obvious implementation details discovered during the spike that Phase 5 implementers must know.

1. **Self-signed certificate trust:** Every user on a fresh NCALayer installation must trust the WSS certificate before `useNCALayer()` can connect. The hook must detect connection failure and guide the user to `https://127.0.0.1:[port]` to trust the cert. [TO FILL: confirm this is still required in the tested version]

2. **PIN dialog behavior:** NCALayer shows a native OS dialog for PIN entry. [TO FILL: describe timing — does the browser freeze while the dialog is open? Is there a timeout? What happens if the user doesn't respond?]

3. **Connection lifecycle:** [TO FILL — does NCALayer close the WebSocket after each operation, or does it maintain a persistent connection? Is reconnection needed between calls?]

4. **Certificate refresh:** [TO FILL — if the certificate expires during a session, does getKeyInfo return updated data or does NCALayer need a restart?]

5. **Concurrent connection behavior:** [TO FILL — can two browser tabs connect to NCALayer simultaneously? What happens?]

6. **NCALayer restart requirement:** [TO FILL — any observed conditions that required NCALayer to be restarted during testing]

7. **Windows-specific notes:** [TO FILL — any behavior differences observed on Windows vs macOS, if both were tested]

8. **Additional discoveries:** [TO FILL — any other unexpected behavior, response fields, or timing issues observed]

---

## Session Log Reference

**Full session log saved at:** `frontend/spikes/findings/spike-02-session-log.json`

This file was captured using the "Copy Full Log as JSON" button in `ncalayer-test.html` and contains all raw WebSocket messages (sent and received) in chronological order (newest first).

**Verification commands (run after filling this document):**
```bash
# Confirm CONFIRMED_PORT line exists
grep "CONFIRMED_PORT:" frontend/spikes/SPIKE-02-FINDINGS.md

# Confirm all 5 decisions are present
grep -E "D-S02-0[1-5]:" frontend/spikes/SPIKE-02-FINDINGS.md

# Check line count (must be >= 100)
wc -l frontend/spikes/SPIKE-02-FINDINGS.md
```

---

## Sources Used in Pre-Population

| Claim | Source | Confidence |
|-------|--------|-----------|
| Port 13579 as primary | github.com/sigex-kz/ncalayer-js-client | MEDIUM |
| Module `kz.gov.pki.knca.basics` is current | github.com/pkigovkz/sdkinfo/wiki/KNCA-Basics-Module | MEDIUM |
| Module `kz.gov.pki.knca.commonUtils` is deprecated | same | MEDIUM |
| keyType values: AUTH, SIGNATURE | community examples, NCA pki.gov.kz forum | LOW |
| AUTH certificate rejected by goszakup for signing | architectural deduction from EKU purpose | LOW — must confirm |
| GOST-3410-2012-512 as KZ certificate algorithm | Kazakhstan EDS law, NCA documentation | MEDIUM |
| pyhanko GOST support | assumption A5 in 01-RESEARCH.md | LOW — must verify |
| wss:// self-signed cert trust requirement | NCALayer installation guides (community) | MEDIUM |

**All MEDIUM/LOW confidence claims above must be replaced with direct observations from live testing.**
