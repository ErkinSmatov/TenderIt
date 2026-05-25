# Domain Pitfalls

**Domain:** Kazakhstan e-procurement tender aggregator (TenderIt)
**Researched:** 2026-05-25
**Confidence:** MEDIUM — NCALayer/goszakup specifics from accumulated domain knowledge of
Kazakhstan PKI ecosystem, NBI (National Certification Authority) documentation, and CIS
government API patterns. Web research tools unavailable during this session; flag items
marked LOW confidence for verification against current official documentation before
implementation.

---

## Critical Pitfalls

Mistakes that cause rewrites, data loss, or legal exposure.

---

### Pitfall 1: NCALayer Not Running — Silent Failure at Submission Time

**What goes wrong:**
The frontend calls `new WebSocket('wss://127.0.0.1:14579')` and receives `ECONNREFUSED`
because the user has not started NCALayer, or NCALayer crashed, or Windows firewall
blocked the port. If this isn't caught gracefully, the submission flow either hangs
indefinitely or throws an unhandled JS error with no useful message to the user.

**Why it happens:**
NCALayer is a separate desktop application. It is not a browser extension. It does not
auto-start on login by default on all OS configurations. Users who opened TenderIt in a
fresh browser session after reboot will hit this every time.

**Consequences:**
- User thinks "submit" was clicked and the tender was sent. It wasn't.
- Submission deadline passes. Legal and financial damage to user's business.
- Support volume explosion: "your site doesn't work."

**Prevention:**
1. Always probe the WebSocket connection (`wss://127.0.0.1:14579`) before displaying the
   signing UI. Show a persistent status indicator: "NCALayer: running" / "NCALayer: not
   detected."
2. On connection failure, show exact instructions: download link, how to launch, which
   tray icon to look for — platform-specific (Windows vs macOS vs Linux).
3. Implement a 5-second keepalive ping on the WebSocket during the signing flow. If it
   drops mid-flow, abort and alert immediately.
4. Never allow the "Submit" button to become clickable unless NCALayer is confirmed
   reachable.

**Detection warning signs:**
- Submission status stays on "Подписание..." indefinitely.
- JS console shows `WebSocket connection to 'wss://127.0.0.1:14579' failed`.

**Phase:** Address in the NCALayer integration phase (before any production submission
attempt).

---

### Pitfall 2: Certificate Type Mismatch — Wrong Key Used for Wrong Operation

**What goes wrong:**
Kazakhstan's NCA issues several certificate types that coexist on a single token or P12
file: AUTH (authentication), RSA_SIGNATURE (content signing, RSA algorithm), and
GOST_SIGNATURE (content signing, GOST R 34.10-2015 algorithm — also called GOST or
ЭКАV). Picking the wrong one causes signature rejection by the portal's verification
service, with an opaque error code.

**Details (MEDIUM confidence — verify against current NBI documentation):**
- `AUTH` certificates: for TLS client authentication only. Never use for document signing.
  Portals that verify document signatures explicitly reject AUTH-signed CMS.
- `RSA_SIGNATURE`: acceptable for document signing on most current goszakup flows.
- `GOST_SIGNATURE`: Kazakhstan began requiring GOST signatures for some official document
  flows aligned with EAEU (Eurasian Economic Union) interoperability requirements. Some
  tender categories on goszakup require GOST; others accept RSA. This distinction is
  tender-type dependent and underdocumented.
- A user's token may have only RSA keys if issued before GOST rollout, or only GOST if
  issued recently — you cannot guarantee which is present.

**Consequences:**
- Signature validation fails on portal. Portal returns error 500 or "подпись
  недействительна." Tender application rejected.
- If you hard-code `RSA_SIGNATURE`, users with GOST-only tokens cannot sign at all.

**Prevention:**
1. On connection to NCALayer, call `getKeys` (or the equivalent `browseKeyStore` /
   `getSubjectDN` sequence) to enumerate ALL available certificates on the token.
2. Present the user a selection of valid signing certificates (filter out AUTH type).
3. Store which certificate alias the user selected alongside the company profile so they
   don't re-select every session.
4. When calling `signData` / `createCMSSignatureFromFile`, pass the exact `alias` of the
   selected certificate.
5. Log the certificate's subject DN and serial number with every submission record for
   audit trail.

**Detection warning signs:**
- Portal API returns `signatureInvalid` or HTTP 422 after what appeared to be a
  successful NCALayer signing operation.
- User reports "работает у одних, не работает у других."

**Phase:** Address in NCALayer integration phase. Certificate enumeration UI must be
built before first real submission test.

---

### Pitfall 3: ЭЦП Certificate Expiry — Submission Fails Silently at Deadline

**What goes wrong:**
Kazakhstan ЭЦП certificates issued by NCA have a 1-year validity period (individual) or
2-year period (legal entity), depending on issuance type. An expired certificate will
produce a CMS signature that is technically valid in structure but fails portal-side
temporal validation. The portal may return an error like "срок действия сертификата
истёк" or simply reject the application with a generic error.

**Why it happens:**
Users do not monitor certificate expiry. The platform signs on their behalf without
warning them. A user may have a working cert today but it expires in 3 days, right before
a major tender deadline.

**Consequences:**
- Submission rejected. Tender opportunity lost.
- User blames the platform. Chargeback risk after monetization.

**Prevention:**
1. On every NCALayer connection, extract the `notAfter` field from the certificate's
   X.509 structure (available via NCALayer's `getSubjectDN` or equivalent info call).
2. Store `cert_expires_at` in the user's company profile in PostgreSQL.
3. Send proactive notifications: 30 days before expiry, 14 days, 7 days, and on day-of.
4. Display a prominent banner in the UI when cert expires within 30 days.
5. Block auto-submission (not manual) when cert is expired; surface clear instructions
   for renewal at NCA (pki.gov.kz).

**Detection warning signs:**
- Portal validation error mentioning "сертификат" after a structurally valid CMS is
  produced.
- `notAfter` field in cert X.509 is in the past.

**Phase:** Address in NCALayer integration phase. Certificate metadata extraction is
mandatory before MVP launch.

---

### Pitfall 4: NCALayer Version Drift — API Contract Breaks Without Warning

**What goes wrong:**
NBI (National Certification Authority of Kazakhstan) releases NCALayer updates that
occasionally rename, remove, or change the behavior of WebSocket commands. The command
structure evolved significantly between NCALayer 1.x and 2.x. Users on older versions
will experience broken signing flows if your code targets a newer API surface, and vice
versa.

**Details (MEDIUM confidence):**
- NCALayer 2.x uses a JSON-RPC-style message format over the WebSocket.
- Earlier versions used a different message envelope.
- The `method` field names differ between versions (e.g., `browseKeyStore` vs `getKeys`
  depending on version).
- NBI does not always maintain backward compatibility.

**Consequences:**
- Signing works in your dev environment (latest NCALayer) but fails for a portion of
  production users on older installs.

**Prevention:**
1. On WebSocket connect, call the version-check method (NCALayer exposes something like
   `getVersion` or `browseInfo`). Parse the returned version string.
2. If version is below your minimum supported version, display an upgrade prompt with a
   direct link to pki.gov.kz download page before proceeding.
3. Maintain a compatibility matrix in code (version → supported command set).
4. Pin your NCALayer integration to the minimum version you tested against and document
   this in onboarding.

**Detection warning signs:**
- `"method not found"` or `"unknown command"` error in NCALayer WebSocket response.
- Works for some users, broken for others with the same OS.

**Phase:** Address in NCALayer integration phase. Version check must be the first action
on every WebSocket connection.

---

### Pitfall 5: goszakup.gov.kz API Rate Limiting and IP Blocking

**What goes wrong:**
The goszakup GraphQL API (`https://ows.goszakup.gov.kz/v3/graphql`) applies rate limits
per API token. Aggressive polling for tender updates (e.g., polling every 30 seconds
across all tender categories) will hit these limits and result in 429 responses or, worse,
silent IP-level blocks at the WAF layer. WAF blocks are not announced and can affect all
users of your platform simultaneously since your server shares one IP (or IP range).

**Why it happens:**
Developers build a naive background scheduler: "fetch all new tenders every 5 minutes."
At scale (many search filter combinations), this multiplies into hundreds of API calls
per cycle.

**Consequences:**
- API token revoked. All tender aggregation stops. All users affected simultaneously.
- Goszakup operator may contact you; in worst case, access permanently terminated.

**Prevention:**
1. Design the aggregation layer around a single shared API token with centralized
   rate-limit tracking.
2. Use cursor-based pagination and incremental fetching: store `last_updated_at` per
   category, fetch only `updatedAt > last_seen`.
3. Implement exponential backoff with jitter on any 429 or 503 response.
4. Add a request queue with a configurable max RPS (start conservatively at 1–2 RPS).
5. Cache aggressively: tender detail pages don't change once published. Cache with TTL
   of 30–60 minutes.
6. For MVP, a 15-minute polling interval is sufficient and safe. Don't optimize for
   real-time until you understand the actual API limits.
7. Maintain a fallback: if the primary API token is rate-limited, queue and retry — do
   not surface the error to users as "no new tenders."

**Detection warning signs:**
- Intermittent empty responses with HTTP 200 but zero results.
- HTTP 429 in API logs.
- Sudden drop in tender count for users.

**Phase:** Address in tender aggregation phase (Phase 1 or 2). Rate limiting
architecture must precede production launch.

---

### Pitfall 6: JWT Token Expiry During Long User Sessions

**What goes wrong:**
The goszakup API uses JWT bearer tokens obtained via OAuth2. These tokens have a fixed
expiry (commonly 1 hour, though goszakup-specific TTL should be verified). Long-running
background jobs that were issued a token at start time will fail mid-execution when the
token expires, with a 401 response. If the token refresh logic is not idempotent, you
can end up with duplicate submission attempts or partial state.

**Why it happens:**
Background sync jobs are fire-and-forget. Token expiry during job execution is not
handled.

**Consequences:**
- Tender data sync stops partway through. Corrupted or incomplete tender cache.
- Submission job fails with 401 after user has already signed the document — but before
  the signed document reaches the portal. User believes submission was sent.

**Prevention:**
1. Implement a token manager singleton: pre-emptively refresh the token 5 minutes before
   expiry. Store expiry in memory alongside the token.
2. All API clients fetch token from the manager, not from a static config.
3. On 401, attempt exactly one token refresh and retry. If refresh fails, alert via
   monitoring. Do not retry indefinitely.
4. For the submission flow specifically: acquire a fresh token immediately before the
   submission API call, even if the existing token appears valid.
5. Separate submission tokens from aggregation tokens if the API supports multiple token
   scopes.

**Detection warning signs:**
- 401 errors appearing in logs ~1 hour after service start or last token refresh.
- Submission status "Отправлено" recorded but portal shows no application received.

**Phase:** Address in API integration foundation phase. Token lifecycle management must
be built as infrastructure, not afterthought.

---

### Pitfall 7: goszakup API Instability and Maintenance Windows

**What goes wrong:**
goszakup.gov.kz is a government system that undergoes scheduled and unscheduled
maintenance. The API goes down on Kazakhstan public holidays, sometimes without advance
notice. During maintenance, the API may return 500 errors, malformed JSON, or simply
timeout. If your application has no circuit breaker, these errors propagate to users as
broken UI.

**Additionally:** The portal occasionally returns HTTP 200 with an HTML error page
(maintenance splash page) instead of JSON, which breaks JSON parsing.

**Why it happens:**
Government systems in CIS region do not follow SaaS uptime standards. Maintenance
is treated as a normal operational mode.

**Consequences:**
- Users cannot view tenders during maintenance. Acceptable if handled gracefully.
- Submissions attempted during maintenance fail. Not acceptable if the user doesn't know.
- JSON parse errors crash the sync service if not caught.

**Prevention:**
1. Always check `Content-Type` header before JSON parsing. If HTML received, treat as
   "service unavailable" and circuit-break.
2. Implement a circuit breaker (e.g., using `tenacity` in Python): after 3 consecutive
   failures, stop calling for 5 minutes, surface a status banner to users.
3. Cache the last successful tender fetch. During outages, show stale data with a
   timestamp: "Данные актуальны на [время]."
4. Store a "portal status" flag in Redis. Background health check updates it every
   5 minutes. UI reads this flag.
5. Never allow submission to proceed if the portal API health check is failing. Show:
   "Портал Госзакупки временно недоступен. Попробуйте через X минут."

**Phase:** Address in tender aggregation phase. Circuit breaker is MVP-critical because
goszakup outages will occur within the first week of production use.

---

### Pitfall 8: Incomplete API Data vs. Portal UI — "Hidden" Required Fields

**What goes wrong:**
The goszakup GraphQL API exposes a subset of the data visible on the portal UI. Some
fields that appear mandatory when submitting via the browser UI are not documented in the
API schema — or are documented as optional but actually required by server-side
validation. You discover this only when a programmatic submission is rejected with a
validation error that the human web flow never triggers.

**Common examples (MEDIUM confidence — verify per current API version):**
- `technicalSpec` XML blob with specific sub-element ordering.
- `supplierQualificationData` fields that appear auto-populated in the browser from the
  user's profile but must be explicitly provided in API calls.
- Document attachment metadata (MIME type, exact file name format).
- Lot-level vs. application-level fields: some fields apply per-lot and must be repeated
  for each lot even if they share the same value.

**Consequences:**
- Auto-submitted application is rejected server-side with a 422 or business-logic error.
- Application is never formally submitted. Deadline passes. User unaware.

**Prevention:**
1. Before building the auto-submission API client, manually submit several real
   applications via the goszakup web UI while intercepting network traffic (browser
   DevTools Network tab). Capture the exact HTTP request body including all fields.
2. Treat the intercepted request body as ground truth. Do not rely solely on the
   published API documentation.
3. Build a submission dry-run mode: construct the full payload and validate it against
   the API's validation endpoint (if one exists) before actually submitting.
4. Log the full API request and response for every submission attempt. Store this in
   PostgreSQL linked to the application record.
5. If the portal returns a validation error, expose the raw error message (translated if
   possible) to the user rather than hiding it.

**Phase:** Address in submission engine phase. This requires a dedicated research spike
before implementing the submission module.

---

### Pitfall 9: Tender Submission Timing — Server Time vs Local Time vs Deadline

**What goes wrong:**
Tender deadlines on goszakup are enforced by the portal's server clock (Almaty time,
UTC+5). A user in Astana (same timezone) who submits at what they believe is 1 minute
before deadline may have the submission rejected if:
- The portal server clock differs from the user's browser clock.
- The portal has a network processing delay that pushes the server-receipt timestamp
  past the deadline.
- The user's browser/OS has an incorrect timezone or drift.

Government portal systems in Kazakhstan have been known to close submissions up to
60 seconds before the posted deadline due to internal processing buffers.

**Consequences:**
- Application is submitted (from user's perspective) but rejected as "late" by the portal.
- No recourse. The tender opportunity is permanently lost.

**Prevention:**
1. Always display deadlines using the portal's server time, not the user's local
   browser time. Fetch server time from the API or use a reliable NTP source.
2. Display a countdown to deadline that is server-clock-derived.
3. Enforce a hard cutoff in TenderIt's auto-submission engine: **do not attempt
   submission within 5 minutes of the deadline**. Display a warning: "Осталось менее 5
   минут. Рекомендуем подать вручную на портале."
4. Log the exact timestamp of the HTTP response from goszakup acknowledging receipt, not
   the timestamp of when TenderIt sent the request.
5. Include a timezone-aware display in the UI showing: "Дедлайн: 17:00 по Алматы
   (UTC+5) — ваше время: 17:00 МСК."

**Phase:** Address in submission engine phase. Server-time synchronization must be a
first-class concern, not an afterthought.

---

### Pitfall 10: Failed Auto-Submission — No Recovery Path

**What goes wrong:**
The auto-submission attempt fails after the user has already signed the document. Failure
modes include: network timeout, portal API error, goszakup maintenance window, JWT
expiry, malformed payload. The signed CMS blob exists but was never sent. Without a
retry queue, this signed document is lost, and the user must restart the entire process
(which may require re-signing with NCALayer if the nonce/timestamp in the CMS is no
longer valid).

**Why it happens:**
Submission is implemented as a synchronous HTTP call with no queue. "Submit" button
triggers a request, response determines outcome. No durability.

**Consequences:**
- User loses tender opportunity without knowing why.
- If the deadline has passed, no recovery is possible at all.
- User loses trust: "I clicked submit, it said success, but my application isn't on the
  portal."

**Prevention:**
1. Model the submission as a durable job, not a synchronous API call. Use a job queue
   (Celery + Redis, or PostgreSQL-backed queue). Store the signed payload in PostgreSQL
   before the first submission attempt.
2. The job has states: `pending` → `in_flight` → `submitted` | `failed`. Show these
   states in the UI.
3. On failure, the job retries with exponential backoff up to N attempts (e.g., 5
   attempts over 30 minutes), as long as the deadline has not passed.
4. If the signed CMS blob expires (CMS signatures include signing time; check portal
   acceptance window), alert the user to re-sign before retrying.
5. After final failure, notify the user via Telegram/WhatsApp with the exact error and a
   direct link to the portal to submit manually. Include the signed document for download
   so they can submit it themselves.
6. Never mark a submission as "Отправлено" until you receive a successful HTTP 200/201
   from the portal AND the response body contains a valid application ID.

**Phase:** Address in submission engine phase. Durable submission queue is MVP-critical.

---

### Pitfall 11: Signature Validation Rejection on Portal Side

**What goes wrong:**
TenderIt produces a CMS (Cryptographic Message Syntax) signature via NCALayer. The portal
rejects this signature with "подпись не прошла проверку" even though NCALayer reported
success. Common causes:
- The data that was signed does not exactly match what the portal expects to verify
  against (encoding difference, BOM in XML, whitespace normalization).
- The CMS was created in `detached` mode but the portal expects `attached`, or vice versa.
- The signed data was base64-encoded before passing to NCALayer, then the signature was
  created over the base64 string rather than the raw bytes.
- The XML document had its namespace declarations reordered by an XML library, changing
  the canonical form that was signed.

**Why it happens:**
CMS/PKCS#7 signing is sensitive to exact byte representation. Any pre-processing of the
document before signing (or any post-processing after) invalidates the signature.

**Consequences:**
- Application structurally submitted but fails signature verification. Rejected.

**Prevention:**
1. Sign the exact bytes that the portal will verify. If submitting an XML document, sign
   the canonicalized (C14N) form if that is what the portal verifies — confirm this by
   intercepting successful manual submissions.
2. Do not base64-encode the document before passing to NCALayer unless the API
   specifically requires it for transport (and if so, ensure NCALayer signs the
   pre-encoded original bytes).
3. Test the signature verification chain end-to-end using Kazakhstan NCA's public
   verification tools before implementing production submission.
4. Use `detached: false` (attached signature) unless documentation explicitly states
   detached is required.
5. Store the exact byte sequence that was signed alongside the CMS in PostgreSQL.

**Phase:** Address in submission engine phase. Requires a spike against the portal's
signature verification endpoint before full implementation.

---

## Moderate Pitfalls

---

### Pitfall 12: Automated Submission — Legal and Regulatory Standing

**What goes wrong:**
The Закон РК «О государственных закупках» (Law on Public Procurement) requires that
tender applications are submitted by an authorized representative of the supplier company.
The ЭЦП (digital signature) legally identifies and commits the signing entity. If TenderIt
signs and submits automatically without the authorized person's explicit, contemporaneous
intent for each specific tender, there is a legal grey area around whether the submission
constitutes valid acceptance of the tender terms.

**Specific risks (MEDIUM confidence — requires legal review by a KZ-licensed attorney):**
- If a submission error causes a winning bid to be submitted at the wrong price, the
  company may be legally bound. Disclaimer in ToS may not fully protect against this
  under KZ civil law.
- Goszakup's own ToS may prohibit automated programmatic submissions without prior
  approval from МЦРИАП (Ministry of Digital Development). This is a common restriction
  on CIS government portals.
- If the user's ЭЦП is used without their explicit per-action consent (e.g., a
  fully-automated overnight submission), this could constitute unauthorized use of an
  electronic signature under the Закон РК «Об электронном документе и электронной
  цифровой подписи».

**Prevention:**
1. **Never submit without explicit user action for each tender.** The user must click a
   final "Подтвердить подачу" button for each specific application. Do not allow
   "auto-submit while I'm asleep" as an MVP feature.
2. Require NCALayer signing at submission time, not as a pre-authorized credential.
   The user physically interacts with NCALayer for each submission. This is strong evidence
   of contemporaneous intent.
3. Include explicit consent language in the submission confirmation: "Я, [ФИО], действуя
   от имени [Компания], подтверждаю подачу заявки на тендер [номер]."
4. Log timestamped user action for every submission: IP address, user agent, session ID,
   signed document hash.
5. Commission a legal review from a Kazakhstani attorney before launching to real users.
   Specifically ask about: (a) ToS compliance with goszakup.gov.kz, (b) ЭЦП usage
   authorization requirements, (c) liability for auto-submitted bids.

**Phase:** Address in legal/compliance review before any real user onboarding. This
is not a "phase 5" concern — it must be resolved before MVP launch with real companies.

---

### Pitfall 13: Kazakhstan Data Localization Requirements

**What goes wrong:**
Kazakhstan's Закон РК «О персональных данных и их защите» (Law on Personal Data and
its Protection, 2013, as amended) and accompanying regulations from МЦРИАП require that
personal data of Kazakhstan citizens and legal entities be stored on servers physically
located within Kazakhstan (or in countries with an adequate protection level as
designated by the authorized body).

TenderIt stores:
- BIN (Business Identification Number) — considered personal/company data.
- Director's full name, IIN (Individual Identification Number) — personal data.
- Uploaded documents (passports, certificates, licenses) — personal data.
- ЭЦП certificate information.

**Consequences:**
- Hosting on AWS eu-central-1 (Frankfurt) or similar non-KZ regions for user data is
  potentially non-compliant.
- МЦРИАП can issue orders requiring data localization. Fines and access blocking are
  possible enforcement mechanisms.
- Companies storing their documents on your platform may face compliance questions from
  auditors.

**Prevention:**
1. Investigate hosting options within Kazakhstan: KazCloud (Kazteleport), national
   cloud from Beeline KZ, or Yandex Cloud KZ (Almaty region). Verify their compliance
   certification.
2. Alternatively, separate PII/documents from operational data: store tender catalog
   (non-personal) anywhere; store user documents and IIN/BIN data exclusively on KZ
   infrastructure.
3. Get a legal opinion on whether "adequate protection level" countries are available as
   an alternative before going with a non-KZ cloud.
4. Include a data processing agreement (DPA) in your Terms of Service that addresses
   data localization.

**Phase:** Address in infrastructure planning phase (before user data is collected in
production). Do not defer to "after launch."

---

### Pitfall 14: MP.kz API — Undocumented and Fragile

**What goes wrong:**
MP.kz (commercial tender platform) does not publish a formal API. Integration is likely
based on reverse-engineered REST endpoints or undocumented GraphQL, making it
brittle. Any platform update by MP.kz can break integration without notice.

**Consequences:**
- MP.kz integration goes dark silently. Users stop seeing commercial tenders.
- No SLA or support channel for API consumers.

**Prevention:**
1. Treat MP.kz integration as best-effort, not guaranteed. Communicate this to users.
2. Add specific health checks and alerting for MP.kz data freshness (if no new tenders
   in 24 hours, trigger alert).
3. Abstract the data source layer so MP.kz can be disabled without affecting goszakup.
4. Monitor MP.kz's front-end for layout/API changes as part of a weekly integration
   smoke test.

**Phase:** Address in aggregation phase. Keep MP.kz isolated behind an adapter interface.

---

### Pitfall 15: Document Format Requirements — XML Schema Strictness

**What goes wrong:**
Goszakup applications often require documents in specific XML formats defined by XSLT or
XSD schemas. These schemas are occasionally updated by МЦРИАП without public announcement.
An application submitted with a slightly outdated schema version will fail validation.

**Prevention:**
1. Pin the exact XML schema version used in each submission in the database.
2. Subscribe to goszakup developer announcements (if any list exists) or implement a
   schema checksum monitor.
3. Build XML generation from a schema-driven library, not string templating, to catch
   structural issues at generation time.
4. Before each production submission, validate the generated XML against the schema
   locally before sending.

**Phase:** Address in submission engine phase as part of payload construction module.

---

## Minor Pitfalls

---

### Pitfall 16: NCALayer CORS and HTTPS Mixed-Content Blocking

**What goes wrong:**
If TenderIt is served over HTTPS, browsers block WebSocket connections to
`ws://127.0.0.1:14579` (insecure WebSocket from secure origin) due to mixed-content
policy. NCALayer 2.x switched to `wss://` (secure WebSocket on port 14579) using a
self-signed certificate. This self-signed cert is not trusted by browsers by default.
Users must manually add a certificate exception on first use.

**Prevention:**
1. Use `wss://127.0.0.1:14579` (note: secure WebSocket).
2. On first launch, detect the untrusted cert scenario (WebSocket connection fails with a
   specific error) and guide the user through the certificate trust step with
   platform-specific screenshots.
3. NCALayer's installer on Windows typically adds the cert to the Windows trusted store.
   macOS users may need to manually trust via Keychain. Linux users may need to add to
   browser-specific cert stores.

**Phase:** Address in NCALayer integration phase as part of onboarding flow.

---

### Pitfall 17: PostgreSQL Document Storage — File Size and Type Validation

**What goes wrong:**
Users upload passports, licenses, and certificates as attachments. Without server-side
validation: oversized files (PDFs can be 50MB+), wrong MIME types, malformed PDFs, or
password-protected PDFs are accepted and stored, then fail when the portal tries to
process them during submission.

**Prevention:**
1. Validate file size (max 10MB per file, per goszakup requirements — verify current
   limit), MIME type, and basic file integrity on upload.
2. For PDF files, attempt a lightweight parse (check magic bytes `%PDF-`) before storing.
3. Store files in an S3-compatible object store (e.g., MinIO on KZ infrastructure), not
   in PostgreSQL bytea fields. Store only the object key + metadata in PostgreSQL.

**Phase:** Address in document storage phase.

---

### Pitfall 18: Telegram / WhatsApp Notification Delivery Failures

**What goes wrong:**
Telegram Bot API has rate limits (30 messages/second per bot, 1 message/second per chat).
WhatsApp Business API (via third-party provider since there's no official self-serve API
in KZ) has its own rate limits and message template approval requirements. Notification
delivery failures are silent unless explicitly handled.

**Prevention:**
1. Queue all notifications through a job queue with retry.
2. For WhatsApp, use only pre-approved message templates to avoid spam filtering.
3. Provide a fallback in-app notification center so users can see missed alerts.

**Phase:** Address in notification phase.

---

### Pitfall 19: BIN Validation — Companies Not Registered on Goszakup Portal

**What goes wrong:**
A company can exist in the KZ business registry (МЮРК) with a valid BIN but not be
registered as a supplier on goszakup.gov.kz. Attempting to submit a tender application
for an unregistered supplier will fail with a registration error. First-time users will
not understand why.

**Prevention:**
1. After company profile creation, attempt a goszakup API lookup by BIN to verify
   supplier registration status.
2. If the company is not registered, surface a clear onboarding step: "Ваша компания не
   зарегистрирована на портале Госзакупки. [Инструкция по регистрации]."
3. Block the submission flow until supplier registration is confirmed.

**Phase:** Address in company profile / onboarding phase.

---

### Pitfall 20: CIS SaaS Anti-Pattern — Over-Engineering Before Validation

**What goes wrong:**
Common in CIS B2B SaaS: teams spend 3–6 months building a "complete" platform before
a single real user submits a tender. Government API integrations turn out to behave
differently than documented. The submission flow built in isolation fails with real
credentials against real production tenders. Major rework required.

**Prevention:**
1. Build the smallest possible end-to-end path first: one tender, one user, one real
   submission. Validate it works before building scale-out features.
2. Recruit 2–3 beta users (real KZ companies) during Phase 2 or 3, not after Phase 6.
3. Test with a real API token against the production goszakup API from day one of
   integration work, not against a test environment (if a test environment even exists —
   goszakup has historically not provided sandbox access).

**Phase:** This is a process pitfall. Address it in project governance from day one.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|---|---|---|
| NCALayer integration | NCALayer not running, wrong cert type, version mismatch | Pitfalls 1, 2, 4: build connection guard and cert enumeration before any signing code |
| NCALayer integration | Cert expiry | Pitfall 3: extract and store `notAfter` on every connection |
| NCALayer integration | Mixed-content HTTPS | Pitfall 16: use `wss://`, guide cert trust setup |
| Tender aggregation | Rate limiting and IP block | Pitfall 5: request queue + exponential backoff from day 1 |
| Tender aggregation | Portal downtime / malformed responses | Pitfall 7: circuit breaker + stale cache display |
| Tender aggregation | MP.kz fragility | Pitfall 14: isolated adapter, best-effort SLA |
| API foundation | JWT expiry in background jobs | Pitfall 6: token manager singleton |
| Submission engine | Wrong cert type in signature | Pitfall 2: user-selected cert alias stored in profile |
| Submission engine | Submission failure with no recovery | Pitfall 10: durable job queue is non-negotiable |
| Submission engine | Timing / deadline enforcement | Pitfall 9: server-time-derived countdown, 5-min cutoff |
| Submission engine | Signature rejection | Pitfall 11: byte-exact signing + end-to-end sig verification test |
| Submission engine | Incomplete required fields | Pitfall 8: intercept real browser submissions as ground truth |
| Submission engine | XML schema staleness | Pitfall 15: schema-driven generation + version pinning |
| Company onboarding | Unregistered supplier | Pitfall 19: BIN lookup on profile creation |
| Document storage | File size / type / MIME issues | Pitfall 17: server-side validation + S3-compatible store |
| Notifications | Rate limits, silent failures | Pitfall 18: queued notifications with retry |
| Legal / compliance | Automated submission legality | Pitfall 12: legal review before real user onboarding |
| Infrastructure setup | Data localization | Pitfall 13: KZ-hosted infrastructure for PII/documents |
| All phases | Over-engineering before validation | Pitfall 20: recruit beta users early, test with real production API |

---

## Confidence Notes

| Area | Confidence | Basis |
|---|---|---|
| NCALayer WebSocket behavior (port, WSS, cert types) | MEDIUM | Kazakhstan PKI ecosystem knowledge; verify exact method names against current NCALayer 2.x release notes at pki.gov.kz |
| goszakup API rate limiting | MEDIUM | General CIS government API patterns; exact limits not publicly documented — test empirically |
| JWT expiry and token lifecycle | HIGH | Standard OAuth2 implementation pattern; verify token TTL against goszakup API developer docs |
| Certificate expiry period (1yr/2yr) | MEDIUM | NCA historical issuance policy; verify current policy at pki.gov.kz |
| Data localization law (Закон о персданных) | MEDIUM | Published law; enforcement posture and "adequate country" list require current legal review |
| Automated submission legality | LOW | Requires Kazakhstani legal counsel — do not rely on this research alone |
| MP.kz API documentation status | MEDIUM | Known to have no public API; confirm current integration method |
| GOST signature requirement per tender type | LOW | EAEU harmonization trend is real; exact current requirement per tender category needs verification against goszakup portal documentation |

---

## Sources

- Kazakhstan Law on Public Procurement (Закон РК от 04.12.2015 №434-V) — official text
  at adilet.zan.kz (verify current amendments)
- Kazakhstan Law on Electronic Documents and Digital Signatures (Закон РК от 07.01.2003
  №370-II, as amended) — adilet.zan.kz
- Kazakhstan Law on Personal Data and its Protection (Закон РК от 21.05.2013 №94-V)
- NCALayer documentation — pki.gov.kz (verify current version; documentation quality
  is uneven and may require reading the source JS examples rather than prose docs)
- Goszakup developer portal — goszakup.gov.kz/ru/developer (verify current API version
  and rate limit documentation)
- МЦРИАП (Ministry of Digital Development, Innovations and Aerospace Industry of
  Kazakhstan) — mdai.gov.kz for current data localization guidance

**Note:** All web research tools (WebSearch, WebFetch) were unavailable during this
research session. All pitfalls are derived from domain knowledge of Kazakhstan government
digital infrastructure, NCA PKI patterns, and CIS e-procurement ecosystems. Items marked
MEDIUM or LOW confidence must be verified against current official sources before
implementation decisions are made.
