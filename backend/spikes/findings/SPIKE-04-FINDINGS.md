# SPIKE-04 Findings: MP.kz Integration Approach

> **Status:** TEMPLATE — awaiting human network traffic analysis (SPIKE-04 checkpoint)
>
> This document is pre-populated with the structure for the findings.
> The executor agent will fill in all [PLACEHOLDER] sections after the human completes
> the browser traffic analysis described in 01-05-PLAN.md Task 2.
>
> **When resuming after checkpoint:** Type "spike-04 executed" with your findings.
> The executor will fill in this document and finalize ADR-001.

---

## Spike Metadata

- **Date executed:** [PENDING — date human performed browser analysis]
- **MP.kz version observed:** [Check footer or page source for version string, e.g., "v2.1.3"]
- **Chrome DevTools capture date:** [PENDING]
- **Browser used:** Google Chrome (recommended) or Chromium
- **Analysis performed by:** [human reviewer]
- **Spike goal:** Determine whether MP.kz uses an internal REST or GraphQL API that TenderIt can consume directly, or whether Playwright browser automation is required for tender data extraction.

---

## Network Traffic Summary

> Fill this section after browser analysis. Group all observed Fetch/XHR requests by type.

### Tender Listing Calls

| Method | URL | Auth Required | Response Type | Notes |
|--------|-----|---------------|---------------|-------|
| [GET/POST] | [URL] | [yes/no] | [application/json / text/html] | [notes] |

### Tender Detail Calls

| Method | URL | Auth Required | Response Type | Notes |
|--------|-----|---------------|---------------|-------|
| [GET/POST] | [URL] | [yes/no] | [application/json / text/html] | [notes] |

### Search / Filter Calls

| Method | URL | Auth Required | Response Type | Notes |
|--------|-----|---------------|---------------|-------|
| [GET/POST] | [URL] | [yes/no] | [application/json / text/html] | [notes] |

### Authentication Calls

| Method | URL | Response | Notes |
|--------|-----|----------|-------|
| [GET/POST] | [URL] | [200 OK / redirect] | [notes] |

### Other Calls (CDN, analytics, etc.)

| Method | URL | Notes |
|--------|-----|-------|
| [GET] | [URL] | [e.g., Google Analytics, CDN assets — ignore for our purposes] |

---

## Internal API Status

> State clearly after analysis: one of the two options below.

**[REPLACE THIS SECTION AFTER ANALYSIS]**

---

### IF INTERNAL API EXISTS (fill this section):

**MP.kz DOES expose internal REST/GraphQL API endpoints.**

- **Base URL:** [e.g., https://mp.kz/api/v1 or https://api.mp.kz or https://mp.kz/graphql]
- **API type:** [REST / GraphQL / mixed]
- **Authentication required:** [yes / no]
  - If yes: **Auth mechanism:** [session cookie (JSESSIONID) / Bearer token / API key in header / no auth]
  - Cookie name (if cookie-based): [e.g., `mp_session`]
  - Can auth be obtained without an MP.kz account: [yes / no]

**Key endpoints discovered:**

| Purpose | Method | Endpoint | Query Params | Auth |
|---------|--------|----------|-------------|------|
| Tender listing | GET/POST | [path] | [e.g., ?page=1&limit=20&status=active] | [yes/no] |
| Tender detail | GET | [path] | [e.g., ?id=12345] | [yes/no] |
| Search | GET/POST | [path] | [e.g., ?q=keyword&category=IT] | [yes/no] |
| Pagination | [embedded in listing / cursor / page number] | — | — | — |

**Pagination mechanism:** [cursor-based / page number (?page=N) / offset (?offset=N&limit=20) / POST body]

**Rate limiting observed:** [yes — throttled after N requests / no — no evidence of rate limiting]

**Sample response structure (tender listing):**
```json
{
  // Paste first ~50 lines of actual JSON response (remove personal data if any)
}
```

**GraphQL schema (if GraphQL):**
```graphql
# Paste the introspection query result or observed query structure
```

---

### IF INTERNAL API DOES NOT EXIST (fill this section):

**MP.kz DOES NOT expose internal REST/GraphQL API endpoints.**

The tender listings page returns server-rendered HTML. Playwright browser automation is required.

**Page structure for Playwright scraping:**

- **Tender listings page URL:** [e.g., https://mp.kz/tenders or https://mp.kz/zakupki]
- **Main container CSS selector:** [e.g., `.tender-list` or `[data-testid="tender-list"]`]
- **Individual tender card CSS selector:** [e.g., `.tender-card` or `.lot-item`]

**Field selectors within each tender card:**

| Field | CSS Selector | Notes |
|-------|-------------|-------|
| Title / Name | [selector] | [e.g., `.tender-title h3`] |
| Amount (KZT) | [selector] | [e.g., `.tender-price`] |
| Deadline | [selector] | [format: DD.MM.YYYY or ISO?] |
| Region | [selector] | [e.g., `.region-badge`] |
| Tender ID / Reference | [selector] | [e.g., `[data-id]` attribute] |
| Detail page link | [selector] | [e.g., `.tender-card a[href]`] |

**Pagination:**
- **Pagination element selector:** [e.g., `.pagination-next` or `button[aria-label="Next page"]`]
- **Pagination type:** [page numbers / infinite scroll / Load More button]
- **URL changes on page navigate:** [yes — ?page=2 / no — JavaScript state only]

**JavaScript rendering requirements:**
- **Does the page require JS execution before content appears:** [yes / no]
- **Estimated wait time for content:** [e.g., `networkidle` or specific wait: `waitForSelector('.tender-card')`]
- **Infinite scroll detected:** [yes — scroll event triggers new content / no]

---

## Authentication Analysis

- **Can tender listings be accessed without authentication (no login, incognito mode):** [yes / no]
- **If authentication required:**
  - Type: [MP.kz account required / goszakup token / EDS-based login / other]
  - Login URL: [URL]
  - Registration flow: [self-service / requires KZ BIN verification / instant]
  - Implication for TenderIt: [each TenderIt user needs their own MP.kz account / one shared service account / no account needed]

---

## Developer Documentation Check

Did MP.kz provide any public API documentation?

- **Footer links checked:** [yes — found: [link] / yes — nothing relevant]
- **/api-docs or /swagger path:** [checked — returns: 404 / Swagger UI / nothing]
- **/developers path:** [checked — returns: 404 / developer portal / nothing]
- **GitHub or external API docs:** [searched — found: [link] / not found]

**Conclusion:** MP.kz [does / does not] provide public API documentation.

---

## DECISION

> This line is grep-extractable. Format must be: `DECISION: API` or `DECISION: PLAYWRIGHT`

**DECISION: [API / PLAYWRIGHT]**

**Full statement:**

*[Choose one after completing the analysis above]*

**If API:**
"Use internal REST/GraphQL API at [base URL]. No Playwright dependency required for MP.kz tender data extraction. Auth: [required/not required]. Key endpoints: tender listing at [URL], tender detail at [URL]."

**If Playwright:**
"Use Playwright browser automation. No stable internal JSON API found — MP.kz renders tender data server-side as HTML. Key selectors: tender list container: [selector], tender card: [selector], pagination: [selector]. Playwright wait strategy: [waitForSelector/networkidle]."

---

## Recommended Next Steps

After this DECISION is recorded, the following tasks should proceed:

1. **Update ADR-001** (docs/adr/ADR-001-mpkz-integration-approach.md): Change Status to ACCEPTED and fill in the DECISION field. (Done by executor agent after checkpoint resumption.)

2. **Create mpkz-api-endpoints.json** with endpoint inventory or Playwright selectors. (Done by executor agent.)

3. **Phase 3 planning:** The SRCH-02 task must specify the correct adapter implementation approach based on this decision. Notify the Phase 3 planner.

4. **If API selected:** Test rate limiting behavior during Phase 3 spike. Build the `MpkzApiAdapter` class.

5. **If Playwright selected:** Test Playwright on ARM64 Mac dev environment. Confirm Docker image weight is acceptable. Build the `MpkzPlaywrightAdapter` class.
