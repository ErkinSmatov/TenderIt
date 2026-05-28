# ADR-001: MP.kz Integration Approach — API vs Playwright

**Status:** PENDING (awaiting SPIKE-04 execution)
**Date:** 2026-05-28
**Deciders:** TenderIt development team

---

## Context

TenderIt requires tender data from MP.kz — Kazakhstan's commercial tender platform — to fulfill requirement SRCH-02 (tender aggregation from multiple sources). MP.kz has no documented public API or developer portal.

Two integration approaches are technically viable:

**Option A — Internal REST/GraphQL API:** Many modern web applications built as SPAs (Single Page Applications) use internal REST or GraphQL APIs to serve their own frontend. If MP.kz's web interface is an SPA, it likely calls internal JSON API endpoints. These endpoints — while undocumented — can be discovered via browser DevTools network traffic analysis. Consuming the same internal API would produce a fast, efficient adapter.

**Option B — Playwright browser automation:** Render MP.kz pages in a headless Chromium browser (Playwright), wait for JavaScript to execute, and extract tender data from the rendered DOM. This approach works regardless of whether an internal API exists, but is slower and more fragile.

SPIKE-04 was designed to resolve this decision by analyzing MP.kz network traffic in a real browser session.

---

## Decision

[To be filled after SPIKE-04 execution — replace "PENDING" in Status with "Accepted"]

**DECISION:** [Use Option A (internal API at [base URL]) / Use Option B (Playwright browser automation)]

---

## Evidence

- **Link:** backend/spikes/findings/SPIKE-04-FINDINGS.md
- **Summary:** [1-2 sentence summary of what was found during SPIKE-04 network traffic analysis]
- **Key finding:** [MP.kz DOES / DOES NOT expose internal REST/GraphQL API endpoints]

---

## Consequences

### Option A (Internal API) — if selected

**Positive consequences:**
- Fast sync: < 1 second per API call vs 5–15 seconds per Playwright page load
- No Playwright Docker dependency (saves ~500MB from Docker image, eliminates ARM64 compatibility concerns)
- Predictable rate limiting behavior (API calls are explicit, can be throttled precisely)
- Simpler error handling (HTTP status codes vs DOM state detection)
- Easier to maintain response parsing (JSON schema vs CSS selectors)

**Negative consequences / Risks:**
- MP.kz internal API may change without notice (no versioning SLA, no public commitment to stability)
- May require session authentication (MP.kz user session cookie), which changes the data model:
  - TenderIt would need to store MP.kz credentials per user, or use a shared service account
  - If per-user: increases auth complexity and data sensitivity (storing third-party credentials)
  - If shared service account: ToS risk (one account serving all TenderIt users)
- API endpoints are not documented: any field name change breaks the adapter
- Legal: using undocumented internal API may violate MP.kz ToS (to be reviewed in SPIKE-05 legal consultation)

**Implementation note for Phase 3:** If this option is chosen, the `MpkzAdapter` class in the backend sync worker (SRCH-02) should implement:
- Session management with cookie refresh logic
- Retry logic with exponential backoff
- Response schema validation (to detect breaking changes early)
- Alert on schema drift (unexpected fields, missing required fields)

---

### Option B (Playwright browser automation) — if selected

**Positive consequences:**
- Works even if no internal API exists or internal API requires complex authentication
- Mimics real browser behavior, making it harder for MP.kz to distinguish from a human user
- Can handle any JavaScript-rendered content (no dependency on API availability)
- CSS selectors can be more stable than internal API schema for UI-stable pages

**Negative consequences / Risks:**
- Playwright dependency adds ~500MB to the Docker image (Chromium browser binary)
- ARM64 Mac + Playwright has known Docker compatibility issues (requires `--platform linux/amd64` override in docker-compose, adds emulation overhead)
- Scraping is 5–15x slower than direct API calls:
  - Browser startup: ~2s per worker invocation (or persistent browser mode)
  - Page load + JS execution: ~3–10s per page
  - Impacts freshness of tender data (longer sync cycles)
- Fragile to UI changes: any MP.kz frontend redesign requires selector maintenance
- Higher resource consumption: Playwright workers require more RAM (Chrome process ~200MB per instance)
- Higher risk of being blocked by MP.kz (rate limiting, bot detection, CAPTCHA)
- Legal: web scraping ToS analysis still required (covered by SPIKE-05)

**Implementation note for Phase 3:** If this option is chosen, the `MpkzAdapter` class should implement:
- Persistent Playwright browser context (avoid browser restart per request)
- Selector registry (centralized CSS selectors with version tracking)
- Screenshot-on-failure logging (for debugging selector breakage)
- Stealth mode (User-Agent rotation, realistic delays, no headless detection flags)
- Graceful degradation: if MP.kz is unreachable, serve cached tender data with staleness warning

---

## Related Decisions

- **ADR-002** (docs/adr/ADR-002-automated-submission-legal-basis.md): The legal ToS question about both MP.kz API usage and Playwright scraping is covered there.
- **SPIKE-04** (backend/spikes/findings/SPIKE-04-FINDINGS.md): The technical evidence for this decision.
- **Phase 3, SRCH-02:** The implementation plan for the MP.kz sync worker depends on this ADR's decision.

---

## Pending Actions

Before this ADR can be finalized (Status: Accepted), the following must be completed:

1. **Human action required:** Execute SPIKE-04 browser traffic analysis (see plan Task 2 in 01-05-PLAN.md)
2. **Legal review:** Confirm with attorney that chosen approach (API or scraping) is permissible under MP.kz ToS
3. **Update this ADR:** Fill in DECISION field and change Status to Accepted
4. **Update backend planning:** Notify Phase 3 planner of the chosen approach so SRCH-02 task is specified correctly
