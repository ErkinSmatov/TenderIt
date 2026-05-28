# TenderIt — Roadmap

## Project

**Core value:** Подача тендерной заявки за 3 клика: нашли → подписали ЭЦП → отправлено автоматически.
**Platforms v1:** goszakup.gov.kz + MP.kz
**Stack:** Next.js 14 + FastAPI + PostgreSQL 16 + Redis + ARQ + MinIO

---

## Phases

- [x] **Phase 1: Spikes & Foundation** — Resolve all critical unknowns and stand up the project skeleton (completed 2026-05-28)
- [ ] **Phase 2: Auth & Company Profile** — Users can register, log in, and maintain a verified company identity
- [ ] **Phase 3: Tender Data Pipeline** — Users can search and browse aggregated tenders from both portals
- [ ] **Phase 4: Document Vault** — Users can store, categorise, and track expiry of company documents
- [ ] **Phase 5: EDS Signing & Submission** — Users can sign and submit applications via NCALayer
- [ ] **Phase 6: Notifications** — Users receive Telegram and WhatsApp alerts for matching new tenders

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
- [ ] 02-01-PLAN.md — Wave 0 foundation: settings, deps, models, migration, BIN validator, test scaffolding
- [ ] 02-02-PLAN.md — Wave 1 vertical slice: registration + login + middleware + dashboard placeholder
- [ ] 02-03-PLAN.md — Wave 2: refresh token rotation + logout
- [ ] 02-04-PLAN.md — Wave 3: password reset (forgot + reset endpoints + pages)
- [ ] 02-05-PLAN.md — Wave 4: company profile GET/PUT + profile page + form
**UI hint**: yes

### Phase 3: Tender Data Pipeline
**Goal**: Users can search, filter, and browse aggregated tenders sourced from both goszakup and MP.kz via background sync workers running on schedule.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05, SRCH-06, SRCH-07
**Success Criteria** (what must be TRUE):
  1. ARQ sync workers run on schedule (goszakup every 15 min, MP.kz every 30 min) and upsert tenders into the unified `tenders` table without duplicates
  2. User can search tenders by keyword and see relevant results from both portals on a single feed
  3. User can filter the tender feed by contract amount range, deadline (days remaining), and region and the list updates accordingly
  4. Each tender in the list displays: title, contract amount, source portal, submission deadline, and region in a readable card
**Plans**: TBD
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
**Plans**: TBD
**UI hint**: yes

### Phase 5: EDS Signing & Submission
**Goal**: Users can create an application draft, review attached documents, sign the payload via NCALayer, and have the system automatically submit it to the portal with durable retry and full status tracking.
**Mode:** mvp
**Depends on**: Phase 3, Phase 4
**Requirements**: SIGN-01, SIGN-02, SIGN-03, SIGN-04, SIGN-05, APPL-01, APPL-02, APPL-03, APPL-04, APPL-05, APPL-06
**Success Criteria** (what must be TRUE):
  1. On any signing page, the UI shows a real-time NCALayer connectivity status indicator (green/red); the Sign button is disabled when NCALayer is unreachable, and an installation guide is shown if it is not running
  2. Before signing, user can see the EDS certificate owner name and expiry date; a persistent warning appears if the certificate expires within 30 days
  3. User can create an application draft for a selected tender, review the list of documents that will be included, enter their NCALayer PIN, and complete signing — receiving the signed XML back from NCALayer within the same page flow
  4. After signing, the system automatically submits the application to the portal via API, and the application status transitions through: Черновик → Подписано → Отправляется → Отправлено
  5. If submission fails, the application enters Ошибка status with the raw portal error message displayed in the UI, and the signed XML is retained for manual download; the durable ARQ job retries for up to 30 minutes before marking final failure
  6. User can view the full history of all submitted applications with their current statuses
**Plans**: TBD
**UI hint**: yes

### Phase 6: Notifications
**Goal**: Users can subscribe to search-based tender alerts and receive timely notifications via Telegram and WhatsApp when new matching tenders appear.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: NOTIF-01, NOTIF-02, NOTIF-03, NOTIF-04, NOTIF-05
**Success Criteria** (what must be TRUE):
  1. User can save their current search filters as a named notification subscription from the tender search UI
  2. User can connect their Telegram account by sending `/start` to the TenderIt bot; new tenders matching their subscription arrive as Telegram messages within 5 minutes of the ARQ dispatcher run
  3. User can connect WhatsApp via Twilio and receive the same subscription alerts as a WhatsApp message
  4. User can view, enable/disable, and delete their notification subscriptions from a settings page
**Plans**: TBD
**UI hint**: yes

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Spikes & Foundation | 5/5 | Complete   | 2026-05-28 |
| 2. Auth & Company Profile | 0/5 | Not started | - |
| 3. Tender Data Pipeline | 0/0 | Not started | - |
| 4. Document Vault | 0/0 | Not started | - |
| 5. EDS Signing & Submission | 0/0 | Not started | - |
| 6. Notifications | 0/0 | Not started | - |

---

## Coverage Validation

| REQ-ID | Phase |
|--------|-------|
| SPIKE-01 | Phase 1 |
| SPIKE-02 | Phase 1 |
| SPIKE-03 | Phase 1 |
| SPIKE-04 | Phase 1 |
| SPIKE-05 | Phase 1 |
| AUTH-01 | Phase 2 |
| AUTH-02 | Phase 2 |
| AUTH-03 | Phase 2 |
| AUTH-04 | Phase 2 |
| COMP-01 | Phase 2 |
| COMP-02 | Phase 2 |
| SRCH-01 | Phase 3 |
| SRCH-02 | Phase 3 |
| SRCH-03 | Phase 3 |
| SRCH-04 | Phase 3 |
| SRCH-05 | Phase 3 |
| SRCH-06 | Phase 3 |
| SRCH-07 | Phase 3 |
| DOCS-01 | Phase 4 |
| DOCS-02 | Phase 4 |
| DOCS-03 | Phase 4 |
| DOCS-04 | Phase 4 |
| DOCS-05 | Phase 4 |
| SIGN-01 | Phase 5 |
| SIGN-02 | Phase 5 |
| SIGN-03 | Phase 5 |
| SIGN-04 | Phase 5 |
| SIGN-05 | Phase 5 |
| APPL-01 | Phase 5 |
| APPL-02 | Phase 5 |
| APPL-03 | Phase 5 |
| APPL-04 | Phase 5 |
| APPL-05 | Phase 5 |
| APPL-06 | Phase 5 |
| NOTIF-01 | Phase 6 |
| NOTIF-02 | Phase 6 |
| NOTIF-03 | Phase 6 |
| NOTIF-04 | Phase 6 |
| NOTIF-05 | Phase 6 |

**Total mapped: 39/39**
