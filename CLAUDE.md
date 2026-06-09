# TenderIt — Project Guide

## Working Principles

- **Не соглашайся автоматически.** Если предложение пользователя неоптимально — скажи об этом прямо и предложи лучший вариант с обоснованием. Цель — качественный результат, а не одобрение.

## Repository Structure

**Монорепо** — один git-репозиторий, всё в одном месте:

```
TenderIt/                    ← единственный git repo
├── .planning/               ← GSD: PROJECT.md, ROADMAP.md, REQUIREMENTS.md, research/
├── frontend/                ← Next.js 14 (App Router)
├── backend/                 ← FastAPI (Python 3.12)
├── CLAUDE.md                ← этот файл
└── .gitignore
```

Все коммиты — в один репозиторий. GSD-агенты могут видеть и frontend, и backend одновременно и запускать задачи параллельно.

## Project Context

**Product:** TenderIt — Kazakhstan e-procurement tender submission tool with NCALayer ЭЦП signing
**Core value:** Paste tender ID → sign documents with ЭЦП in advance → system auto-submits the moment the tender opens (notify + confirm flow)

**Target user:** Director / sole proprietor of a Kazakhstani SMB handling procurement themselves

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Backend | FastAPI (Python 3.12), SQLAlchemy 2.x async |
| Database | PostgreSQL 16 |
| Cache / Queue | Redis + ARQ (async task queue) |
| File Storage | MinIO (S3-compatible) |
| EDS Signing | NCALayer WebSocket (wss://127.0.0.1:13579) — browser-only, NEVER server-side. **Dual-mode:** 1.x (macOS) → `commonUtils` + array args; 2.x (Windows) → `basics` + object args. Version auto-detected on connect. |
| Notifications | python-telegram-bot + Twilio WhatsApp Business API |

## Key Architectural Rules

1. **NCALayer is browser-only.** The backend NEVER connects to NCALayer. All signing happens in the browser via a `useNCALayer()` React hook. The backend only receives and verifies the signed XML blob.
   - **Confirmed endpoint:** `wss://127.0.0.1:13579` (SPIKE-02, 2026-05-28)
   - **Port 14579** in old docs is incorrect — confirmed port is **13579**
   - **Dual-mode dispatch** (version auto-detected from broadcast on connect):
     - NCALayer ≥ 2.0 (Windows): module `kz.gov.pki.knca.basics`, named object args, `xmlToSign` = base64-encoded; signed result in `response.result`
     - NCALayer 1.x (macOS): module `kz.gov.pki.knca.commonUtils`, positional array args, `xmlToSign` = **raw XML string** (NOT base64 — SAX parser receives it directly); signed result in **`response.responseObject`** as plain XMLDSig string
   - **No minimum version requirement.** NCALayer 1.4 (macOS) fully confirmed: `getKeyInfo` ✅ `signXml` ✅ (2026-05-28)

2. **Private keys never leave the user's device.** No .p12 file uploads to server.

3. **Kazakhstan data localization.** PII (ИИН, БИН, passport data) must be hosted on Kazakhstan infrastructure.

4. **Tender data from official API.** goszakup.gov.kz **Unified Services (Унифицированные сервисы) REST API** — token obtained 2026-06-09. Lookup by tenderID on demand; no bulk sync. MP.kz deferred to v2.

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

```bash
/gsd-plan-phase 1      # спланировать фазу
/gsd-execute-phase 1   # выполнить (запускает frontend + backend агентов параллельно)
/gsd-progress          # статус проекта
```
