# SPIKE-01 Findings: goszakup.gov.kz v3 GraphQL API

> **Status:** PARTIALLY COMPLETE  
> Sections marked `[PENDING — token required]` will be populated after the human-action
> checkpoint in Task 2 is resolved (API token obtained and spike script executed).

---

## Spike Metadata

- **Date executed (partial):** 2026-05-28
- **Executor:** GSD agent (automated reachability probe) + [PENDING — name of human executor for full run]
- **Token account type:** [PENDING — supplier / buyer / other, filled after token obtained]
- **Script version (git commit):** bd69798 (spike_goszakup.py first commit)

---

## Endpoint Confirmation

- **URL tested:** https://ows.goszakup.gov.kz/v3/graphql
- **HTTP response to unauthenticated request:** `401 Unauthorized`
- **Response body (unauthenticated):**
  ```json
  {
    "name": "Unauthorized",
    "message": "Your request was made with invalid credentials.",
    "code": 0,
    "status": 401,
    "type": "yii\\web\\UnauthorizedHttpException"
  }
  ```
- **HTTP response to authenticated request:** `[PENDING — token required]`
- **Average response time (unauthenticated 401):** ~78 ms (measured via curl)
- **Average response time (authenticated):** `[PENDING — token required]`

**CONFIRMED:** The endpoint is reachable from the internet. A 401 response (not ECONNREFUSED or
timeout) confirms the host resolves, the TLS handshake succeeds, and the application processes
the request. The endpoint is operational as of 2026-05-28.

---

## Authentication Flow

- **Token type:** Bearer
- **Header:** `Authorization: Bearer {token}`
- **Token validity period:** `[PENDING — check API documentation or observe token expiry in practice]`
- **401 response body:**
  ```json
  {
    "name": "Unauthorized",
    "message": "Your request was made with invalid credentials.",
    "code": 0,
    "status": 401,
    "type": "yii\\web\\UnauthorizedHttpException"
  }
  ```
- **Token obtained from:** https://goszakup.gov.kz/ru/developer/ows_v3
  (submit a written request to АО «Центр Электронных Финансов»;
  see `docs/letter-templates/goszakup-api-token-request.md` for the template)
- **Notes on auth flow:** The error response uses Yii2 framework conventions
  (`yii\web\UnauthorizedHttpException`) — this means the backend is built on Yii2/PHP,
  not a modern GraphQL-native server. This is relevant context for understanding
  API behavior and error formats.

---

## Schema Summary

`[PENDING — token required to run introspection]`

Once `python -m spikes.spike_goszakup` is executed with a valid token, populate this section
from `spike-01-schema.json`:

- **queryType name:** [PENDING]
- **mutationType:** [PENDING — this is the critical gate for Phase 5]
  - If present: list all mutation field names here
  - If absent: state "Programmatic submission via GraphQL mutation is NOT possible.
    Phase 5 must use [browser automation / undocumented REST endpoint]."
- **Key Query fields relevant to TenderIt:**
  - TrdBuy: [PENDING — check field names]
  - TrdApp: [PENDING]
  - Supplier: [PENDING]

**Note on schema browser:** A public schema browser may be available at
https://ows.goszakup.gov.kz/help/v3/schema/ — check this URL in a browser even without a token.
If accessible, it can answer the mutation question before the token arrives.

---

## Rate Limit Findings

`[PENDING — token required to run rate limit probe]`

Once the probe completes, populate from `spike-01-rate-limit-probe.json`:

- **Requests sent before 429:** [PENDING — number or "no 429 observed in 15 requests"]
- **429 response body:** [PENDING — paste if observed]
- **Retry-After header value:** [PENDING — if present]
- **X-RateLimit-* headers:** [PENDING — list all observed]
- **Recommended safe polling rate:** [PENDING — determine from findings]

**Interim assumption (conservative):** Until measured, use 1 request per 2 seconds for
all production API calls. The rate limit probe uses 1 req/sec with automatic stop at 429.

---

## TrdBuy Sample Response

`[PENDING — token required to run TrdBuy live query]`

Once executed, paste the first item from `spike-01-trdbuy-sample.json` here.

---

## DECISIONS

### D-S01-01: Submission approach for Phase 5

- **EVIDENCE:** `[PENDING — introspection result needed to determine mutation existence]`
- **DECISION:** `[PENDING — Use GraphQL mutation / Use browser automation / Requires further investigation]`
- **IMPACT:** If `mutationType` is NOT present in the schema, Phase 5 (APPL-03) cannot
  use a direct API call to submit tender applications. The architecture must instead use
  browser automation (Playwright) or capture the undocumented submission REST endpoint
  via browser traffic analysis (SPIKE-03). This is the highest-priority finding from
  this spike.

### D-S01-02: ARQ sync interval

- **EVIDENCE:** `[PENDING — rate limit measurement needed]`
- **DECISION:** `[PENDING — Safe polling interval, must not exceed 1 req per N seconds]`
- **Interim safe default:** 1 request per 2 seconds until measured rate limit is known.

---

## Open Questions After Spike

1. **Does `mutationType` exist?** — The single most important question for Phase 5 architecture.
   Cannot be answered without a valid API token.

2. **Is schema introspection enabled?** — Some production GraphQL APIs disable introspection.
   If disabled, schema must be reconstructed from the public schema browser at
   https://ows.goszakup.gov.kz/help/v3/schema/ or from browser traffic capture.

3. **What is the token validity period?** — If tokens expire (e.g., every 24 hours or monthly),
   the application needs a token refresh mechanism or manual rotation process.

4. **Does the API support filtering in TrdBuy?** — TenderIt's Phase 3 search feature depends
   on server-side filtering (by region, category, price range). If only pagination is supported,
   client-side filtering adds data transfer overhead.

5. **Are there undocumented REST endpoints?** — The Yii2 framework signature suggests the
   API may expose REST endpoints alongside GraphQL. SPIKE-03 (browser traffic capture) will
   investigate this.

---

## Reachability Evidence (Pre-Token)

The following was confirmed without a token and is not subject to revision:

| Test | Method | Result |
|------|--------|--------|
| DNS resolution | curl to ows.goszakup.gov.kz | Success |
| TLS handshake | HTTPS POST | Success |
| Application response | 401 body (Yii2 format) | Received in ~78 ms |
| Framework inference | `yii\web\UnauthorizedHttpException` in response | Yii2/PHP backend |

This is sufficient to confirm architectural rule: the backend connects to goszakup via HTTPS
POST to `https://ows.goszakup.gov.kz/v3/graphql` with `Authorization: Bearer {token}`.
No CORS headers are needed (server-to-server call).
