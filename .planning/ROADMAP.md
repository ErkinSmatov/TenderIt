# TenderIt — Roadmap

## Project

**Core value:** Подача тендерной заявки за 3 клика: вставил ID → подписал ЭЦП → система подаёт автоматически когда тендер откроется.
**Platforms v1:** goszakup.gov.kz (Унифицированные сервисы API, токен получен)
**Stack:** Next.js 14 + FastAPI + PostgreSQL 16 + Redis + ARQ + MinIO

---

## Phases

- [x] **Phase 1: Spikes & Foundation** — Resolve all critical unknowns and stand up the project skeleton (completed 2026-05-28)
- [ ] **Phase 2: Auth & Company Profile** — Users can register, log in, and maintain a verified company identity
- [ ] **Phase 3: Tender Data Pipeline** — Users can search and browse aggregated tenders from both portals
- [ ] **Phase 4: Document Vault** — Users can store, categorise, and track expiry of company documents
- [ ] **Phase 5: EDS Signing & Submission** — Users can sign and submit applications via NCALayer
- [ ] **Phase 6: Notifications** — Users receive Telegram and WhatsApp alerts for matching new tenders
- [ ] **Phase 7: Discovery & Matching** — Users configure filters; system auto-matches and notifies via Telegram

---

## Phase Details

### Phase 1: Spikes & Foundation
**Goal**: Verify all critical API contracts and legal constraints before writing any integration code, and stand up the project skeleton so spike results run against real infrastructure.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: SPIKE-01, SPIKE-02, SPIKE-03, SPIKE-04, SPIKE-05
**Success Criteria** (what must be TRUE):
  1. Developer has documented goszakup GraphQL schema, confirmed auth token flow, and recorded actual rate limits from live calls
  2. Developer has called NCALayer `signXml` against a real certificate on a Windows VM and recorded the exact JSON request/response envelope
  3. Developer has captured a complete goszakup browser submission payload via DevTools and saved it as ground-truth spec for Phase 5
  4. Developer has determined whether MP.kz exposes stable internal REST/GraphQL endpoints (vs. Playwright fallback), documented with network trace evidence
  5. Legal opinion is in writing: automated programmatic goszakup submission is permissible, per-action user consent (click + PIN) satisfies KZ EDS law, and infrastructure hosting requirements are confirmed
**Plans**: TBD
**UI hint**: no

### Phase 2: Auth & Company Profile
**Goal**: Users can create an account, authenticate securely, and maintain a complete company profile that will be used across all downstream features.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, COMP-01, COMP-02
**Success Criteria** (what must be TRUE):
  1. User can register with email and password and receive a confirmation; an invalid email or duplicate account is rejected with a clear message
  2. User can log in and remain authenticated across browser sessions (JWT refresh flow) until they explicitly log out
  3. User can reset a forgotten password via an emailed link and set a new password successfully
  4. User can fill in and save company profile fields (BIN, company name, legal address) and edit them at any later time
**Plans**: 5 plans
- [x] 02-01-PLAN.md — Wave 0 foundation: settings, deps, models, migration, BIN validator, test scaffolding
- [x] 02-02-PLAN.md — Wave 1 vertical slice: registration + login + middleware + dashboard placeholder
- [x] 02-03-PLAN.md — Wave 2: refresh token rotation + logout
- [x] 02-04-PLAN.md — Wave 3: password reset (forgot + reset endpoints + pages)
- [x] 02-05-PLAN.md — Wave 4: company profile GET/PUT + profile page + form
**UI hint**: yes

### Phase 3: Tender Lookup
**Goal**: Users can find a specific tender by ID, view its full details, and add it to their watchlist for document preparation and auto-submission.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: SRCH-01, SRCH-02, SRCH-03, SRCH-04
**Success Criteria** (what must be TRUE):
  1. User can enter a tender ID (номер объявления) into a search field and the system returns the matching tender from goszakup Unified Services API
  2. User sees a tender card with: title, lot description, customer (заказчик), contract amount, submission deadline, and current status
  3. User can add the tender to their watchlist; the watchlist is persisted and visible on the dashboard
  4. An unknown or malformed tender ID returns a clear "not found" message, not a crash
**Plans**: 4 plans
- [ ] 03-00-PLAN.md — Wave 0 spike: confirm token, record numberAnno/date/open-status, scaffold tests + react-query provider
- [ ] 03-01-PLAN.md — Wave 1: Tender+UserWatchlist models, migration, goszakup service, 30-min cache-aside
- [ ] 03-02-PLAN.md — Wave 2: tender schemas + auth-gated routes (lookup, watchlist CRUD) + integration tests
- [ ] 03-03-PLAN.md — Wave 3: search page, TenderCard, WatchlistButton, dashboard watchlist section
**UI hint**: yes

### Phase 4: Document Vault
**Goal**: Users can upload, categorise, and manage their company documents in a persistent vault, with automatic expiry warnings and auto-attachment to new applications.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: DOCS-01, DOCS-02, DOCS-03, DOCS-04, DOCS-05
**Success Criteria** (what must be TRUE):
  1. User can upload a document (PDF, DOCX, any format) and it is stored durably in MinIO and retrievable via pre-signed download URL
  2. User can assign a category to each document (устав, лицензия, сертификат, свидетельство о регистрации, прочее) and change it later
  3. User can set an expiry date on a document; the UI shows a warning indicator 14 days before and 7 days before the expiry date
  4. User can delete a document from the vault and it is removed from all future application drafts
  5. When a new application draft is created, the system automatically pre-attaches the company's current (non-expired) documents to the document list
**Plans**: 3 plans
- [x] 04-01-PLAN.md — Wave 1: deps (minio, python-multipart) + config + MinIO service + Document model + schemas + compute_expiry_status + migration 0003 + test scaffold
- [x] 04-02-PLAN.md — Wave 2: 6 auth-gated routes (upload/list/attachable/url/patch/delete) + document_service CRUD + IDOR protection + MinIO-mock unit tests
- [x] 04-03-PLAN.md — Wave 3: /documents page + DocumentUploadForm + DocumentCard (expiry badges) + DocumentVault + uploadFile helper + Sidebar nav + human-verify
**UI hint**: yes

### Phase 5: EDS Signing & Submission
**Goal**: Users can prepare a signed application draft in advance; when a watched tender opens for applications, the system notifies the user via Telegram/WhatsApp and auto-submits upon confirmation (or after 15-minute timeout fallback).
**Mode:** mvp
**Depends on**: Phase 3, Phase 4
**Requirements**: SIGN-01, SIGN-02, SIGN-03, SIGN-04, SIGN-05, APPL-01, APPL-02, APPL-03, APPL-04, APPL-05, APPL-06, APPL-07, APPL-08, APPL-09
**Success Criteria** (what must be TRUE):
  1. On any signing page, the UI shows a real-time NCALayer connectivity status indicator (green/red); the Sign button is disabled when NCALayer is unreachable, and an installation guide is shown if it is not running
  2. Before signing, user can see the EDS certificate owner name and expiry date; a persistent warning appears if the certificate expires within 30 days
  3. User can create an application draft for a watched tender, review the list of documents that will be included, enter their NCALayer PIN, and complete signing — receiving the signed XML back from NCALayer within the same page flow
  4. After signing, application is stored in Подписано state and waits for the tender to open
  5. An ARQ polling job checks the status of each watched tender with a signed draft via goszakup API; when status changes to «open for applications», the job fires immediately
  6. User receives a Telegram/WhatsApp message: «Тендер №{ID} открыт. Подаём заявку? [Да] [Нет]»; if "Да" or no reply in 15 minutes → system submits automatically; if "Нет" → submission cancelled
  7. Application status transitions: Черновик → Подписано → Ожидает открытия → Отправляется → Отправлено
  8. If submission fails, the application enters Ошибка status with the raw portal error message; the durable ARQ job retries for up to 30 minutes before marking final failure; signed XML is retained for manual download
  9. User can view the full history of all submitted applications with their current statuses
**Plans**: 5 plans
- [x] 05-01-PLAN.md — Wave 1: migration 0004 + applications table + GoszakupPortalClient (login/submit) + Redis session/confirm helpers + application state machine + CRUD endpoints
- [x] 05-02-PLAN.md — Wave 1: useNCALayer() dual-mode hook + signing UI (status/cert/install) + Gamma-encryption (step 7) investigation
- [x] 05-03-PLAN.md — Wave 2: portal proxy steps 1-11 + /api/goszakup/* endpoints + application wizard (lot price → documents → NCALayer signing)
- [x] 05-04-PLAN.md — Wave 2: python-telegram-bot + ARQ worker (poll_watchlist cron + auto_submit) + Telegram webhook + 15-min confirm fallback
- [x] 05-05-PLAN.md — Wave 3: applications list + detail (30s polling) + status badges + error surface + Sidebar nav
**UI hint**: yes

### Phase 6: Notifications
**Goal**: Users can connect Telegram and WhatsApp to receive tender-status notifications and manage their watchlist from a settings page.
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: NOTIF-04, NOTIF-05, NOTIF-06
**Success Criteria** (what must be TRUE):
  1. User can connect their Telegram account by sending `/start` to the TenderIt bot; account link is stored and used for all tender-status notifications (tender opened alerts + submission confirmations)
  2. User can connect WhatsApp via Twilio and receive the same tender-status notifications
  3. User can view their watchlist in settings — see each tracked tender with its current status, and enable/disable/remove entries
**Plans**: TBD
**UI hint**: yes

### Phase 7: Discovery & Matching
**Goal**: Users can configure keyword/region/category filters; the system periodically fetches new tenders from goszakup, matches them against each user's filters, and notifies via the existing Telegram bot — user clicks "Участвуем" to enter the Phase 5 submission pipeline.
**Mode:** mvp
**Depends on**: Phase 2, Phase 5 (application_service); Phase 6 (telegram_chat_id for notifications — Telegram module built but inactive until Phase 6 provides /start linkage)
**Parallel with**: Phase 6 (independent backend workstream)
**Requirements**: DISC-01, DISC-02, DISC-03, DISC-04, DISC-05, DISC-06
**Success Criteria** (what must be TRUE):
  1. User can create and update filter rules (keywords, СПГЗ codes, region, min/max amount) via UI
  2. ARQ worker polls goszakup batch API every 15 minutes and upserts new/changed tenders to local DB
  3. Matching worker runs after each poll and creates tender_match records for each user whose filters hit a new tender
  4. User sees a "Подборка" feed of matched tenders with status (новый / пропущен / участвуем)
  5. When Phase 6 telegram_chat_id is available, user receives Telegram card per match with "Участвуем / Пропустить" buttons; "Участвуем" calls application_service.create() entering the Phase 5 pipeline
  6. Sidebar shows a link to the Telegram bot (t.me/<botname>)
**Plans**: 6 plans
- [x] 07-01-PLAN.md — Wave 1: migrations 0005-0007 + extend Tender model + ClientFilter + TenderMatch ORM models + Pydantic schemas
- [x] 07-02-PLAN.md — Wave 1: goszakup batch fetch (fetch_tenders_batch) + poll_goszakup_discovery ARQ cron task
- [x] 07-03-PLAN.md — Wave 2: matching_service + run_matching ARQ task + worker_settings extension + discovery CRUD router + main.py
- [x] 07-04-PLAN.md — Wave 2: create_discovery_draft + send_discovery_notification + disc:* Telegram webhook handlers
- [x] 07-05-PLAN.md — Wave 3: /discovery feed + /discovery-filters form + TenderMatchCard + StatusBadge + Sidebar + middleware
- [x] 07-06-PLAN.md — Wave 4: human verification checkpoint
**UI hint**: yes

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Spikes & Foundation | 5/5 | Complete   | 2026-05-28 |
| 2. Auth & Company Profile | 0/5 | Not started | - |
| 3. Tender Lookup | 0/4 | Planned | - |
| 4. Document Vault | 0/3 | Planned | - |
| 5. EDS Signing & Submission | 3/5 | In Progress|  |
| 6. Notifications | 0/0 | Not started | - |
| 7. Discovery & Matching | 0/6 | Planned | - |

---

## Coverage Validation

| REQ-ID | Phase | Notes |
|--------|-------|-------|
| SPIKE-01 | Phase 1 | ✅ Resolved |
| SPIKE-02 | Phase 1 | ✅ Resolved |
| SPIKE-03 | Phase 1 | Pending |
| SPIKE-05 | Phase 1 | Pending |
| AUTH-01 | Phase 2 | |
| AUTH-02 | Phase 2 | |
| AUTH-03 | Phase 2 | |
| AUTH-04 | Phase 2 | |
| COMP-01 | Phase 2 | |
| COMP-02 | Phase 2 | |
| SRCH-01 | Phase 3 | Lookup by tenderID |
| SRCH-02 | Phase 3 | Unified Services API |
| SRCH-03 | Phase 3 | |
| SRCH-04 | Phase 3 | Watchlist |
| DOCS-01 | Phase 4 | Upload + MinIO + pre-signed URL |
| DOCS-02 | Phase 4 | 5 категорий |
| DOCS-03 | Phase 4 | expiry_status + badges |
| DOCS-04 | Phase 4 | Delete (MinIO + БД) |
| DOCS-05 | Phase 4 | GET /attachable |
| SIGN-01 | Phase 5 | |
| SIGN-02 | Phase 5 | |
| SIGN-03 | Phase 5 | |
| SIGN-04 | Phase 5 | |
| SIGN-05 | Phase 5 | |
| APPL-01 | Phase 5 | Complete |
| APPL-02 | Phase 5 | Complete |
| APPL-03 | Phase 5 | Complete |
| APPL-04 | Phase 5 | Complete |
| APPL-05 | Phase 5 | Complete |
| APPL-06 | Phase 5 | Complete |
| APPL-07 | Phase 5 | Complete |
| APPL-08 | Phase 5 | Complete |
| APPL-09 | Phase 5 | Complete |
| NOTIF-04 | Phase 6 | Telegram connect |
| NOTIF-05 | Phase 6 | WhatsApp connect |
| NOTIF-06 | Phase 6 | Watchlist mgmt |
| DISC-01 | Phase 7 | client_filters CRUD (07-01, 07-03) |
| DISC-02 | Phase 7 | ARQ batch poll 15min (07-02, 07-03) |
| DISC-03 | Phase 7 | run_matching + matching_service (07-03) |
| DISC-04 | Phase 7 | /discovery feed + TenderMatchCard (07-03, 07-05) |
| DISC-05 | Phase 7 | Telegram disc:* + create_discovery_draft (07-04) |
| DISC-06 | Phase 7 | Sidebar Telegram bot link (07-05) |

**Total mapped: 42/42**
*(SPIKE-04, SRCH-05/06/07, NOTIF-01/02/03 → moved to v2)*

*Traceability updated 2026-07-19 — Phase 7 Discovery & Matching planned (6 plans, 4 waves)*
