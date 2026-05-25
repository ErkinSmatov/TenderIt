# TenderIt — Project Guide

## Repository Structure

```
TenderIt/                    ← root (this repo) — planning docs only
├── .planning/               ← GSD planning artifacts (PROJECT.md, ROADMAP.md, etc.)
├── frontend/                ← Next.js 14 app (SEPARATE git repo)
└── backend/                 ← FastAPI app (SEPARATE git repo)
```

**IMPORTANT:** `frontend/` and `backend/` are separate git repositories. When committing code:
- Frontend code → commit inside `frontend/` directory
- Backend code → commit inside `backend/` directory
- Planning docs → commit in the root `TenderIt/` repository

## Project Context

**Product:** TenderIt — Kazakhstan e-procurement tender aggregator with NCALayer ЭЦП signing
**Core value:** Submit a tender application in 3 clicks: find → sign with ЭЦП → auto-submit

**Target user:** Director / sole proprietor of a Kazakhstani SMB handling procurement themselves

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Backend | FastAPI (Python 3.12), SQLAlchemy 2.x async |
| Database | PostgreSQL 16 |
| Cache / Queue | Redis + ARQ (async task queue) |
| File Storage | MinIO (S3-compatible) |
| EDS Signing | NCALayer WebSocket (ws://localhost:14579) — browser-only, NEVER server-side |
| Notifications | python-telegram-bot + Twilio WhatsApp Business API |

## Key Architectural Rules

1. **NCALayer is browser-only.** The backend NEVER connects to ws://localhost:14579. All signing happens in the browser via a `useNCALayer()` React hook. The backend only receives and verifies the signed XML blob.

2. **Private keys never leave the user's device.** No .p12 file uploads to server.

3. **Kazakhstan data localization.** PII (ИИН, БИН, passport data) must be hosted on Kazakhstan infrastructure.

4. **Tender data from official APIs.** goszakup.gov.kz GraphQL API + MP.kz (verify API vs scraping in Phase 1 spike).

5. **Durable submission queue.** Tender submissions go through ARQ jobs with retry — never synchronous HTTP from a request handler.

## Phase Roadmap Summary

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Spikes & Foundation (verify goszakup API, NCALayer protocol, submission payload, MP.kz API, legal) | Not started |
| 2 | Auth & Company Profile (JWT auth, BIN/address profile) | Not started |
| 3 | Tender Data Pipeline (ARQ sync workers, search, filters) | Not started |
| 4 | Document Vault (MinIO storage, expiry tracking, auto-attach) | Not started |
| 5 | EDS Signing & Submission (NCALayer integration, application state machine) | Not started |
| 6 | Notifications (Telegram bot, WhatsApp via Twilio) | Not started |

## Planning Docs

- [PROJECT.md](.planning/PROJECT.md) — context, goals, decisions
- [REQUIREMENTS.md](.planning/REQUIREMENTS.md) — 39 v1 requirements with REQ-IDs
- [ROADMAP.md](.planning/ROADMAP.md) — 6-phase execution plan
- [research/SUMMARY.md](.planning/research/SUMMARY.md) — domain research synthesis

## GSD Workflow

Run `/gsd-plan-phase 1` to start planning Phase 1.
Run `/gsd-execute-phase 1` to execute a planned phase.
Run `/gsd-progress` to check current status.
