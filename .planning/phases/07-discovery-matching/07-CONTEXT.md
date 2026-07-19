# Phase 7 — Discovery & Matching: Context

**Created:** 2026-07-19
**Status:** Ready for planning
**Source:** Product discussion (2026-07-19) — decisions captured from PHASE-3-DISCOVERY-MATCHING.md + user clarifications

---

<domain>
## Phase Boundary

Phase 7 adds proactive tender discovery on top of the existing reactive lookup-by-ID (Phase 3). Users configure filters; the system runs background polling workers to fetch tenders in bulk from goszakup, matches them against each user's filters, shows a discovery feed, and sends Telegram notifications with one-click application entry.

This phase is designed to be executed by a parallel team alongside Phase 6. It DOES NOT block on Phase 6 being complete — the Telegram notification module is built but only activates once Phase 6 provides `telegram_chat_id` via the `/start` handler (NOTIF-04).

**Out of scope for this phase:**
- zakup.sk.kz (deferred to v2 per explicit product decision)
- Profitability calculation (deferred — formula not defined yet)
- WhatsApp notifications for discovery matches (Phase 6 covers Twilio; this phase wires Telegram only)
</domain>

<decisions>
## Implementation Decisions

### D-01: No zakup.sk.kz
**LOCKED.** Only goszakup.gov.kz. The sk.kz source is v2. Do not add `source='sk_kz'` columns, workers, or routing — adding them now would require legal review (SPIKE-05 level strictness) before any code is written.

### D-02: No profitability calculation
**LOCKED.** `profitability_service.py` is NOT part of this phase. The formula is undefined. `tender_match` records do NOT have a `profitability` column. The Telegram card and the UI feed show amount/deadline/region but NOT a margin estimate.

### D-03: Telegram notifications depend on Phase 6
**LOCKED.** `telegram_chat_id` for a user is stored by the Phase 6 `/start` handler (NOTIF-04). The Phase 7 notification service MUST read this field to send messages. Build the notification service in full, but guard every send call with `if user.telegram_chat_id is None: skip`. The Telegram callback handlers (Участвуем/Пропустить) are also built here — they plug into the same bot as Phase 5's confirm flow (DO NOT create a second bot).

### D-04: Telegram callback_data prefixes
**LOCKED.** Phase 5-04 uses `confirm:` prefix for confirm/deny application submission. This phase MUST use `disc:` prefix for Участвуем/Пропустить callbacks to avoid collision. Format: `disc:participate:{match_id}` and `disc:skip:{match_id}`.

### D-05: "Участвуем" calls existing application_service
**LOCKED.** The Telegram handler for "Участвуем" MUST call `application_service.create(user_id, tender_id)` — no separate state machine, no bridge table. The application enters the Phase 5 pipeline exactly as if the user created it manually.

### D-06: ARQ worker cadence — 15 minutes
**LOCKED.** The goszakup batch polling worker (`poll_goszakup_discovery`) runs every 15 minutes via ARQ cron. Conservative rate — goszakup has no public SLA. Use `date_last_changed` or equivalent to fetch only new/updated records since last run.

### D-07: Matching worker is a separate ARQ task
**LOCKED.** After the poll worker upserts tenders, it enqueues a `run_matching` ARQ task. `run_matching` loads all active `client_filters`, finds tenders inserted/updated in the last poll window, applies rule-based matching (keywords AND/OR, region, СПГЗ codes, amount range), and creates `tender_match` records (status=`matched`). Keep matching logic in `services/matching_service.py` — testable in isolation with mocked data.

### D-08: Sidebar Telegram bot link
**LOCKED.** Add a static link in `Sidebar.tsx` pointing to `t.me/<botname>` (use `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME` env var). Renders as "Telegram бот" entry below "Заявки". Does NOT require auth — opens in a new tab.

### D-09: No new Telegram bot
**LOCKED.** There is ONE bot for the whole product. Phase 5-04 already registers the webhook at `/api/telegram/webhook`. Phase 7 extends the same webhook router with `disc:*` callback handlers. Do NOT create a separate bot token, a separate webhook, or a separate router file.

### D-10: client_filters CRUD — per-user, one active set
**LOCKED.** v1: one filter set per user (upsert semantics — PUT replaces the entire filter). No named presets, no multiple sets. Frontend: a single settings page with keyword/region/СПГЗ/amount fields that saves on submit.

### D-11: tender_matches status machine
**LOCKED.** `matched` → `notified` → (`skipped` | `participating`). `UNIQUE(user_id, tender_id)` constraint. No re-notification for an already-notified match. A tender removed from goszakup does not delete the match record — it stays in final status.

### D-12: Discovery feed page — /discovery
**LOCKED.** New page at `/discovery` in the dashboard layout. Shows tender_match records for the logged-in user, newest first, with TenderMatchCard component showing: tender title, customer, amount, deadline, region, source badge (goszakup), status badge (Новый/Уведомлён/Участвуем/Пропущен). "Участвуем" button on a Новый/Уведомлён card triggers immediate application creation (same call as Telegram handler). "Пропустить" sets status=skipped.

### Claude's Discretion
- Exact GraphQL/REST query for batch goszakup fetch (fields to request, pagination strategy) — researcher to determine from existing `goszakup_service.py` patterns
- Index strategy for `client_filters` keyword matching (ILIKE vs. pg_trgm vs. full-text) — researcher to recommend based on expected data volume
- UI component library choices for DiscoveryFeed — follow existing patterns in `frontend/src/components/`
- ARQ retry/backoff config for poll worker — follow existing pattern in `auto_submit.py`
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing codebase to extend (DO NOT duplicate)
- `backend/app/workers/tasks/poll_watchlist.py` — ARQ cron pattern to mirror for the new discovery poll worker
- `backend/app/workers/tasks/auto_submit.py` — ARQ retry/backoff pattern
- `backend/app/routers/telegram_webhook.py` — existing webhook router to EXTEND with `disc:*` handlers (DO NOT create a new router file)
- `backend/app/services/telegram_service.py` — existing send helper to extend with discovery notification message builder
- `backend/app/services/application_service.py` — `create()` method that Phase 7 "Участвуем" handler must call
- `backend/app/services/goszakup_service.py` — existing goszakup client; extend for batch fetch, do not rewrite

### Data model neighbours (READ before writing migrations)
- `backend/app/models/tender.py` — existing tenders table; Phase 7 may add columns, must not drop or rename existing ones
- `backend/app/models/user_watchlist.py` — existing watchlist; Phase 7 does NOT touch watchlist logic
- `backend/app/models/application.py` — read to understand `application_service.create()` signature

### Planning context
- `backend/PHASE-3-DISCOVERY-MATCHING.md` — full feature specification document
- `.planning/REQUIREMENTS.md` — DISC-01 through DISC-06 are the v1 requirement IDs for this phase
- `.planning/phases/05-eds-signing-submission/05-CONTEXT.md` — Phase 5 decisions (confirm flow, ARQ patterns, Telegram callback prefix `confirm:`)

### Frontend patterns
- `frontend/src/app/(dashboard)/applications/page.tsx` — list page pattern (useQuery, empty state, error alert)
- `frontend/src/components/layout/Sidebar.tsx` — nav structure to extend with /discovery link + Telegram bot link
- `frontend/src/components/applications/ApplicationStatusBadge.tsx` — status badge pattern to replicate for TenderMatchStatusBadge
</canonical_refs>

<specifics>
## Specific Ideas

- **Batch goszakup fetch**: Use `date_last_changed` filter on the Unified Services API to avoid full re-fetch every 15 min. Store `last_polled_at` in a `worker_state` Redis key.
- **Matching keywords**: Simple ILIKE `%keyword%` per keyword, OR-joined. СПГЗ code = exact match on `spgz_code` column. Region = exact match. Amount = between `min_amount` and `max_amount` (NULL = no bound).
- **Discovery page URL**: `/discovery` (add to middleware `protectedRoutes`)
- **Telegram bot username**: env var `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME` for the sidebar link
- **No bulk notification**: one Telegram message per match, sent immediately after `run_matching` creates the record. If user has no telegram_chat_id, skip silently and leave match in `matched` status (no `notified` transition).
</specifics>

<deferred>
## Deferred Ideas

- **zakup.sk.kz** — explicitly deferred to v2 (legal review required before any implementation)
- **Profitability calculation** — deferred (formula not defined)
- **WhatsApp notifications for discovery** — covered by Phase 6 Twilio setup, not this phase
- **Named filter presets / multiple filter sets** — v2 (v1 = one set per user, upsert)
- **Keyword subscription email digest** — v2 (NOTIF-01/02/03 are already v2)
- **MP.kz as second source** — SPIKE-04 pending, deferred to v2
</deferred>

---

*Phase: 07-discovery-matching*
*Context gathered: 2026-07-19 from product discussion + PHASE-3-DISCOVERY-MATCHING.md*
