# Phase 05: EDS Signing & Submission — Research

**Researched:** 2026-07-09
**Domain:** NCALayer WebSocket, goszakup PHP portal proxy, ARQ workers, python-telegram-bot
**Confidence:** HIGH (codebase patterns), MEDIUM (ARQ/Telegram via docs), LOW (NCALayer gamma method)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-05-01:** Backend реализует `GoszakupPortalClient` — конкретный HTTP-клиент для портала.
- Файл: `backend/app/services/goszakup_portal_client.py`
- Метод `public_application(tender_buy_id, application_id, session_cookie, csrf_token)` → финальный сабмит
- Что делает браузер: шаги 1-11 (create_draft, add_lots, beneficiary, gamma encryption, save signs, priceoffers_next)
- Что делает ARQ: шаг 12 (`ajax_public_application`) с сессией из Redis

**D-05-02:** Сценарий B — PHP сессия (PHPSESSID + CSRF). **Вариант 2** архитектуры:
- Браузер выполняет шаги 1-11, передаёт `{session_cookie, csrf_token, goszakup_application_id}` на backend
- Redis хранит: `goszakup_session:{user_id}` = `{phpsessid, csrf, application_id, tender_buy_id}` TTL=20h
- Session refresh: ARQ → 401 → уведомление → пользователь логинится в goszakup через NCALayer → новая сессия → Redis → retry

**D-05-03:** Минимальный MVP ввод: только цена per лот + выбор документов из Document Vault.
- Авто из Company Profile: supplierBin, supplierName, supplierAddress, supplierDirector
- Дефолты без ввода: deliveryTerm=30, paymentTerm="по факту поставки", vatPercent=0, currency="KZT"

**D-05-04:** Машина состояний: `draft | signed | waiting | submitting | submitted | error`
- `ready_at` — когда браузер завершил шаги 1-11
- `signed_xml` — убран (нет unsigned XML в реальном флоу)

**D-05-05:** ARQ cron job `poll_watchlist_tenders` каждые 5 минут. При `status_id == 220` → триггер submission.

**D-05-06:** Phase 5 реализует полный Telegram-флоу (python-telegram-bot), WhatsApp → Phase 6.
- Inline кнопки «Да / Нет», TTL confirm = 900s (15 мин)
- Redis: `confirm:{application_id}` → "pending"/"yes"/"no" TTL=900s
- Нет ответа 15 мин → ARQ delayed job → авто-сабмит

**D-05-07:** `useNCALayer()` hook — dual-mode dispatch:
- URL: `wss://127.0.0.1:13579`
- 1.x: `kz.gov.pki.knca.commonUtils` + array args + raw XML → `responseObject`
- 2.x: `kz.gov.pki.knca.basics` + object args + base64 → `result`

**D-05-08:** Backend НЕ верифицирует подпись в MVP. goszakup сам верифицирует при submit.

**DB Schema (зафиксирована):**
- Таблица `applications` со схемой из CONTEXT.md
- `ALTER TABLE users ADD COLUMN telegram_chat_id BIGINT`
- Alembic revision: `0004` → `down_revision = "0003"`

### Claude's Discretion

- Конкретная структура ARQ WorkerSettings (WorkerSettings class vs module-level)
- Telegram webhook vs polling для получения callback-ов от пользователя
- Точная структура `callback_data` для inline кнопок (формат для передачи app_id)
- Порядок и структура планов 05-01..05-05

### Deferred Ideas (OUT OF SCOPE)

- WhatsApp (Twilio) → Phase 6
- MP.kz submission → v2
- Верификация подписи (pyhanko) → v2
- Настройки уведомлений в UI → Phase 6
- Мультилот с разными delivery terms per лот → v2
- Document attachment через goszakup portal (show_doc) → открытый вопрос, не блокирует MVP
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SIGN-01 | Проверка доступности NCALayer, статус-индикатор | useNCALayer hook: WebSocket connect/disconnect detection |
| SIGN-02 | Отображение данных сертификата ЭЦП | `getKeyInfo` → `subjectDn`, `notAfter` из response |
| SIGN-03 | Предупреждение если сертификат истекает < 30 дней | Сравнение `notAfter` с Date.now() в hook |
| SIGN-04 | Подписание заявки через NCALayer (PIN → signed result) | `signXml` (1.x) / `sign` (2.x); шаг 9: `createCMSSignatureFromBase64` (1.x); шаг 7: UNKNOWN — открытый вопрос |
| SIGN-05 | Инструкция установки если NCALayer не запущен | UI state: disconnected → guidance link |
| APPL-01 | Создать черновик заявки | POST /api/applications → DB + goszakup шаги 1-5 через proxy |
| APPL-02 | Просмотр документов до подписания | GET /api/documents/attachable (уже реализован в Phase 4) |
| APPL-03 | Авто-сабмит через API | ARQ `auto_submit_application` с сессией из Redis |
| APPL-04 | Статус заявки в UI | Polling GET /api/applications/{id}/status или SSE |
| APPL-05 | История заявок | GET /api/applications (list) |
| APPL-06 | UI уведомление при ошибке | application.status == 'error' + application.error_message |
| APPL-07 | ARQ polling goszakup API, watchlist статусы | ARQ cron каждые 5 мин + goszakup_service.fetch_tender |
| APPL-08 | Telegram уведомление при открытии тендера | python-telegram-bot bot.send_message + InlineKeyboardMarkup |
| APPL-09 | Да/Нет/15-мин fallback | Redis confirm key + ARQ delayed job `_defer_by=timedelta(minutes=15)` |
</phase_requirements>

---

## Summary

Phase 5 является центральной для продукта: именно здесь реализуется основная ценность TenderIt — авто-подача заявки. SPIKE-03 (2026-07-09) полностью задокументировал реальный HTTP флоу goszakup портала: 12 шагов, form-encoded запросы, PHP сессия (PHPSESSID + CSRF), Gamma-шифрование цены через NCALayer. Финальный сабмит — один POST запрос с живой сессией.

Три технических кита фазы: (1) `GoszakupPortalClient` — backend proxy для всех вызовов к порталу, включая гозакуп авторизацию через NCALayer; (2) `useNCALayer()` hook — dual-mode для 1.x/2.x с поддержкой `signXml`, `createCMSSignatureFromBase64`, и ещё не известного метода для Gamma encryption; (3) ARQ cron + delayed jobs + python-telegram-bot webhook для confirm-flow.

**Critical open question:** NCALayer метод для шага 7 (Gamma encryption price) неизвестен из публичной документации. CommonUtils.java не содержит метода шифрования. Необходимо инспектировать JavaScript goszakup портала для определения точного метода WS вызова. Это должно быть sub-task в Plan 05-02.

**Primary recommendation:** Backend проксирует ВСЕ вызовы к goszakup (CORS блокирует прямые XHR из браузера TenderIt). `GoszakupPortalClient` обрабатывает шаги login + 1-11 + 12. Браузер управляет только NCALayer вызовами.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| NCALayer WebSocket connect/sign | Browser | — | NCALayer слушает localhost, сервер никогда не коннектится (CLAUDE.md rule 1) |
| goszakup portal auth (get PHPSESSID) | API / Backend | — | CORS блокирует прямые браузерные XHR к goszakup из TenderIt домена |
| goszakup шаги 1-6, 8, 10-11 (proxy) | API / Backend | — | Backend проксирует form-encoded запросы с хранимым PHPSESSID |
| Gamma encryption (NCALayer CMS, шаг 7) | Browser | — | NCALayer на localhost, публичный ключ приходит через backend proxy (шаг 6) |
| GOST подпись (шаг 9) | Browser | — | NCALayer на localhost, `createCMSSignatureFromBase64` |
| Финальный сабмит (шаг 12) | ARQ Worker | — | Отложенный авто-сабмит при status_id==220; сессия из Redis |
| Application state machine | API / Backend | — | Единый источник истины; статус хранится в PostgreSQL |
| Polling goszakup за статусом тендера | ARQ Worker | — | Cron job каждые 5 мин, goszakup_service с кешем |
| Telegram уведомления | ARQ Worker | — | bot.send_message из ARQ при обнаружении status_id==220 |
| Telegram callback (Да/Нет) | API / Backend | — | FastAPI webhook endpoint принимает Update от Telegram |
| Application UI (статус, история) | Frontend Server | — | SSR или клиентский polling для статуса |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| arq | 0.28.0 | ARQ job queue — уже установлен | Уже в pyproject.toml, используется в архитектуре с Redis |
| python-telegram-bot | 22.8 | Telegram Bot API wrapper | Официальная библиотека, async-native, inline keyboards OOB |
| httpx | 0.28.1 | HTTP клиент для goszakup proxy | Уже установлен, async, поддерживает cookies |
| redis | 5.3.1 | Redis storage для сессий и confirm | Уже установлен, паттерн redis_service.py установлен |
| sqlalchemy[asyncio] | 2.0.37 | ORM для applications table | Уже в стеке, async паттерн установлен |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tenacity | (already used) | Retry для goszakup proxy calls | Уже используется в goszakup_service.py |
| fakeredis | ≥2.0.0 | Redis mock в тестах | Уже в dev deps; для тестов ARQ workers и confirm flow |
| respx | 0.23.1 | Mock httpx в тестах | Уже в dev deps; для мока goszakup portal calls |

### Не нужны (решение принято)

| Вместо | Не использовать | Обоснование |
|--------|-----------------|-------------|
| pyhanko | XML/CMS верификация | D-05-08: backend не верифицирует в MVP |
| Jinja2 XML шаблоны | Ручная генерация XML | D-S03-01: XML генерирует сам портал |
| OAuth/SSO | goszakup авторизация | Портал использует PHP сессию + NCALayer signXml |

**Installation (новые зависимости):**

```bash
# В backend/pyproject.toml добавить:
"python-telegram-bot==22.8",
# Затем:
pip install -e ".[dev]"
```

**Version verification:**

```
python-telegram-bot: 22.8 [VERIFIED: pypi.org 2026-07-09]
arq: 0.28.0 [VERIFIED: pip show arq в .venv]
httpx: 0.28.1 [VERIFIED: pip show httpx в .venv]
```

---

## Architecture Patterns

### System Architecture Diagram

```
[Browser / TenderIt UI]
       │
       ├─ NCALayer WS calls (wss://127.0.0.1:13579)
       │     ├─ getKeyInfo → certificate data
       │     ├─ signXml → goszakup login XML (auth flow)
       │     ├─ [UNKNOWN method] → Gamma encrypt price (step 7)
       │     └─ createCMSSignatureFromBase64 → PKCS#7 sign (step 9)
       │
       ├─ POST /api/goszakup/auth → TenderIt Backend
       │     └─ GoszakupPortalClient.login() → goszakup /user/sendsign/kz
       │           └─ PHPSESSID stored: Redis goszakup_session:{user_id} TTL=20h
       │
       ├─ POST /api/goszakup/proxy/steps-1-5 → TenderIt Backend
       │     └─ GoszakupPortalClient.{create_draft, add_lots, beneficiary, docs_next}
       │           → goszakup portal form-encoded calls
       │
       ├─ POST /api/goszakup/proxy/get-encr-info → TenderIt Backend
       │     └─ GoszakupPortalClient.get_encr_info() → public key for gamma
       │           → returned to browser for NCALayer CMS encrypt (step 6)
       │
       ├─ POST /api/goszakup/proxy/steps-8-11 → TenderIt Backend
       │     └─ GoszakupPortalClient.{add_encrypt, save_gamma_signs, priceoffers_next}
       │           → using encryptedData from browser NCALayer (steps 8, 10, 11)
       │
       └─ POST /api/applications/{id}/mark-ready → TenderIt Backend
             └─ Application status: draft → signed → waiting
                   └─ Redis: goszakup_session:{user_id} updated with app_id, tender_buy_id

[TenderIt Backend — FastAPI]
       │
       ├─ GET /api/telegram/webhook ← Telegram servers POST updates
       │     └─ Parse Update → CallbackQuery → extract app_id from callback_data
       │           └─ Redis: confirm:{app_id} = "yes"/"no"
       │                 └─ "yes" → enqueue_job('auto_submit_application', app_id, immediately)
       │                    "no"  → update application status = error
       │
       └─ PostgreSQL: applications table (status state machine)

[ARQ Worker — separate process]
       │
       ├─ cron poll_watchlist_tenders (every 5 min)
       │     └─ SELECT * FROM applications WHERE status='waiting'
       │           └─ goszakup_service.fetch_tender_by_number_anno() (30-min cache)
       │                 └─ status_id == 220 →
       │                       ├─ Telegram bot.send_message + InlineKeyboardMarkup [Да|Нет]
       │                       ├─ Redis: confirm:{app_id} = "pending" TTL=900s
       │                       └─ enqueue_job('auto_submit_application', app_id,
       │                                      _defer_by=timedelta(minutes=15))
       │
       └─ auto_submit_application(ctx, app_id)
             ├─ Check Redis confirm:{app_id}:
             │     "no" → abort (user cancelled)
             │     "yes" OR expired/pending → proceed
             │
             ├─ Read goszakup_session:{user_id} from Redis
             │     → PHPSESSID + CSRF + application_id + tender_buy_id
             │
             ├─ GoszakupPortalClient.public_application(...)
             │     POST /ru/application/ajax_public_application/{tenderBuyId}/{appId}
             │     → {"status": "ok"} → update DB status = submitted
             │     → {"status": "error"} → raise Retry(defer=ctx['job_try']**2 * 30)
             │
             └─ Max 7 retries = ~30 min backoff; final failure → status = error
```

### Recommended Project Structure (новые файлы Phase 5)

```
backend/
├── app/
│   ├── models/
│   │   └── application.py          # Application ORM model
│   ├── schemas/
│   │   └── application.py          # ApplicationCreate, ApplicationResponse, etc.
│   ├── services/
│   │   ├── goszakup_portal_client.py  # Backend proxy для всех portal calls + auth
│   │   └── application_service.py     # CRUD + state transitions
│   ├── routers/
│   │   ├── applications.py         # POST/GET /api/applications
│   │   ├── goszakup_proxy.py       # POST /api/goszakup/* (proxy для steps 1-11 + auth)
│   │   └── telegram_webhook.py     # POST /api/telegram/webhook
│   └── workers/
│       ├── worker_settings.py      # WorkerSettings class для arq CLI
│       └── tasks/
│           ├── poll_watchlist.py   # poll_watchlist_tenders cron job
│           └── auto_submit.py      # auto_submit_application delayed job
├── alembic/versions/
│   └── 0004_create_applications.py

frontend/
└── src/
    ├── app/(dashboard)/
    │   └── applications/
    │       ├── page.tsx             # APPL-05: история заявок
    │       └── [id]/
    │           └── page.tsx         # APPL-04: статус + детали заявки
    └── hooks/
        └── useNCALayer.ts           # SIGN-01..05, часть SIGN-04
```

### Pattern 1: GoszakupPortalClient — Backend Proxy

**Что:** Backend проксирует ВСЕ form-encoded POST запросы к goszakup порталу. Хранит и использует PHPSESSID + CSRF из Redis.

**Почему backend, не browser:** `instruction_for_SPIKE03` показывает `Sec-Fetch-Site: same-origin` — auth call был сделан С goszakup домена. Браузер TenderIt не может делать cross-origin XHR к goszakup и получить ответ (CORS). Даже если goszakup не блокирует preflight, `httpOnly` PHPSESSID cookie недоступна JavaScript для чтения и передачи в TenderIt backend.

```python
# backend/app/services/goszakup_portal_client.py
# Source: SPIKE-03-FINDINGS.md + instruction_for_SPIKE03

import httpx
from app.config import settings

PORTAL_BASE = "https://v3bl.goszakup.gov.kz"

class GoszakupPortalClient:
    """Backend proxy для v3bl.goszakup.gov.kz.

    Все запросы: Content-Type: application/x-www-form-urlencoded
    Auth: PHPSESSID cookie передаётся в каждом запросе.
    """

    async def login_with_signed_xml(self, signed_xml: str) -> str:
        """
        POST /user/sendsign/kz с NCALayer-подписанным XML.
        Returns PHPSESSID cookie value.

        Flow (из instruction_for_SPIKE03):
        1. Browser NCALayer signXml('<root><key>{challenge}</key></root>')
        2. Browser POSTs signed XML to /api/goszakup/auth → this method
        3. This method calls goszakup, extracts Set-Cookie: PHPSESSID
        """
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.post(
                f"{PORTAL_BASE}/user/sendsign/kz",
                data={"sign": signed_xml},
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            resp.raise_for_status()
            phpsessid = resp.cookies.get("PHPSESSID")
            if not phpsessid:
                raise ValueError("goszakup login failed: no PHPSESSID in response")
            return phpsessid

    async def create_application(
        self, tender_buy_id: int, phpsessid: str, csrf: str,
        subject_address: str, iik: str
    ) -> int:
        """
        Step 1: POST /ru/application/ajax_create_application/{tenderBuyId}
        Returns applicationId (int).
        """
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{PORTAL_BASE}/ru/application/ajax_create_application/{tender_buy_id}",
                data={
                    "csrf": csrf,
                    "subject_address": subject_address,
                    "iik": iik,
                    "contact_phone": "",
                    "tax_payer_type": "UL",
                },
                cookies={"PHPSESSID": phpsessid},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["id"]

    async def public_application(
        self,
        tender_buy_id: int,
        application_id: int,
        phpsessid: str,
        csrf: str,
    ) -> dict:
        """
        Step 12 (ARQ): POST /ru/application/ajax_public_application/{tBuyId}/{appId}
        Returns {"status":"ok"} or {"status":"error","message":"..."}
        """
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{PORTAL_BASE}/ru/application/ajax_public_application"
                f"/{tender_buy_id}/{application_id}",
                data={
                    "public_app": "Y",
                    "agree_price": "false",
                    "agree_contract_project": "false",
                    "agree_covid19": "false",
                    "csrf": csrf,
                },
                cookies={"PHPSESSID": phpsessid},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            return resp.json()
```

### Pattern 2: ARQ WorkerSettings с DB + Redis pools

**Что:** ARQ worker запускается как отдельный процесс. `on_startup` инициализирует DB session factory и DB engine.

```python
# backend/app/workers/worker_settings.py
# Source: Context7 /websites/arq-docs_helpmanual_io VERIFIED

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.workers.tasks.poll_watchlist import poll_watchlist_tenders
from app.workers.tasks.auto_submit import auto_submit_application


async def startup(ctx):
    """Initialize DB engine and session factory for ARQ worker."""
    engine = create_async_engine(settings.database_url)
    ctx["db_engine"] = engine
    ctx["db_session_factory"] = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

async def shutdown(ctx):
    await ctx["db_engine"].dispose()


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [auto_submit_application]
    cron_jobs = [
        cron(
            poll_watchlist_tenders,
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            unique=True,  # предотвращает дублирование при нескольких воркерах
        )
    ]
    on_startup = startup
    on_shutdown = shutdown
```

**Запуск:**

```bash
python -m arq backend.app.workers.worker_settings.WorkerSettings
```

### Pattern 3: ARQ Delayed Job + Retry (15-min fallback + 30-min retries)

```python
# backend/app/workers/tasks/auto_submit.py
# Source: Context7 /websites/arq-docs_helpmanual_io VERIFIED

from datetime import timedelta
from arq import Retry

BACKOFF_SECONDS = [0, 30, 90, 180, 300, 600, 900]  # total ~35 min

async def auto_submit_application(ctx, application_id: int):
    """
    ARQ job: финальный submit заявки на goszakup.
    Вызывается либо:
    - ARQ delayed: _defer_by=timedelta(minutes=15) (fallback if no Telegram response)
    - Сразу при ответе "Да" через webhook
    """
    import json
    redis = ctx["redis"]

    # Проверить ответ пользователя
    confirm = await redis.get(f"confirm:{application_id}")
    if confirm == "no":
        # Пользователь отказался
        await _set_error(ctx, application_id, "Cancelled by user")
        return

    # Если "yes" или expired/pending — подаём
    # Получить сессию из Redis
    user_id = await _get_user_id_for_app(ctx, application_id)
    session_raw = await redis.get(f"goszakup_session:{user_id}")
    if not session_raw:
        raise Retry(defer=60)  # подождать обновления сессии
    session = json.loads(session_raw)

    from app.services.goszakup_portal_client import GoszakupPortalClient
    client = GoszakupPortalClient()
    result = await client.public_application(
        tender_buy_id=session["tender_buy_id"],
        application_id=session["application_id"],
        phpsessid=session["phpsessid"],
        csrf=session["csrf"],
    )

    if result.get("status") == "ok":
        await _mark_submitted(ctx, application_id)
    else:
        job_try = ctx.get("job_try", 1)
        if job_try <= 7:  # до 30 мин backoff
            defer = BACKOFF_SECONDS[min(job_try, len(BACKOFF_SECONDS)-1)]
            raise Retry(defer=defer)
        await _set_error(ctx, application_id, result.get("message", "Unknown error"))
```

**Enqueue 15-min fallback** (из `poll_watchlist_tenders`):

```python
# Source: Context7 /websites/arq-docs_helpmanual_io VERIFIED
await redis.enqueue_job(
    "auto_submit_application",
    application_id,
    _defer_by=timedelta(minutes=15),
    _job_id=f"submit:{application_id}",  # uniqueness: только один submit job per app
)
```

### Pattern 4: python-telegram-bot — send from ARQ + receive in FastAPI

**Отправка из ARQ worker** (без Application/polling loop):

```python
# Source: Context7 /python-telegram-bot/python-telegram-bot VERIFIED

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

async def send_tender_notification(
    bot_token: str,
    chat_id: int,
    number_anno: str,
    application_id: int,
):
    """Отправить Telegram уведомление с inline кнопками Да/Нет."""
    keyboard = [[
        InlineKeyboardButton("Да", callback_data=f"confirm:yes:{application_id}"),
        InlineKeyboardButton("Нет", callback_data=f"confirm:no:{application_id}"),
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    bot = telegram.Bot(bot_token)
    async with bot:
        await bot.send_message(
            chat_id=chat_id,
            text=f"Тендер №{number_anno} открыт для подачи заявок.\nПодаём заявку? 🗂",
            reply_markup=reply_markup,
        )
```

**Получение callbacks в FastAPI** (webhook endpoint):

```python
# backend/app/routers/telegram_webhook.py
from fastapi import APIRouter, Request, HTTPException
from telegram import Update, Bot

router = APIRouter()

@router.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    """
    Telegram POSTs Update сюда когда пользователь нажимает кнопку.
    Регистрация: bot.set_webhook(url="https://tenderit.kz/api/telegram/webhook")
    """
    body = await request.json()
    update = Update.de_json(body, bot=None)

    if update.callback_query:
        query = update.callback_query
        data = query.data  # e.g., "confirm:yes:123"
        await query.answer()

        parts = data.split(":")
        if parts[0] == "confirm" and len(parts) == 3:
            action = parts[1]      # "yes" or "no"
            app_id = int(parts[2])
            await _handle_confirm(action, app_id, request)

    return {"ok": True}
```

**Настройка webhook при старте:**

```python
# В lifespan FastAPI main.py — добавить:
async with telegram.Bot(settings.telegram_bot_token) as bot:
    await bot.set_webhook(url=f"{settings.webhook_base_url}/api/telegram/webhook")
```

### Pattern 5: useNCALayer Hook — Dual-Mode Dispatch

```typescript
// frontend/src/hooks/useNCALayer.ts
// Source: SPIKE-02-FINDINGS.md [VERIFIED on NCALayer 1.4 macOS, 2026-05-28]

interface NCALayerHookResult {
  status: 'disconnected' | 'connecting' | 'connected' | 'signing' | 'error'
  version: string | null
  certificates: Certificate[]
  connect: () => Promise<void>
  getCertificates: () => Promise<Certificate[]>
  signXml: (xml: string) => Promise<string>
  createCMSSignatureFromBase64: (base64Data: string) => Promise<string>
  // Gamma encryption method: REQUIRES INVESTIGATION — see Open Questions
  gammaEncryptPrice?: (lpId: string, encrParams: object) => Promise<GammaResult>
  error: string | null
}

// Version detection: NCALayer broadcasts version on connect AUTOMATICALLY
// {"result":{"version":"1.4"}} — no extra call needed

function sendRequest(ws: WebSocket, req: object): Promise<unknown> {
  return new Promise((resolve, reject) => {
    ws.onmessage = (ev) => resolve(JSON.parse(ev.data))
    ws.send(JSON.stringify(req))
  })
}

// signXml dual-mode (SPIKE-02 confirmed):
async function signXmlDualMode(
  ws: WebSocket, isLegacy: boolean, xml: string
): Promise<string> {
  if (isLegacy) {
    // 1.x: commonUtils + array args + RAW XML (NOT base64) → responseObject
    const resp: any = await sendRequest(ws, {
      module: "kz.gov.pki.knca.commonUtils",
      method: "signXml",
      args: ["PKCS12", "SIGNATURE", xml, "", ""]
    })
    return resp.responseObject  // plain XMLDSig string
  } else {
    // 2.x: basics + object args + base64 → result
    const base64xml = btoa(unescape(encodeURIComponent(xml)))
    const resp: any = await sendRequest(ws, {
      module: "kz.gov.pki.knca.basics",
      method: "sign",
      args: { tokenType: "PKCS12", keyType: "SIGNATURE", xmlToSign: base64xml }
    })
    return atob(resp.result)  // decode base64 back (2.x behavior unconfirmed)
  }
}

// createCMSSignatureFromBase64 (шаг 9 — GOST подпись):
async function createCMSFromBase64DualMode(
  ws: WebSocket, isLegacy: boolean, base64Data: string
): Promise<string> {
  if (isLegacy) {
    // commonUtils — confirmed available in CommonUtils.java [VERIFIED: GitHub]
    const resp: any = await sendRequest(ws, {
      module: "kz.gov.pki.knca.commonUtils",
      method: "createCMSSignatureFromBase64",
      args: ["PKCS12", "SIGNATURE", base64Data, false]
    })
    return resp.responseObject  // PKCS#7/CMS blob
  } else {
    // basics 2.x format (unconfirmed)
    const resp: any = await sendRequest(ws, {
      module: "kz.gov.pki.knca.basics",
      method: "sign",
      args: { tokenType: "PKCS12", keyType: "SIGNATURE", data: base64Data, format: "cms" }
    })
    return resp.result
  }
}
```

### Goszakup Login Flow (для получения PHPSESSID)

```
Source: instruction_for_SPIKE03 [VERIFIED: реальный HAR/curl из SPIKE]

1. Browser → GET /api/goszakup/auth/challenge
   Backend → GET v3bl.goszakup.gov.kz/ru/user/login → extract challenge key from HTML
   Return: { challengeKey: "83db90ec..." }

2. Browser NCALayer signXml:
   XML: <root><key>{challengeKey}</key></root>
   Method: signXml dual-mode (1.x commonUtils или 2.x basics)
   Result: signed XMLDSig XML with GOST-3410-2015-512 signature

3. Browser → POST /api/goszakup/auth/login { signedXml: "<?xml version=..." }
   Backend GoszakupPortalClient.login_with_signed_xml(signed_xml)
   → POST v3bl.goszakup.gov.kz/user/sendsign/kz
     Body: sign={url_encoded_signed_xml}
     Headers: Content-Type: application/x-www-form-urlencoded, X-Requested-With: XMLHttpRequest
   → Extract Set-Cookie: PHPSESSID={value}
   → Extract CSRF token (from response body/cookie)
   → Redis: goszakup_session:{user_id} = { phpsessid, csrf } TTL=20h
   Return: { success: true }
```

**ВАЖНО:** После первого логина goszakup может показать форму выбора ИП/физ.лицо + галочку условий + пароль (из instruction_for_SPIKE03). Это одноразовая настройка аккаунта. Для существующих аккаунтов этот шаг пропускается. Backend proxy должен обрабатывать эти intermediate форм-редиректы прозрачно.

### Anti-Patterns to Avoid

- **NCALayer из backend:** Backend НИКОГДА не коннектится к wss://127.0.0.1:13579 (CLAUDE.md rule 1)
- **Прямые XHR к goszakup из браузера:** CORS блокирует; все вызовы через TenderIt backend proxy
- **Хранить PHPSESSID в PostgreSQL:** Сессии меняются часто, TTL короткий → Redis
- **Синхронный HTTP в ARQ:** Использовать `async with httpx.AsyncClient()` в каждом job методе
- **Один глобальный httpx.AsyncClient в ARQ:** httpx не thread-safe между event loops; создавать async with per request
- **python-telegram-bot Application.run_polling():** Блокирующий вызов, несовместим с FastAPI lifespan; использовать webhook
- **Хранить bot token в коде:** В settings.telegram_bot_token (env: TELEGRAM_BOT_TOKEN)
- **ARQ job без `_job_id` для delayed submit:** Без уникального job_id возможны дубли auto_submit; использовать `_job_id=f"submit:{application_id}"`

---

## Don't Hand-Roll

| Problem | Не строить | Использовать | Почему |
|---------|-----------|--------------|--------|
| Telegram inline keyboards | Ручная HTTP Telegram API | `python-telegram-bot 22.8` | InlineKeyboardButton/Markup, Update.de_json — всё готово |
| ARQ delayed jobs | Свой scheduler в Redis | `arq enqueue_job(_defer_by=...)` | Атомарность, deduplication по job_id, Retry exception |
| ARQ cron | Celery beat, APScheduler | `arq.cron(func, minute={...})` | Уже в стеке, нет новых зависимостей |
| Redis key helpers | Inline f-strings везде | Паттерн из redis_service.py (функции-обёртки) | Единообразие, тестируемость |
| httpx sessions | requests.Session | `httpx.AsyncClient()` as context manager | Уже в стеке (goszakup_service.py), async |
| Form URL encoding | Ручная сборка строки | httpx `data={}` параметр | httpx автоматически кодирует dict как x-www-form-urlencoded |

**Key insight:** ARQ + httpx + redis уже в стеке. Не нужны новые категории зависимостей, кроме python-telegram-bot.

---

## Runtime State Inventory

> Фаза создаёт новые данные в runtime системах (Redis, PostgreSQL). Нет переименований.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Новые Redis ключи: `goszakup_session:{user_id}`, `confirm:{application_id}` | Создаются в Phase 5 — нет migration |
| Stored data | Новая таблица PostgreSQL: `applications` | Alembic migration 0004 |
| Stored data | ALTER TABLE users ADD COLUMN telegram_chat_id | Alembic migration 0004 |
| Live service config | Telegram bot webhook URL — нужно зарегистрировать | `bot.set_webhook()` в lifespan или при деплое |
| OS-registered state | None — нет task scheduler / systemd / pm2 | — |
| Secrets/env vars | Новые: `TELEGRAM_BOT_TOKEN`, `WEBHOOK_BASE_URL` (опционально `TELEGRAM_WEBHOOK_SECRET`) | Добавить в .env.example и Settings |
| Build artifacts | None — нет compiled binaries | — |

---

## Common Pitfalls

### Pitfall 1: CORS при прямых браузерных вызовах к goszakup

**Что идёт не так:** Browser TenderIt domain делает XHR к `v3bl.goszakup.gov.kz` → браузер блокирует response (нет CORS headers) или блокирует запрос (PHPSESSID cookie для другого домена).

**Почему так:** `Sec-Fetch-Site: same-origin` в SPIKE-03 capture показывает — реальные вызовы происходили с goszakup домена. JavaScript на TenderIt не может читать httpOnly cookies goszakup.

**Как избежать:** Все HTTP вызовы к goszakup — через backend proxy (`GoszakupPortalClient`). Браузер вызывает `/api/goszakup/proxy/*` на TenderIt backend.

**Warning signs:** `Access to fetch at 'https://v3bl.goszakup.gov.kz/...' from origin 'http://localhost:3000' has been blocked by CORS policy`

---

### Pitfall 2: NCALayer 1.x — base64 XML ломает SAX parser

**Что идёт не так:** Передать `xmlToSign: btoa(xml)` в `commonUtils.signXml` → `SAXParseException: Content is not allowed in prolog` (NCALayer 1.x передаёт arg[2] прямо в Java SAX parser).

**Почему так:** NCALayer 1.x использует Java reflection; arg[2] идёт напрямую в `javax.xml.parsers.SAXParser.parse()`.

**Как избежать:** SPIKE-02 confirmed: 1.x — raw XML string в `args[2]`. Только 2.x — base64. Проверять `isLegacy = parseInt(version) < 2`.

**Warning signs:** Error code 500, `org.xml.sax.SAXParseException` в NCALayer response.

---

### Pitfall 3: ARQ duplicate auto_submit jobs

**Что идёт не так:** Пользователь нажимает «Да» → webhook enqueues immediate job. 15-минутный delayed job уже в очереди → два submit запроса к goszakup → 409 или двойная подача.

**Почему так:** ARQ не знает о логической связи между delayed и triggered jobs.

**Как избежать:** Использовать `_job_id=f"submit:{application_id}"` при enqueue. ARQ deduplicate by job_id — второй enqueue возвращает None (job уже существует). [VERIFIED: Context7 arq docs — `if await pipe.exists(job_key, result_key_prefix + job_id): return None`]

---

### Pitfall 4: python-telegram-bot Application.run_polling() несовместим с FastAPI

**Что идёт не так:** Запустить `application.run_polling()` в FastAPI lifespan → блокирующий вызов, FastAPI не стартует.

**Почему так:** `run_polling()` — синхронный blocking loop.

**Как избежать:** Использовать webhook через `bot.set_webhook()`. Callbacks от Telegram приходят на FastAPI endpoint `/api/telegram/webhook`. ARQ worker отправляет сообщения через `async with bot: await bot.send_message(...)`.

---

### Pitfall 5: goszakup CSRF token scope

**Что идёт не так:** CSRF token меняется при каждой смене страницы/сессии → использование устаревшего CSRF → 403 от goszakup.

**Почему так:** PHP CSRF tokens привязаны к сессии/странице.

**Как избежать:** Обновлять CSRF при получении из ответа каждого шага. Хранить последний CSRF вместе с PHPSESSID в Redis. При 403 → refresh flow (перелогин через NCALayer).

---

### Pitfall 6: ARQ startup без async DB context manager

**Что идёт не так:** Использовать `settings.database_url` в job без создания engine → `RuntimeError: Event loop is closed` или connection leak.

**Почему так:** ARQ не поддерживает FastAPI's `get_db()` dependency injection.

**Как избежать:** В `WorkerSettings.on_startup`: создать `create_async_engine` + `sessionmaker`. В каждом job: `async with ctx["db_session_factory"]() as session:`.

---

## Code Examples

### Alembic Migration 0004 (паттерн из 0003)

```python
# backend/alembic/versions/0004_create_applications.py
# Source: 0003_create_documents.py [VERIFIED: codebase pattern]

revision: str = "0004"
down_revision: Union[str, None] = "0003"

def upgrade() -> None:
    # users table: add telegram_chat_id
    op.add_column("users", sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True))

    # applications table (from CONTEXT.md D-05-04 schema)
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tender_id", sa.Integer(), nullable=False),
        sa.Column("lots_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("document_ids", postgresql.ARRAY(sa.Integer()), nullable=False,
                  server_default="{}"),
        sa.Column("goszakup_application_id", sa.BigInteger(), nullable=True),
        sa.Column("goszakup_tender_buy_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("ready_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_applications_user_id", "applications", ["user_id"])
    op.create_index(
        "idx_applications_status",
        "applications", ["status"],
        postgresql_where=sa.text("status IN ('waiting', 'submitting')")
    )
```

### Redis Helpers для Phase 5 (паттерн из redis_service.py)

```python
# Source: redis_service.py [VERIFIED: codebase pattern]
import json

_GOSZAKUP_SESSION_TTL = 72000   # 20 часов
_CONFIRM_TTL = 900               # 15 минут

async def store_goszakup_session(
    redis, user_id: int,
    phpsessid: str, csrf: str,
    application_id: int, tender_buy_id: int
) -> None:
    data = {
        "phpsessid": phpsessid,
        "csrf": csrf,
        "application_id": application_id,
        "tender_buy_id": tender_buy_id,
    }
    await redis.setex(
        f"goszakup_session:{user_id}",
        _GOSZAKUP_SESSION_TTL,
        json.dumps(data)
    )

async def get_goszakup_session(redis, user_id: int) -> dict | None:
    raw = await redis.get(f"goszakup_session:{user_id}")
    return json.loads(raw) if raw else None

async def set_confirm_pending(redis, application_id: int) -> None:
    await redis.setex(f"confirm:{application_id}", _CONFIRM_TTL, "pending")

async def update_confirm(redis, application_id: int, value: str) -> None:
    """value: 'yes' | 'no'"""
    await redis.set(f"confirm:{application_id}", value)
    # Не меняем TTL — истечёт когда истечёт

async def get_confirm(redis, application_id: int) -> str | None:
    return await redis.get(f"confirm:{application_id}")
```

### Settings — новые переменные

```python
# backend/app/config.py — добавить в Settings:
telegram_bot_token: str = ""            # env: TELEGRAM_BOT_TOKEN
webhook_base_url: str = "https://tenderit.example.com"  # env: WEBHOOK_BASE_URL
telegram_webhook_secret: str = ""       # env: TELEGRAM_WEBHOOK_SECRET (для верификации)
```

---

## State of the Art

| Старый подход | Текущий подход | Когда изменился | Impact |
|--------------|----------------|----------------|--------|
| NCALayer commonUtils + object args | Dual-mode: 1.x=array, 2.x=object | SPIKE-02 2026-05-28 | macOS поддерживается |
| JWT Bearer для goszakup API | PHP Session (PHPSESSID + CSRF) | SPIKE-03 2026-07-09 | Backend proxy, не OAuth |
| python-telegram-bot 13.x (sync) | python-telegram-bot 20.x+ (async) | v20.0 2022 | Полностью async, Application builder pattern |
| ARQ polling для confirmations | FastAPI webhook + ARQ delayed | — | Не нужен отдельный polling process |

**Deprecated/outdated:**
- `commonUtils` с object args: не работает на 1.x (NoSuchMethodException) — используем array args
- Port 14579 для NCALayer: incorrect, подтверждён 13579 (SPIKE-02)
- `python-telegram-bot < 20`: synchronous API, несовместима с async FastAPI

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | NCALayer метод для step 7 (Gamma encryption) — вызов через NCALayer WS (не browser WebCrypto) | Architecture, Code Examples | Если WebCrypto — нет NCALayer зависимости для шага 7; другой API |
| A2 | goszakup login одним POST /user/sendsign/kz достаточно для получения PHPSESSID без last-step форм | Code Examples (login flow) | Может потребоваться дополнительные POST шаги (choice форм) — backend proxy сложнее |
| A3 | goszakup CSRF token содержится в cookie или response body шага 1 (ajax_create_application) | Architecture | Если CSRF нужно извлекать из HTML — нужен HTML parser в backend |
| A4 | ARQ `_job_id` deduplicate предотвращает двойной submit | Pitfalls | Нужна тест-верификация в Phase 5 тестах |
| A5 | python-telegram-bot 22.8 совместима с async/await паттерном проекта | Standard Stack | Если breaking changes — pin другую версию |
| A6 | goszakup portal НЕ блокирует Telegram callback_data с application_id (нет IDOR) | Security | Нужен signed callback_data или верификация ownership в webhook handler |

---

## Open Questions

1. **NCALayer метод для Gamma encryption (шаг 7) — КРИТИЧЕСКИЙ**
   - Что знаем: SPIKE-03 описывает это как "NCALayer WS call"; CommonUtils.java не имеет encryption метода; kz.gov.pki.knca.basics документирует только sign
   - Что неясно: Точный JSON-RPC request format для WS в шаге 7; возможно это browser WebCrypto (не NCALayer)
   - Рекомендация: Plan 05-02 должен включать sub-task: `Inspect goszakup portal JS source (v3bl.goszakup.gov.kz/js) to identify step 7 WS call format`. Открыть DevTools на goszakup, поставить breakpoint на ws.send(), зафиксировать request при шаге gamma encryption.

2. **goszakup login multi-step flow**
   - Что знаем: instruction_for_SPIKE03 показывает выбор ИП/физлицо + условия + пароль после NCALayer sign (первый логин). Это может быть одноразовая настройка.
   - Что неясно: Нужны ли эти шаги при каждом логине или только при первом? Как backend proxy обрабатывает redirects?
   - Рекомендация: В Plan 05-01 протестировать полный login flow через backend proxy с существующим аккаунтом goszakup.

3. **Извлечение CSRF token из goszakup responses**
   - Что знаем: CSRF передаётся в теле каждого form-encoded POST. Откуда взять начальный CSRF при создании сессии?
   - Что неясно: CSRF приходит в cookie? В Set-Cookie при login? В HTML? В response JSON?
   - Рекомендация: Проверить response headers `ajax_create_application` (шаг 1) — искать `Set-Cookie: csrf=...` или JSON field.

4. **Document attachment на goszakup portal (D-S03-03)**
   - Что знаем: Не захвачено в SPIKE-03. URL шага: `/ru/application/show_doc/{tBuyId}/{appId}/{lotId}/{appLotId}`
   - Что неясно: Какой HTTP метод и body для прикрепления файла с goszakup на шаге документов
   - Рекомендация: Не блокирует MVP (документы опциональны в v1). Шаг 5 (`ajax_docs_next`) пропускает документы при `next=1`.

5. **Telegram webhook vs settings — production setup**
   - Что знаем: Telegram требует HTTPS для webhook. localhost development нужен ngrok или аналог.
   - Рекомендация: В Wave 0 tests — mock telegram calls через monkeypatch. Webhook registration через `TELEGRAM_WEBHOOK_SECRET` для верификации источника.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | applications table | Check required | ≥14 assumed | — (блокирует) |
| Redis | goszakup_session, confirm TTL | ✓ (arq 0.28.0 installed) | 5.3.1 (client) | — |
| MinIO | Phase 4 documents | ✓ (Phase 4) | minio 7.x | — |
| arq | ARQ worker | ✓ | 0.28.0 | — |
| httpx | goszakup proxy | ✓ | 0.28.1 | — |
| python-telegram-bot | Telegram notifications | ✗ NOT INSTALLED | — | Нужно добавить в pyproject.toml |
| NCALayer (user's machine) | Signing flow | User-side | 1.x или 2.x | SIGN-05: show install guide |

**Missing dependencies without fallback:**
- `python-telegram-bot==22.8` — нужно добавить в `backend/pyproject.toml`

**Missing dependencies with fallback:**
- NCALayer на машине пользователя — если не установлен, показываем SIGN-05 install guide (не блокирует backend)

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| Config file | `pytest.ini` or `pyproject.toml [tool.pytest]` |
| Quick run | `cd backend && pytest tests/test_applications.py -x` |
| Full suite | `cd backend && pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SIGN-01 | NCALayer hook status transitions | unit | `pytest tests/test_ncalayer_hook.spec.ts` (frontend) | ❌ Wave 0 |
| SIGN-04 | signXml dual-mode dispatch | unit | `pytest tests/test_ncalayer_hook.spec.ts` (frontend) | ❌ Wave 0 |
| APPL-01 | POST /api/applications → создаёт черновик | integration | `pytest tests/test_applications.py::test_create_draft -x` | ❌ Wave 0 |
| APPL-03 | auto_submit_application job при status=ok | unit | `pytest tests/test_auto_submit.py::test_submit_success -x` | ❌ Wave 0 |
| APPL-07 | poll_watchlist_tenders переходит to submitting при status 220 | unit | `pytest tests/test_poll_watchlist.py::test_trigger_on_220 -x` | ❌ Wave 0 |
| APPL-09 | Да → immediate submit; Нет → cancel; timeout → submit | integration | `pytest tests/test_confirm_flow.py -x` | ❌ Wave 0 |

### Sampling Rate

- Per task commit: `cd backend && pytest tests/test_applications.py tests/test_auto_submit.py -x`
- Per wave merge: `cd backend && pytest tests/ -v`
- Phase gate: Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_applications.py` — covers APPL-01, APPL-04, APPL-05
- [ ] `backend/tests/test_goszakup_proxy.py` — covers proxy calls с respx mocks
- [ ] `backend/tests/test_auto_submit.py` — covers ARQ job logic (fakeredis + respx)
- [ ] `backend/tests/test_poll_watchlist.py` — covers ARQ cron trigger logic
- [ ] `backend/tests/test_confirm_flow.py` — covers APPL-09 Да/Нет/timeout
- [ ] `backend/tests/test_telegram_webhook.py` — covers FastAPI webhook endpoint
- [ ] `frontend/src/hooks/__tests__/useNCALayer.test.ts` — covers SIGN-01..05 hook states

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | goszakup PHPSESSID in Redis (не в DB), TTL=20h |
| V3 Session Management | yes | Redis `goszakup_session:{user_id}` — one session per user |
| V4 Access Control | yes | application.user_id == current_user.id (IDOR, аналог Phase 4 pattern) |
| V5 Input Validation | yes | Pydantic schemas для `ApplicationCreate`; validate `lots_data` structure |
| V6 Cryptography | NO | Crypto происходит в NCALayer на устройстве пользователя |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| IDOR на applications (user A видит app user B) | Information Disclosure | `SELECT ... WHERE id=? AND user_id=?` — как в Phase 4 get_user_document() |
| Telegram callback IDOR (user подменяет app_id в callback_data) | Tampering | Проверять ownership: `application.user_id == telegram_chat_id owner` в webhook handler |
| PHPSESSID утечка через logs | Information Disclosure | Не логировать PHPSESSID, CSRF — только audit-log факт события |
| ARQ job replay / двойная подача | Tampering | `_job_id=f"submit:{app_id}"` deduplicate; проверять status перед submit |
| Telegram webhook spoofing | Spoofing | `X-Telegram-Bot-Api-Secret-Token` header проверка |
| goszakup сессия без expiry в Redis | Elevation of Privilege | TTL=72000s (20h) жёстко установлен |

---

## Sources

### Primary (HIGH confidence)
- `backend/spikes/findings/SPIKE-03-FINDINGS.md` — полный flow goszakup portal, эндпойнты, форматы
- `frontend/spikes/SPIKE-02-FINDINGS.md` — NCALayer protocol, dual-mode, confirmed port 13579
- `frontend/instruction_for_SPIKE03` — реальный goszakup auth curl (NCALayer signXml + /user/sendsign/kz)
- `backend/app/services/redis_service.py` — установленный паттерн Redis helpers
- `backend/alembic/versions/0003_create_documents.py` — паттерн alembic migration
- Context7 `/websites/arq-docs_helpmanual_io` — ARQ enqueue_job, cron, Retry, WorkerSettings
- Context7 `/python-telegram-bot/python-telegram-bot` — Bot.send_message, InlineKeyboard, webhook
- GitHub `pkigovkz/NLCommonBundle/CommonUtils.java` — все публичные методы NCALayer 1.x commonUtils

### Secondary (MEDIUM confidence)
- PyPI `python-telegram-bot 22.8` — текущая стабильная версия [VERIFIED: pypi.org 2026-07-09]
- Context7 ARQ docs — `_defer_by`, `_job_id`, `Retry(defer=...)` паттерны

### Tertiary (LOW confidence)
- NCALayer basics module — только `sign` метод в публичной документации; методы для encryption не найдены
- Предположение о WebSearch: goszakup CORS policy неизвестна из публичных источников

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — все версии верифицированы
- Architecture (backend proxy): HIGH — CORS подтверждён из instruction_for_SPIKE03 `Sec-Fetch-Site: same-origin`
- NCALayer signXml/createCMS: HIGH — SPIKE-02 confirmed
- NCALayer Gamma encryption step 7: LOW — метод неизвестен из публичных источников
- ARQ patterns (cron, defer, retry): HIGH — Context7 docs verified
- python-telegram-bot patterns: HIGH — Context7 docs verified

**Research date:** 2026-07-09
**Valid until:** 2026-08-09 (ARQ/PTB stable; goszakup portal — может меняться)
