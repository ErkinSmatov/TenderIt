# Project Research Summary

**Project:** TenderIt — Kazakhstan E-Procurement Tender Aggregator
**Domain:** B2B SaaS — tender aggregation + EDS signing + automated goszakup submission
**Researched:** 2026-05-25
**Confidence:** MEDIUM (core stack HIGH; Kazakhstan-specific integrations MEDIUM; legal items LOW)

---

## Executive Summary

TenderIt is a Kazakhstan-specific B2B SaaS that solves a genuine whitespace problem: all existing competitors (zakup.smart.kz, tenderbot.kz, tender.kz) stop at discovery and notification; none automate document assembly or EDS signing. The target user is the SMB director who handles procurement personally, operates under deadline pressure, and loses tenders primarily due to timing failures and document errors — not lack of opportunity. The recommended architecture is a Next.js 14 / FastAPI / PostgreSQL stack with an ARQ async worker layer for tender sync and notification dispatch. All crypto operations happen in the browser via NCALayer WebSocket (wss://127.0.0.1:14579) — the backend assembles payloads and receives signed XML, but never touches private keys or the NCALayer process directly.

The highest technical risk is the goszakup submission pipeline: the GraphQL API schema is undocumented in detail, the exact payload required for programmatic application submission is unknown without intercepting real browser traffic, and Kazakhstan's GOST signature requirements per tender type are inconsistently documented. These are not theoretical concerns — they are the specific items that cause CIS government portal integrations to fail after months of development against stale documentation. The first-priority action before any implementation is a set of mandatory spikes covering: goszakup schema introspection, NCALayer live WebSocket test, submission payload capture via browser traffic interception, MP.kz internal API discovery, and a legal review of automated submission permissibility.

The secondary risk is non-technical: Kazakhstan's personal data localization law requires that BINs, IINs, director names, and uploaded documents be stored on Kazakhstan-hosted infrastructure. Hosting user data on AWS eu-central-1 is potentially non-compliant. Infrastructure provider selection (KazCloud / Beeline KZ / Kcell) must happen before any real user data is collected. Commission a Kazakhstani attorney review before onboarding the first real company — specifically covering goszakup ToS compliance for programmatic submission and EDS authorization requirements under the Law on Electronic Documents and Digital Signatures.

---

## Key Findings

### Recommended Stack

The core stack is straightforward and high-confidence: Next.js 14 App Router for SSR on tender listings, FastAPI 0.110+ with Pydantic v2 for the API tier, PostgreSQL 16 with JSONB for portal-specific tender fields, Redis 7 as cache and ARQ broker. ARQ (not Celery) is the correct task queue choice because all sync tasks are async-native httpx operations; Celery's sync worker model creates impedance mismatch with FastAPI's async event loop. MinIO in Docker provides S3-compatible document storage with no cloud provider dependency, suitable for Kazakhstan data residency requirements.

The integration stack carries more uncertainty. The goszakup GraphQL endpoint at https://ows.goszakup.gov.kz/v3/graphql is confirmed to exist, but schema details and rate limits are community-sourced (MEDIUM confidence). MP.kz has no public API — Playwright-based scraping is the fallback, but inspecting their network traffic for internal REST endpoints should happen before committing to Playwright. NCALayer v2 uses wss://127.0.0.1:14579 with a self-signed certificate; the signXml method in the kz.gov.pki.knca.commonUtils module covers tender submission, but exact message shapes require a live test against a real NCALayer installation. For backend signature verification, pyhanko + asn1crypto handles CMS/PKCS#7; GOST-3410 support in pyhanko must be verified before committing — if it fails, NCANode (a Node.js sidecar wrapping kalkancrypt) is the fallback.

**Core technologies:**
- **Next.js 14 App Router + TypeScript 5 + TanStack Query 5:** SSR tender feed, RSC for initial loads, TanStack Query for status polling and cache invalidation
- **FastAPI 0.110 + Pydantic v2 + SQLAlchemy 2.x async + asyncpg:** async-native API tier; Pydantic v2 for all portal data parsing and request validation
- **PostgreSQL 16:** JSONB for raw portal data, tsvector GIN index for full-text tender search, UNIQUE(portal, portal_id) for upsert safety
- **Redis 7 + ARQ:** task queue for goszakup/MP.kz sync jobs (every 15-30 min) and notification dispatch (every 5 min); Redis also serves as tender listing cache
- **MinIO (S3-compatible):** document vault storage; swap to any S3 provider with zero code changes via boto3; never store .p12 key files server-side
- **NCALayer WebSocket (browser-only):** wss://127.0.0.1:14579; useNCALayer() React hook manages connection lifecycle; backend never calls NCALayer
- **python-telegram-bot 21.x + Twilio WhatsApp:** Telegram as primary notification channel (highest open rate in KZ SMB); WhatsApp via Twilio for MVP, migrate to Meta Cloud API at scale
- **httpx 0.27 + tenacity:** async HTTP client for all outbound API calls with retry/backoff; Playwright as fallback for MP.kz if no internal API found
- **pyhanko + asn1crypto:** backend CMS signature verification (GOST support to be validated in spike)
- **WeasyPrint + Jinja2:** PDF generation for tender application documents from HTML templates

### Expected Features

**Must have (table stakes) — users consider these the minimum viable product:**
- Tender search with keyword, KTRU (prefix/tree UI, not exact-code), sum range, deadline, procurement method (konkurs / ZCP), region, and status filters
- Tender detail page with all portal fields in readable format
- Saved search profiles (up to 5 per company) — prerequisite for notifications
- Telegram notifications for new tender matches — competitors all offer this; absence is disqualifying
- Company profile (BIN, name, director, address, goszakup API token)
- Document vault: upload, store, and track company documents with expiry date metadata
- EDS signing via NCALayer WebSocket — the legally required action for goszakup submission
- goszakup auto-submit via official GraphQL API — the primary value proposition
- Application status tracking: DRAFT > DOCUMENTS_READY > SIGNING > SIGNED > SUBMITTING > SUBMITTED / SUBMIT_FAILED
- User registration and JWT auth

**Should have (differentiators — competitors do not offer these):**
- Document expiry tracking with proactive warnings (government certificates have 3-month validity; licenses 1-year) — prevents the most common document-related rejection
- EDS certificate expiry warning on dashboard ("your key expires in 14 days") — prevents blocking at the worst possible moment
- NCALayer connectivity status indicator before the user starts filling a form — prevents wasted effort and support tickets
- Deadline countdown with urgency signal ("3h left") — competitors show dates, not countdowns
- Certificate selection UI (enumerate all certs from NCALayer, filter out AUTH type) — required to handle GOST vs RSA certificate type differences
- WhatsApp notifications as second channel for directors who do not use Telegram

**Defer to v2+ (validated anti-features for MVP):**
- MP.kz integration — validate goszakup first; same architecture scales; add after first 10 real submissions
- Analytics dashboard (win rates, market prices) — store raw data now; surface in v2
- One-click re-application — implement after application history UX is proven
- Smart KTRU suggestion — manual filter works for v1; add trigram matching in v1.1
- Subscription / billing system — free during validation phase
- Multi-company / team features — target user is a sole procurement person
- AI-generated technical proposals — hallucination risk in regulated submissions is disqualifying
- Mobile app — NCALayer is desktop-only; PWA meta tags are sufficient for v1

### Architecture Approach

The system separates into five runtime concerns: web tier (Next.js), API tier (FastAPI with business logic), worker tier (ARQ jobs sharing the FastAPI codebase), storage tier (PostgreSQL + MinIO), and external integrations (goszakup, MP.kz, NCALayer on localhost, Telegram, WhatsApp). The key architectural constraint is NCALayer: it runs on the user's machine and is called exclusively from browser JavaScript — a server cannot proxy this connection because it binds to localhost. This shapes the submission pipeline into a three-stage flow: (1) FastAPI assembles the application XML payload, (2) the browser sends it to NCALayer for signing and receives signed XML back, (3) the browser POSTs the signed XML to FastAPI which calls the goszakup submission mutation. Both portals implement a PortalAdapter protocol so submission and sync logic is shared infrastructure with swappable adapters.

**Major components:**
1. **Next.js UI** — renders tender feed (RSC), manages useNCALayer() WebSocket hook, displays application state machine, probes NCALayer status on page load
2. **FastAPI Auth Router** — JWT issue/refresh, user registration, password hashing
3. **FastAPI Tender Router + TenderService** — unified search/filter/pagination over local PostgreSQL; never calls portals live
4. **FastAPI Application Router + SubmissionService** — draft creation, payload XML assembly, receives signed XML, calls portal adapters; application state machine enforced server-side
5. **ARQ Sync Workers** — separate jobs per portal; goszakup every 15 min, MP.kz every 30 min; upsert into unified tenders table
6. **Notification Dispatcher** — runs every 5 min; matches new tenders against subscriptions; dedup via UNIQUE(company_id, tender_id, channel)
7. **Document Service** — versioned document storage via S3-compatible abstraction; pre-signed URLs; auto-attaches current documents to new applications
8. **goszakup Adapter / MP.kz Adapter** — portal-specific clients behind shared PortalAdapter protocol; own mapper to unified tender schema

**NCALayer flow:** When a user clicks "Confirm and Sign," the browser POSTs to /applications/{id}/prepare; FastAPI assembles the full application XML and returns it as payloadXml. The browser's useNCALayer() hook opens wss://127.0.0.1:14579, sends a signXml message, and waits while NCALayer shows the user a PIN dialog. On success NCALayer returns the signed XML; the browser POSTs it to /applications/{id}/submit. FastAPI stores the signed XML in the applications table for audit, transitions status to SUBMITTING, and calls the goszakup GraphQL submission mutation. Status transitions to SUBMITTED on portal acknowledgment with a valid application ID, or SUBMIT_FAILED with the raw portal error message retained for user display.

**Build order (hard dependency sequence):**
1. PostgreSQL schema + Alembic + FastAPI skeleton + SQLAlchemy async + config
2. Auth (register / login / JWT refresh)
3. Company profile CRUD
4. goszakup sync adapter + unified schema + ARQ worker + tender search API + Next.js feed
5. MP.kz adapter (parallel; same PortalAdapter interface)
6. Document vault (upload, versioning, pre-signed download, expiry metadata)
7. Application pipeline: draft > prepare (XML assembly) > useNCALayer() > sign > submit > status polling
8. Subscription CRUD + Telegram bot + notification dispatcher
9. WhatsApp (additive; same dispatcher)
10. Hardening: circuit breakers, durable submission queue, token encryption, rate limiting, Sentry

### Critical Pitfalls

1. **NCALayer not running at submission time** — WebSocket to wss://127.0.0.1:14579 gets ECONNREFUSED; user believes tender was submitted; deadline passes unnoticed. Prevention: probe NCALayer on every signing page load and surface a persistent green/red status indicator; disable the Sign button until NCALayer is confirmed reachable; never allow silent failure.

2. **Wrong certificate type selected** — Kazakhstan NCA issues AUTH, RSA_SIGNATURE, and GOST_SIGNATURE certificates; AUTH is for TLS only and portal signature verification will reject it. Prevention: on every NCALayer connection enumerate all available certificates via getKeyInfo/browseKeyStore, filter to signing certs only, present selection UI, store chosen alias in company profile.

3. **Submission failure with no recovery path** — network timeout or portal error occurs after the user has signed; without a retry queue the signed document is lost and re-signing may fail if the CMS timestamp has expired. Prevention: model submission as a durable ARQ job (pending > in_flight > submitted | failed); store signed_xml in PostgreSQL before first attempt; retry with exponential backoff for 30 minutes; notify user via Telegram on final failure with a manual-submission download link.

4. **Incomplete submission payload — hidden required fields** — goszakup portal auto-populates fields from the supplier profile that are not in the API documentation; programmatic submissions missing these fields fail with opaque validation errors. Prevention: intercept real browser traffic on goszakup using DevTools Network tab before building the submission module; treat the captured request body as ground truth, not the API docs.

5. **Kazakhstan data localization violation** — storing BINs, IINs, director names, and uploaded documents on non-KZ infrastructure risks non-compliance with the Law on Personal Data. Prevention: select a Kazakhstan-hosted provider (KazCloud / Beeline KZ / Kcell) for PostgreSQL and MinIO before onboarding any real users; obtain legal opinion before launch.

---

## Implications for Roadmap

Based on combined research, a 6-phase structure is recommended. Phase ordering is driven by hard build dependencies, the spike-first principle (do not build against unverified API contracts), and the validation-before-features principle (recruit beta users during Phase 3, not after Phase 6).

### Phase 1: Spikes and Foundation

**Rationale:** Five critical unknowns block all downstream phases. Building any integration without resolving them risks a rewrite. Simultaneously establish the project skeleton so spike results run against real infrastructure.

**Delivers:** Verified API contracts for goszakup and NCALayer; confirmed MP.kz approach; legal clearance for automated submission; PostgreSQL schema, Alembic, FastAPI skeleton, SQLAlchemy async, Auth, Company profile CRUD.

**Mandatory spikes:**
1. goszakup GraphQL schema introspection — run __schema query, verify auth token flow, measure actual rate limits
2. NCALayer WebSocket live test — install on Windows VM, call getKeyInfo and signXml with a real certificate, confirm exact JSON envelope and error codes
3. Submission payload capture — manually submit a tender application via goszakup browser UI with DevTools Network open; capture every field in the POST body; this is ground truth for Phase 4
4. MP.kz network traffic analysis — check for internal REST/GraphQL endpoints before committing to Playwright scraping
5. Legal review — confirm automated submission is permissible under goszakup ToS and KZ EDS law; confirm per-action user consent (clicking Sign + entering PIN) satisfies authorization requirements

**Avoids:** Pitfall 8 (hidden required fields), Pitfall 12 (automated submission legality), Pitfall 20 (over-engineering before validation), Pitfall 4 (NCALayer version drift).

**Research flag:** NEEDS research phase — NCALayer spike is niche and underdocumented in English; goszakup submission mutation schema is not publicly detailed.

### Phase 2: Tender Data Pipeline

**Rationale:** Everything downstream requires tenders in the local database. This phase can be built and validated end-to-end before the submission feature exists.

**Delivers:** goszakup and MP.kz sync workers (ARQ, 15/30 min schedule), unified tenders table with JSONB and tsvector GIN index, tender search/filter API with all 8 priority filters, Next.js tender feed with RSC + TanStack Query, NCALayer status indicator on dashboard.

**Implements:** PortalAdapter protocol, both portal adapters, sync_state table, circuit breaker for portal outages, exponential backoff on 429 responses, stale-data cache display during outages.

**Avoids:** Pitfall 5 (goszakup rate limiting), Pitfall 7 (portal downtime — circuit breaker), Pitfall 14 (MP.kz fragility — isolated adapter).

**Research flag:** Standard patterns; skip research phase.

### Phase 3: Document Vault and Company Onboarding

**Rationale:** Document vault is a hard prerequisite for the application pipeline. BIN validation against goszakup supplier registry must happen before any submission attempt. Recruit 2-3 beta users at the end of this phase.

**Delivers:** Document upload/versioning/download (MinIO + pre-signed URLs), document expiry date metadata storage and display, BIN lookup to verify goszakup supplier registration, EDS certificate metadata extraction and expiry warning on dashboard, infrastructure standing up on KZ-hosted provider.

**Avoids:** Pitfall 3 (EDS cert expiry — store notAfter on every NCALayer connect), Pitfall 17 (file size/type validation), Pitfall 19 (unregistered supplier), Pitfall 13 (data localization — KZ hosting confirmed before this phase begins).

**Research flag:** Standard patterns; skip research phase.

### Phase 4: Application Pipeline and EDS Submission

**Rationale:** This is the core product value and the highest technical risk phase. Phase 1 spikes are hard prerequisites. Beta users from Phase 3 test this against real production tenders.

**Delivers:** Application CRUD (draft creation, document attachment), payload XML assembly (/prepare endpoint), useNCALayer() React hook with full connection lifecycle management, certificate selection UI (enumerate certs, filter AUTH type, store alias), signing page with NCALayer status guard, goszakup submission adapter (GraphQL mutation), durable ARQ submission job with retry, application status polling, SUBMIT_FAILED recovery path (Telegram alert + manual download link), server-time-derived deadline countdown with 5-minute cutoff enforcement.

**Avoids:** Pitfall 1 (NCALayer not running), Pitfall 2 (wrong cert type), Pitfall 9 (deadline timing — server clock, 5-min cutoff), Pitfall 10 (submission failure — durable job queue), Pitfall 11 (signature rejection — byte-exact signing), Pitfall 6 (JWT expiry — token manager pre-refreshes before submission).

**Research flag:** NEEDS research phase — goszakup submission mutation and GOST vs RSA handling require current-state verification.

### Phase 5: Notifications

**Rationale:** Telegram notifications are table stakes and the primary discovery channel, but they depend on Phase 2 data and Phase 1 profiles. WhatsApp is additive on the same dispatcher infrastructure.

**Delivers:** Subscription CRUD API and UI (keywords, KTRU codes, region, amount range, portals), Telegram bot with webhook mode, notification dispatcher ARQ job (every 5 min), dedup via UNIQUE constraint, deadline reminders (48h, 24h for tracked tenders), WhatsApp via Twilio as second channel.

**Avoids:** Pitfall 18 (notification rate limits — queued delivery with retry), notification anti-patterns (no past-deadline tenders, no unfiltered spam).

**Research flag:** Standard patterns; skip research phase.

### Phase 6: Hardening and Production Readiness

**Rationale:** Internal beta with real users will surface edge cases before public launch.

**Delivers:** Encryption at rest for signed_xml, goszakup_token, mpkz_token (Fernet), rate limiting on all API endpoints, Sentry error tracking, PostgreSQL GIN trigram index for fuzzy KTRU search, portal health check flag in Redis, NCALayer version check with upgrade prompt, goszakup XML schema version pinning and checksum monitor, data processing agreement in Terms of Service.

**Avoids:** Pitfall 15 (XML schema staleness), Pitfall 16 (NCALayer HTTPS mixed-content — wss:// + cert trust onboarding guide), remaining hardening items across prior phases.

**Research flag:** Standard patterns; skip research phase.

---

### Phase Ordering Rationale

- Phases 1 and 2 precede everything because auth+company profile and local tender data are hard prerequisites for all user-facing features.
- Phase 3 (Document Vault) gates Phase 4 (Applications) — a submission package cannot be assembled without stored documents.
- Phase 4 (Submission) is isolated until Phase 1 spikes are complete — building submission against unverified API contracts is the canonical CIS SaaS failure mode (Pitfall 20).
- Phase 5 (Notifications) is independent of Phase 4 but deprioritized below submission because notifications without submission is a weaker product; goszakup data from Phase 2 is sufficient to start notifications.
- Phase 6 is last by definition; security-critical hardening items (token encryption, signed XML encryption) should be pulled into Phase 4 if beta users are real companies with real BIN data.

### Research Flags Summary

| Phase | Needs Research Phase | Reason |
|-------|---------------------|--------|
| Phase 1 | Yes | NCALayer protocol, goszakup schema, submission payload are all unverified |
| Phase 2 | No | Standard async sync worker + PostgreSQL patterns |
| Phase 3 | No | Standard document storage and onboarding patterns |
| Phase 4 | Yes | goszakup submission mutation schema; GOST signature handling in NCALayer and pyhanko |
| Phase 5 | No | Standard Telegram/WhatsApp bot patterns |
| Phase 6 | No | Standard hardening patterns |

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Next.js/FastAPI/PostgreSQL/ARQ are well-documented; ARQ + httpx + asyncpg pattern is proven in production |
| Features | MEDIUM-HIGH | Regulatory requirements (table stakes) are HIGH; competitor feature lists are MEDIUM (no live scrape possible) |
| Architecture | HIGH | Component boundaries and data flow are standard aggregator patterns; NCALayer browser-only constraint is well-understood |
| Pitfalls | MEDIUM | NCALayer method names and goszakup rate limits are community-sourced; legal items are LOW and require attorney review |

**Overall confidence:** MEDIUM-HIGH on technical implementation. LOW on legal/regulatory items that require Kazakhstani legal counsel.

### Gaps to Address

- **goszakup submission payload fields:** Unknown without browser traffic interception. Block Phase 4 start until Phase 1 Spike 3 is complete. Do not estimate Phase 4 duration until this is resolved.
- **GOST vs RSA signature requirement per tender type:** Whether specific tender categories require GOST-3410 is underdocumented. Verify in Phase 1 Spike 2; add certificate type routing to the submission adapter accordingly.
- **pyhanko GOST-3410-2012-512 support:** Must be verified before committing to pyhanko for backend CMS verification. If absent, NCANode sidecar is the fallback — adds a Docker service and Node.js dependency.
- **goszakup API rate limits (exact numbers):** Official documentation is sparse. Start conservatively at 1-2 RPS; measure empirically in Phase 1 Spike 1; adjust ARQ job schedule and caching TTL accordingly.
- **MP.kz internal API existence:** Network traffic analysis may reveal REST endpoints more stable than Playwright scraping. This changes the MP.kz adapter implementation entirely. Spike 4 must complete before MP.kz work begins.
- **Kazakhstan data localization — adequate protection countries list:** Current MTSRIAP guidance requires legal review. Do not assume any non-KZ cloud provider is compliant without a legal opinion.
- **goszakup test/sandbox environment:** No known sandbox exists. All integration testing runs against production. Spikes require real API tokens and careful rate limit management from day one.

---

## Phase 1 Spikes (Mandatory Before Building)

These must be completed and documented before any Phase 2 implementation begins. Each has a binary pass/fail outcome that gates subsequent work.

1. **goszakup GraphQL API:** Introspect schema via __schema query, verify bearer token auth flow, measure rate limits with conservative test calls, confirm cursor-based pagination behavior, identify TrdBuy field names in current schema version.

2. **NCALayer WebSocket — live test:** On a Windows VM with NCALayer installed, connect to wss://127.0.0.1:14579, call getKeyInfo/browseKeyStore, call signXml with a test payload, confirm exact JSON envelope and error codes, document the version string from getVersion or equivalent method.

3. **Submission payload — browser traffic capture:** Using a real company account on goszakup, initiate a tender application via the browser UI with DevTools Network open, capture the complete HTTP request body (all fields, headers, signed XML structure). This is the ground truth for the Phase 4 submission module.

4. **MP.kz internal API discovery:** Inspect MP.kz network traffic in browser DevTools. If internal REST/GraphQL endpoints exist and are stable, document them as the integration target. If not, Playwright is the fallback; document page structure for scraping.

5. **Legal review:** Engage a Kazakhstan-licensed attorney to review: (a) goszakup.gov.kz ToS compliance for programmatic submission, (b) EDS authorization — does per-action user consent (clicking Sign + entering PIN in NCALayer) satisfy the Law on Electronic Documents and Digital Signatures authorization requirement, (c) liability framework for erroneous auto-submitted bids.

---

## Open Questions

| Question | Blocks | Resolution path |
|----------|--------|----------------|
| Does goszakup API support programmatic application submission, or portal UI only? | Phase 4 | Spike 1 + Spike 3; direct contact with goszakup support if unclear |
| Which tender categories require GOST-3410 vs RSA signature? | Phase 4 | Spike 2 + pki.gov.kz documentation |
| Does pyhanko support GOST-3410-2012-512? | Phase 4 | Test in Spike 2; if not, implement NCANode sidecar |
| Does MP.kz expose internal REST endpoints? | Phase 2 MP.kz adapter | Spike 4 |
| What are the exact goszakup submission payload fields? | Phase 4 | Spike 3 (browser traffic capture) |
| Is automated submission legally permissible under KZ law? | Phase 4 launch | Legal review (Spike 5) |
| Which KZ cloud provider is compliant for data localization? | Phase 3 infrastructure | Legal review + provider capability assessment |
| Does goszakup provide a test/sandbox environment? | Phase 1 | Direct inquiry to goszakup support; assume production-only |

---

## Sources

### Primary (HIGH confidence)
- Kazakhstan Law on Public Procurement (Zakon RK No. 434-V, 04.12.2015) — tender lifecycle, document requirements, procurement methods
- NCALayer v2 documentation — pki.gov.kz (WebSocket protocol, certificate types, method names)
- goszakup Open Data API — ows.goszakup.gov.kz/v3/graphql (GraphQL endpoint, TrdBuy entity structure)
- FastAPI + ARQ async patterns — arq-docs.helpmanual.io, FastAPI official docs
- PostgreSQL 16 tsvector and GIN indexes — postgresql.org/docs

### Secondary (MEDIUM confidence)
- Kazakh developer community (GitHub: NCANode, ncalayer-js-client) — NCALayer WebSocket message envelope details
- zakup.smart.kz, tenderbot.kz, tender.kz — competitor feature observations (training knowledge, no live scrape)
- goszakup rate limit estimates (~100-200 req/min) — developer forum reports, not official documentation
- Kazakhstan personal data localization requirements — published law text; enforcement posture requires current legal review
- pyhanko PKCS#7 / CMS documentation — pyhanko.readthedocs.io

### Tertiary (LOW confidence — must verify before implementation)
- GOST-3410-2012-512 requirement per tender category on goszakup — EAEU harmonization trend, underdocumented
- goszakup ToS permissibility of automated submission — requires direct contact or legal review
- MP.kz API status ("no public API") — inference from site type; verify with network traffic analysis in Phase 1 Spike 4

---

*Research completed: 2026-05-25*
*Ready for roadmap: yes — pending Phase 1 spike results before Phase 4 can be fully estimated*
