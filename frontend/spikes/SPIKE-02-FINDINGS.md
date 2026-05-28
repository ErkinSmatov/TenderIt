# SPIKE-02: NCALayer WebSocket Protocol Findings

> **Status:** AWAITING LIVE TEST  
> This document is pre-populated with all information available from public sources (research confidence: MEDIUM).
> Fields marked `[TO FILL]` require live NCALayer testing using the test harness at `frontend/spikes/ncalayer-test.html`.
> After testing, save the session log as `frontend/spikes/findings/spike-02-session-log.json` and replace `[TO FILL]` entries with actual recorded values.

---

## Spike Metadata

- **Date executed:** [TO FILL — date of live test]
- **NCALayer version:** [TO FILL — from getVersion response]
- **Operating system of test machine:** [TO FILL — e.g., Windows 11, macOS 14.x]
- **Browser used for testing:** [TO FILL — e.g., Chrome 125, Firefox 127]
- **Certificate type used:** .p12 file (PKCS12) — [TO FILL: confirm or note if different]
- **Certificate purpose tested:** [TO FILL — e.g., "company signing certificate" / "test development certificate"]
- **Researcher:** [TO FILL]

---

## CONFIRMED_PORT: [TO FILL]

> **How to determine:** Run on the NCALayer machine before testing:
> - macOS/Linux: `netstat -an | grep LISTEN | grep -E "13579|14579"`
> - Windows: `netstat -ano | findstr "13579 14579"`
>
> **Known background:** Community sources (ncalayer-js-client, sigex-kz) consistently report port **13579** for NCALayer 2.x (wss://). The port 14579 appears in older documentation and may be used by legacy installations. Neither value is officially confirmed in the public NCA documentation — this spike produces the ground truth.

**Netstat output (paste verbatim):**
```
[TO FILL — paste the netstat line(s) showing the NCALayer listening port]
```

**Confirmed port:** [TO FILL — e.g., 13579]

---

## WebSocket URL

- **Confirmed URL:** `wss://127.0.0.1:[TO FILL: port]`
- **Protocol:** [TO FILL — WSS (secure WebSocket) or WS (plain)]
- **Self-signed certificate:** [TO FILL — yes/no]
- **Certificate trust procedure:**
  If WSS and self-signed: open `https://127.0.0.1:[port]` in the browser, click Advanced → Proceed.
  This must be done once per browser profile. [TO FILL: confirm this worked or describe alternative]

**Known background:** NCALayer 2.x uses WSS (TLS-wrapped WebSocket) with a self-signed certificate issued by NCA Kazakhstan. Plain WS (no TLS) may be available on a different port or disabled depending on OS/version.

---

## Module Confirmation

**Known background (from research):**
- `kz.gov.pki.knca.basics` — current module, introduced in NCALayer 2.x
- `kz.gov.pki.knca.commonUtils` — deprecated/legacy module from NCALayer 1.x; may still work as fallback

| Module | Status | Tested | Verdict |
|--------|--------|--------|---------|
| `kz.gov.pki.knca.basics` | CURRENT (recommended) | [TO FILL: yes/no] | [TO FILL: worked/failed] |
| `kz.gov.pki.knca.commonUtils` | DEPRECATED (fallback) | [TO FILL: yes/no] | [TO FILL: worked/failed/not tested] |

**Working module for all useNCALayer() calls:** [TO FILL]

**Deprecated module fallback behavior:** [TO FILL — describe what happens when commonUtils is called: does it return an error, partial response, or full response?]

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
[TO FILL — paste the XML that was in the textarea when Sign XML was clicked]
```

**Request (exact JSON sent):**
```json
[TO FILL — paste from session log SENT entry for signXml]
```

**Response (exact JSON received — include the FULL response structure; redact sensitive data only if the XML contains real company/personal data):**
```json
[TO FILL — paste full RECEIVED entry from session log for signXml]
```

**Signed XML structure:** [TO FILL — describe the outer wrapper: CMS envelope? XMLDSig? Raw signed XML? Is the output base64-encoded or plain XML text?]

**Which keyType succeeded:** [TO FILL — "SIGNATURE" or "AUTH" or other]

**PIN dialog behavior:** [TO FILL — did NCALayer show a dialog? Was it modal? On which monitor? Did it time out?]

---

### createCMSSignatureFromBase64 (optional — run if time permits)

**Request (exact JSON sent):**
```json
[TO FILL — paste from session log, or "NOT TESTED"]
```

**Response (exact JSON received):**
```json
[TO FILL — paste from session log, or "NOT TESTED"]
```

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

**Evidence:** netstat output from test machine (pasted above)

```
CONFIRMED_PORT: [TO FILL — e.g., 13579]
```

**DECISION:** `useNCALayer()` will connect to `wss://127.0.0.1:[TO FILL: port]`

**Fallback behavior:** [TO FILL — should useNCALayer() auto-try the second port on connection failure, or is one port definitively correct?]

---

### D-S02-02: Module to use for all NCALayer calls

**Evidence:** getVersion and getKeyInfo test results above

**DECISION:** Use `[TO FILL: module name]` as primary for all useNCALayer() calls.
Use `[TO FILL: other module]` as fallback only if primary returns "method not found" / "module not found".

**Rationale:** [TO FILL — e.g., "basics module responded correctly to all tested methods; commonUtils was not tested / returned deprecation warning / also worked"]

---

### D-S02-03: Certificate type filtering in browseKeyStore / getKeyInfo UI

**Evidence:** getKeyInfo response showing multiple certificate types (AUTH + SIGNATURE)

**DECISION:** Filter getKeyInfo results to show only certificates where `keyType` is `[TO FILL: e.g., "SIGNATURE"]`.
Exclude `keyType == "AUTH"` from the certificate selection UI. The certificate picker in the Phase 5 signing flow must not present AUTH certificates to the user for document signing.

**Reason:** [TO FILL — e.g., "goszakup portal rejects AUTH-signed documents; observed keyType values were AUTH and SIGNATURE; SIGNATURE cert succeeded in signXml"]

---

### D-S02-04: signXml input format

**Evidence:** signXml request/response above

**DECISION:** The `xmlToSign` argument to `signXml` must be `[TO FILL: "base64-encoded UTF-8 string" / "plain XML string" / other observed format]`.

Encoding method in useNCALayer() hook: `btoa(unescape(encodeURIComponent(xmlString)))` — [TO FILL: confirm this worked or specify the correct encoding approach]

**Response format:** The signed output is `[TO FILL: "base64-encoded signed XML" / "plain XMLDSig XML" / "CMS envelope base64"]`.
useNCALayer() must `[TO FILL: atob() decode / return as-is / parse as XML]` before sending to the backend.

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
