# GAMMA-ENCRYPTION-FINDINGS.md

**Status:** CONFIRMED — CryptoSocket protocol fully reverse-engineered from local installation (2026-07-19).
Full function signature, WS URL, and message format documented below. Unblocks 05-03.

---

## Confirmed step-7 method

**Software:** CryptoSocket by НИЛ «Гамма Технологии» (TUMAR-CSP)
**WebSocket URL:** `ws://127.0.0.1:6126/tumarcsp`
**Protocol:** Custom JSON (completely different from NCALayer — no module/method/args)
**Function:** `EFCAPI.EncryptOfferPrice`

---

## CryptoSocket WebSocket Protocol

### Step 1 — Authentication (first message on every connect)

```json
{
  "TumarCSP": "SYSAPI",
  "Function": "SetAPIKey",
  "Param": {
    "apiKey": "<license-key-base64>"
  }
}
```

Response on success:
```json
{"result": "true"}
```

**IMPORTANT — License key concern:** The API key is domain-locked and must be issued by Gamma
Technologies for each domain. The goszakup portal has its own key. TenderIt needs to either:
- Obtain a EFCAPI license key from Gamma Technologies (gamma.kz/contact), or
- Proxy the call via the goszakup page (have the user perform step 7 on the portal)

For MVP development: a key for `localhost`/`127.0.0.1` is likely available for testing.

---

### Step 7 — EncryptOfferPrice Request

```json
{
  "TumarCSP": "EFCAPI",
  "Function": "EncryptOfferPrice",
  "Param": {
    "pl_sum":      5000,
    "d_sum":       1000,
    "d_messageUp":    "",
    "d_messageDown":  "",
    "id_priceoffer":  "AF89UX3146",
    "public_key":  "BgIAAEWgAAAARUMxAAIAADLYhEtwpUUB3jpQdHmV6QmULVSBM06vGXbHTqGap00EErXB8X67dEG6QdyN1fU7q1F8GwOIiK4szek3D5ZplUc"
  }
}
```

| Param | Type | Source |
|-------|------|--------|
| `pl_sum` | int | price integer part (from user input) |
| `d_sum` | int | price decimal part (from user input) |
| `d_messageUp` | string | appears to be upper bound or empty |
| `d_messageDown` | string | appears to be lower bound or empty |
| `id_priceoffer` | string | lot price-offer ID from portal (returned by step 6 `ajax_get_encr_info`) |
| `public_key` | string | base64 public key returned by step 6 `ajax_get_encr_info` |

### Step 7 — EncryptOfferPrice Response

```json
{
  "result": "true",
  "encryptData": "...",
  "encryptKey":  "...",
  "sign":        "...",
  "salt":        "..."
}
```

On error:
```json
{"result": "false", "code": "10007", "error": "Function not supported"}
```

**Field mapping to portal POST `ajax_add_encrypt`:**

| CryptoSocket response | Portal `ajax_add_encrypt` field |
|----------------------|--------------------------------|
| `encryptData` | `encryptedData` |
| `encryptKey`  | `sessionKey` |
| `salt`        | `salt` |
| `sign`        | `sign` |
| `id_priceoffer` | `info` (likely — `info` field not directly returned by CryptoSocket) |

*Note:* The exact `info` field mapping to portal's `ajax_add_encrypt` body needs one live DevTools
verification (low priority — can be confirmed during integration testing).

---

## Source of findings

All protocol details reverse-engineered from the local CryptoSocket installation at `/Library/TumarCSP/`:

| Finding | Source | Method |
|---------|--------|--------|
| WS URL `ws://127.0.0.1:6126/tumarcsp` | `/Library/TumarCSP/cryptosocket/conf/static/js/main.c58c91a6.js` | `grep wss` |
| Port 6126 confirmed running | `lsof -i -n -P` output | process: `CryptoSoc` |
| `EFCAPI.EncryptOfferPrice` function | `/Library/TumarCSP/cryptosocket/plug/libEFCAPI.dylib` | `strings` |
| Full param list + example | `libEFCAPI.dylib` embedded HTML docs | `strings` |
| Response fields `encryptData`, `encryptKey`, `sign`, `salt` | `libEFCAPI.dylib` string table | `strings` |
| SetAPIKey auth message | `libEFCAPI.dylib` embedded JS | `strings` |

---

## Architecture for 05-03

Step 7 requires a **new `useCryptoSocket()` hook** — completely separate from `useNCALayer()`:

```
ApplicationWizard:
  Step 6: GET ajax_get_encr_info  -> { public_key, id_priceoffer, ... }
  Step 7: useCryptoSocket().encryptOfferPrice(price, encrParams)
            Request: EFCAPI.EncryptOfferPrice(pl_sum, d_sum, id_priceoffer, public_key)
            Response: { encryptData, encryptKey, sign, salt }
  Step 8: POST ajax_add_encrypt   <- { encryptedData, sessionKey, salt, sign, info }
  Step 9: useNCALayer().createCMSSignatureFromBase64(encryptData)
            -> PKCS#7 blob
  Step 10: POST ajax_save_gamma_signs
```

`useCryptoSocket.ts` must:
1. Connect to `ws://127.0.0.1:6126/tumarcsp`
2. On open: send `SetAPIKey` with the TenderIt EFCAPI license key
3. On `{"result":"true"}` from SetAPIKey: set status = `connected`
4. Expose `encryptOfferPrice(params)` returning `GammaEncryptResult`
5. Handle status: `disconnected | connecting | connected | encrypting | error`

---

## Full Application Flow (final confirmed version)

| Step | Action | Who | Method | Key data |
|------|--------|-----|--------|----------|
| 1 | Create draft | Browser->Backend->Portal | POST `ajax_create_application/{tBuyId}` | Returns `applicationId` |
| 2 | Add lots | Browser->Backend->Portal | POST `ajax_add_lots/{tBuyId}/{appId}` | `selectLots[]={lotId}` |
| 3 | Confirm lots | Browser->Backend->Portal | POST `ajax_lots_next` | `next=1&confirmed=0` |
| 4 | Beneficiary info | Browser->Backend->Portal | POST `ajax_save_info` | BIN, citizenship, etc. |
| 5 | Skip docs step | Browser->Backend->Portal | POST `ajax_docs_next` | `next=1` |
| 6 | Get encryption params | Browser->Backend->Portal | POST `ajax_get_encr_info` | `lpId&version={csVersion}&csrf` -> `{public_key, id_priceoffer, ...}` |
| **7** | **Gamma encrypt price** | **Browser->CryptoSocket (6126)** | **`EFCAPI.EncryptOfferPrice`** | **Input: price + params from step 6; Output: {encryptData, encryptKey, sign, salt}** |
| 8 | Save encrypted price | Browser->Backend->Portal | POST `ajax_add_encrypt` | `encryptedData, sessionKey, salt, sign, info` |
| **9** | **GOST sign encrypted data** | **Browser->NCALayer (13579)** | **`createCMSSignatureFromBase64`** | **Output: PKCS#7 blob** |
| 10 | Save GOST signature | Browser->Backend->Portal | POST `ajax_save_gamma_signs` | `xmlData[lpId]=encryptData&signData[lpId]=pkcs7Blob` |
| 11 | Confirm price step | Browser->Backend->Portal | POST `ajax_priceoffers_next` | `offer[appLotId][lpId][price]=encryptData` |
| 12 | Final submit (ARQ) | ARQ Worker->Portal | POST `ajax_public_application` | Session cookie + CSRF + `public_app=Y` |

**Step 7: CryptoSocket WS port 6126. Step 9: NCALayer WS port 13579. Steps 1-6, 8, 10-11: TenderIt backend proxy. Step 12: ARQ-only.**

---

## Open items for 05-03

| Item | Priority | Notes |
|------|----------|-------|
| Confirm `info` field mapping in `ajax_add_encrypt` | LOW | Capture once during integration test |
| Confirm exact `pl_sum`/`d_sum` encoding (tenge, kopeck split?) | MEDIUM | Test with a real price |
| Obtain EFCAPI license key from Gamma Technologies for TenderIt domain | HIGH - BUSINESS | Without this key, `SetAPIKey` will fail in production. For MVP/dev: key for 127.0.0.1 may work locally |
| Confirm `version` param in step 6 is CryptoSocket version (not NCALayer) | LOW | Check `BaseAPI.GetVersion` call before step 6 |

---

## Analysis Log

```
2026-07-09 — Automated JS scraping blocked (goszakup requires PHPSESSID)
2026-07-17 — User confirmed: step 7 uses CryptoSocket (TUMAR-CSP), NOT NCALayer
2026-07-19 — lsof: CryptoSocket running on ports 6126-6130
2026-07-19 — strings on libEFCAPI.dylib: full protocol reverse-engineered
             WS: ws://127.0.0.1:6126/tumarcsp
             Function: EFCAPI.EncryptOfferPrice
             All params and response fields confirmed
```
