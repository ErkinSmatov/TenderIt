# GAMMA-ENCRYPTION-FINDINGS.md

**Status:** PARTIAL — automated best-effort analysis complete. Human DevTools capture required to confirm step-7 NCALayer call.

**Blocks:** 05-03 (application state machine) must NOT start until the "Confirmed step-7 method" section below is filled with an actual DevTools capture.

---

## Confirmed step-7 method

**Current status:** UNCONFIRMED — requires live DevTools capture (see "Human Capture Required" below).

**Best-effort hypothesis (from SPIKE-03 HAR + architecture analysis):**

Step 7 uses NCALayer WebSocket — NOT browser WebCrypto. This is strongly implied by the `version` parameter (see "Key Evidence" section).

**Most likely NCALayer call for step 7 (hypothesis):**
```json
{
  "module": "kz.gov.pki.knca.commonUtils",
  "method": "createCmsEncryptedObject",
  "args": ["PKCS12", "<publicCertBase64>", "<priceDataBase64>"]
}
```
OR alternatively (name may differ in actual portal JS):
```json
{
  "module": "kz.gov.pki.knca.commonUtils",
  "method": "encryptData",
  "args": ["PKCS12", "<recipientCertBase64>", "<plaintextBase64>"]
}
```

**Expected response structure (from SPIKE-03 HAR step 8 body, working backwards):**
```json
{
  "encryptedData": "bR41xz...",
  "sessionKey": "...",
  "salt": "...",
  "info": "...",
  "sign": "..."
}
```

**Method 05-03 must call:**
- IF step 7 is NCALayer WS: Add a new `gammaEncrypt(lpId, encrParams)` method to `useNCALayer.ts`
- IF step 7 is browser WebCrypto: No hook change needed; implement in `useGammaEncrypt()` using `crypto.subtle` + the public key from `ajax_get_encr_info`

**PENDING CONFIRMATION** — fill in after DevTools capture.

---

## Key Evidence (from SPIKE-03)

### What is known with HIGH confidence

| Finding | Source | Confidence |
|---------|--------|-----------|
| Step 7 result fields: `{encryptedData, sessionKey, salt, info, sign}` | SPIKE-03 HAR step 8 body (POST `ajax_add_encrypt`) | HIGH |
| Step 6 sends `lpId&version={ncalayer_version}&csrf` to `ajax_get_encr_info` | SPIKE-03 HAR step 6 | HIGH |
| Step 9 is `createCMSSignatureFromBase64(encryptedData)` via NCALayer | SPIKE-03 HAR step 10 `signData` = PKCS#7 blob | HIGH |
| Step 9 result field: `responseObject` (PKCS#7 CMS blob) | SPIKE-03 signData starts with MIIP8gYJKoZIhvcNA... | HIGH |

### Critical inference: step 7 is NCALayer WS, not WebCrypto

The `ajax_get_encr_info` request includes `version={ncalayer_version}` (captured value: `version=1.0.13.2287`).

**Why this matters:** If step 7 used browser `crypto.subtle`, the NCALayer version would be irrelevant to the portal server — it would just return a fixed public key. The fact that the portal receives the NCALayer version and (presumably) adapts its encryption parameters **strongly implies** the server sends version-specific parameters for a NCALayer-driven encryption call, not a WebCrypto one.

This rules out the pure-WebCrypto hypothesis with HIGH probability.

---

## Full Application Flow (SPIKE-03 confirmed, 12 steps)

| Step | Action | Who | Method | Key data |
|------|--------|-----|--------|----------|
| 1 | Create draft | Browser→Backend→Portal | POST `ajax_create_application/{tBuyId}` | Returns `applicationId` |
| 2 | Add lots | Browser→Backend→Portal | POST `ajax_add_lots/{tBuyId}/{appId}` | `selectLots[]={lotId}` |
| 3 | Confirm lots | Browser→Backend→Portal | POST `ajax_lots_next` | `next=1&confirmed=0` |
| 4 | Beneficiary info | Browser→Backend→Portal | POST `ajax_save_info` | BIN, citizenship, etc. |
| 5 | Skip docs step | Browser→Backend→Portal | POST `ajax_docs_next` | `next=1` |
| 6 | Get encryption params | Browser→Backend→Portal | POST `ajax_get_encr_info` | `lpId&version={ncaVersion}` → returns publicKey + params |
| **7** | **Gamma encrypt price** | **Browser→NCALayer WS** | **UNKNOWN METHOD** | **Input: price + publicKey from step 6; Output: {encryptedData, sessionKey, salt, info, sign}** |
| 8 | Save encrypted price | Browser→Backend→Portal | POST `ajax_add_encrypt` | `encryptedData, sessionKey, salt, info, sign` |
| **9** | **GOST sign encrypted data** | **Browser→NCALayer WS** | **`createCMSSignatureFromBase64(encryptedData)`** | **Output: PKCS#7 blob (MIIP8g...)** |
| 10 | Save GOST signature | Browser→Backend→Portal | POST `ajax_save_gamma_signs` | `xmlData[lpId]=encryptedData&signData[lpId]=pkcs7Blob` |
| 11 | Confirm price step | Browser→Backend→Portal | POST `ajax_priceoffers_next` | `offer[appLotId][lpId][price]=encryptedData` |
| 12 | Final submit (ARQ) | ARQ Worker→Portal | POST `ajax_public_application` | Session cookie + CSRF + `public_app=Y` |

**Steps 7 and 9 use NCALayer WS. Steps 1-6, 8, 10-11 go through TenderIt backend proxy. Step 12 is ARQ-only.**

---

## Step 9: Confirmed — uses createCMSSignatureFromBase64

Step 9 NCALayer call (confirmed from SPIKE-03):

```typescript
// useNCALayer() hook call for step 9 (already implemented in useNCALayer.ts):
const signData = await ncaLayer.createCMSSignatureFromBase64(encryptedData)
```

The `signData` value from step 10 in HAR starts with `MIIP8gYJKoZIhvcNA...` which is a base64-encoded PKCS#7 / CMS SignedData structure using GOST-3410-2022 algorithm.

This call is **already implemented** in `useNCALayer.ts` → `createCMSSignatureFromBase64(base64Data)`.

---

## What 05-03 Must Call (pending step-7 confirmation)

### Step 9 — CONFIRMED

```typescript
// Implemented in useNCALayer.ts:
const pkcs7Blob = await ncaLayer.createCMSSignatureFromBase64(encryptedData)
```

### Step 7 — TWO OPTIONS (confirm via DevTools)

**Option A: New `gammaEncrypt` method in useNCALayer.ts (most likely)**
```typescript
// TO BE ADDED to useNCALayer.ts after DevTools confirms this is NCALayer WS:
interface GammaEncryptResult {
  encryptedData: string
  sessionKey: string
  salt: string
  info: string
  sign: string
}

const gammaResult = await ncaLayer.gammaEncrypt(priceBase64, publicKeyBase64)
// Returns: { encryptedData, sessionKey, salt, info, sign }
```

**Option B: Browser WebCrypto path (ruled out by version-parameter evidence, but confirm)**
```typescript
// If DevTools shows NO NCALayer WS call for step 7:
const gammaResult = await gammaEncryptWithWebCrypto(price, publicKeyFromStep6)
```

---

## Human Capture Required

The automated analysis (public JS scraping) was blocked by the goszakup portal requiring an active PHP session (PHPSESSID). The portal does not serve priceoffers.js publicly without authentication.

### DevTools Capture Instructions

1. Log into your goszakup supplier account at https://v3bl.goszakup.gov.kz
2. Start a real tender application (or use a test tender in draft state)
3. Navigate to the price (Гамма-шифрование) step
4. Open DevTools → **Network → WS** tab (WebSocket messages)
5. Trigger the price encryption action (enter a price and click "Зашифровать")
6. In the WS panel, look for a message to `wss://127.0.0.1:13579` containing:
   - A `method` field like `signXml`, `encryptData`, `createCmsEncryptedObject`, `gammaEncrypt`
   - The `module` field (`commonUtils` or `basics`)
   - The `args` structure

7. Also check **Sources** → `priceoffers.js` → search for `ws.send(` to find the exact JSON
8. Paste the captured request JSON into the "Confirmed step-7 method" section above
9. State which of the two 05-03 options applies (A: new gammaEncrypt, B: WebCrypto)

### Resume signal

After completing the DevTools capture, type:
- `"approved"` — GAMMA-ENCRYPTION-FINDINGS.md records the confirmed step-7 method
- `"blocked: no goszakup account"` — to defer with the Option A (new gammaEncrypt) assumption and proceed to 05-03

---

## Automated Analysis Attempt Log

```
2026-07-09 — Attempted to fetch v3bl.goszakup.gov.kz/ru/application/priceoffers
Status: BLOCKED — portal redirects to login without active PHPSESSID
Exit code: 0 (TCP connection succeeded) but response body empty (redirect to login)

Attempted: curl -s --max-time 10 "https://v3bl.goszakup.gov.kz/ru/application/priceoffers"
Result: Connection established to 89.218.65.137:443 but session required for HTML response

Public JS assets at /js/priceoffers.js or similar could not be located without
first authenticating to get a valid session and inspecting the page HTML for script tags.
```

**Conclusion:** Automated JS scraping not possible without a live session. Human DevTools capture is the only way to confirm the step-7 NCALayer call format.
