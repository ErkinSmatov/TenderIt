# Phase 6: Notifications — Research

**Researched:** 2026-07-20
**Domain:** python-telegram-bot deep-link flow, React Query v5 conditional polling, FastAPI router extension
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** WhatsApp/Twilio (NOTIF-05) деferred to v2 — не строить ничего для WhatsApp.
- **D-02:** NOTIF-06 — только просмотр и удаление watchlist. Кнопки включить/выключить нет. Используется существующий `DELETE /api/watchlist/{number_anno}`.
- **D-03:** Алгоритм Telegram deep-link: `POST /api/notifications/telegram/link-token` → UUID-токен (15 мин) → deep_link `t.me/{BOTNAME}?start={TOKEN}` → webhook `/start TOKEN` → записать `telegram_chat_id` → polling.
- **D-04:** Расширяем `telegram_webhook.py` для `update.message` — не создаём новый роутер, не создаём нового бота.
- **D-05:** `DELETE /api/notifications/telegram` — зачищает `telegram_chat_id` и `telegram_link_token`.
- **D-06:** `GET /api/notifications/status` → `{telegram_connected: bool, telegram_chat_id: int | null}`.
- **D-07:** Страница `/settings/notifications` — TelegramConnectCard (верхний блок) + WatchlistSettingsTable (ниже).
- **D-08:** Sidebar: добавить `{ href: '/settings/notifications', label: 'Настройки', icon: Bell }` после "Документы".
- **D-09:** Миграция `0008` — добавить в `users`: `telegram_link_token String(64) nullable unique`, `telegram_link_token_expires_at DateTime(timezone=True) nullable`.
- **D-10:** Новый роутер `backend/app/routers/notifications.py`, три эндпоинта, подключить в `main.py` с prefix `/api`.

### Claude's Discretion
- Конкретная длина поллинга (3 сек / 60 сек — значения обоснованы ниже).
- Обработка race condition при двойном вызове link-token (решение: перезаписывать).
- Позиция "Настройки" в Sidebar — after "Документы" (подтверждено по navItems).
- UI внутри TelegramConnectCard (spinner, loading state) — следовать существующим паттернам.

### Deferred Ideas (OUT OF SCOPE)
- WhatsApp / Twilio (NOTIF-05) — v2.
- Push-уведомления в браузере — вне скопа.
- Email-уведомления — вне скопа.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NOTIF-04 | Пользователь может подключить Telegram-бот через команду /start с привязкой к аккаунту | D-03 deep-link flow полностью исследован — PTB Update.message.text формат верифицирован |
| NOTIF-06 | Пользователь может просмотреть и управлять watchlist (удалить отслеживаемые тендеры) | Существующие `GET /api/watchlist` и `DELETE /api/watchlist/{number_anno}` готовы — фронтенд только их вызывает |
</phase_requirements>

---

## Summary

Phase 6 доставляет два независимых потока: (A) Telegram account linking через deep-link `/start TOKEN` flow и (B) watchlist management UI. Оба потока используют уже существующий бэкенд-код (один бот, один webhook, существующие watchlist-эндпоинты) — новый код минимален.

Ключевое техническое открытие: в текущем `telegram_webhook.py` при отсутствии `callback_query` выполняется ранний `return {"ok": True}` — именно туда вставляется обработка `update.message` для команды `/start TOKEN`. Это минимальное расширение, которое не трогает ни одну из существующих ветвей кода.

Фронтенд использует `@tanstack/react-query` v5 (уже установлен, QueryClientProvider уже обёрнут вокруг `(dashboard)/layout.tsx`). Условный поллинг реализуется через `refetchInterval` как функцию — это нативный v5-паттерн, уже используется в `/applications/[id]/page.tsx` с `refetchInterval: 30000`. Остановка поллинга через `pollingActive` state + `setTimeout(60s)`.

**Primary recommendation:** Реализовать в 3 плана: (1) backend — migration + notifications router, (2) backend — webhook extension, (3) frontend — settings page + sidebar.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Генерация link-token | API / Backend | — | Секретный токен не должен генерироваться на фронтенде; JWT-auth обязателен |
| Deep-link URL → пользователю | API / Backend | Frontend | Backend знает BOTNAME (settings); фронтенд показывает как кнопку |
| /start TOKEN обработка | API / Backend | — | Telegram шлёт webhook на сервер; клиентский код не задействован |
| Запись telegram_chat_id | API / Backend → Database | — | Только сервер пишет PII в БД |
| Polling telegram_connected | Frontend | — | Клиентская задача — ждать события через pooling и обновить UI |
| Watchlist display + delete | Frontend → API / Backend | Database | Существующие эндпоинты GET/DELETE /api/watchlist |

---

## Standard Stack

### Core (все уже установлены)

| Library | Version | Purpose | Статус |
|---------|---------|---------|--------|
| python-telegram-bot | 22.8 | PTB: `Update.de_json`, `telegram.Bot` async context | [VERIFIED: pyproject.toml] |
| @tanstack/react-query | ^5.100.14 | `useQuery` + `refetchInterval` polling | [VERIFIED: package.json] |
| SQLAlchemy 2.x async | 2.0.37 | ORM, add_column migration | [VERIFIED: pyproject.toml] |
| Alembic | 1.14.0 | migrations | [VERIFIED: pyproject.toml] |
| secrets (stdlib) | 3.12 builtin | `token_urlsafe(32)` для link token | [ASSUMED] |

### Нет новых зависимостей
Phase 6 не требует установки новых пакетов — всё уже присутствует.

---

## Architecture Patterns

### System Architecture Diagram

```
Browser                   FastAPI Backend              PostgreSQL
  |                            |                           |
  |-- POST /notifications/  -->|-- secrets.token_urlsafe-->|
  |   telegram/link-token      |-- UPDATE users SET        |
  |                            |   telegram_link_token     |
  |<-- {deep_link: t.me/...} --|                           |
  |                            |                           |
  | (user opens Telegram)      |                           |
  |                       Telegram Bot                     |
  |                            |                           |
  |              POST /api/telegram/webhook <-- Telegram   |
  |                            |-- SELECT user WHERE       |
  |                            |   telegram_link_token=    |
  |                            |-- UPDATE telegram_chat_id |
  |                            |-- Bot.send_message("OK") ->Telegram
  |                            |                           |
  |-- GET /notifications/   -->|-- SELECT user.            |
  |   status (poll 3s)         |   telegram_chat_id        |
  |<-- {telegram_connected:true}                           |
  |                            |                           |
  |-- GET /watchlist        -->|-- SELECT watchlist        |
  |-- DELETE /watchlist/{n} -->|-- DELETE WHERE user_id    |
```

### Recommended Project Structure

```
backend/app/
├── routers/
│   ├── notifications.py          # NEW: 3 endpoints (link-token, status, disconnect)
│   └── telegram_webhook.py       # EXTEND: add message handler for /start TOKEN
├── models/
│   └── user.py                   # EXTEND: add telegram_link_token fields
├── config.py                     # EXTEND: add telegram_bot_username setting
└── alembic/versions/
    └── 0008_add_telegram_link_token.py  # NEW: ADD COLUMN × 2

frontend/src/
├── app/(dashboard)/
│   └── settings/
│       └── notifications/
│           └── page.tsx           # NEW: /settings/notifications page
├── components/
│   └── notifications/
│       ├── TelegramConnectCard.tsx  # NEW: connect/disconnect block
│       └── WatchlistSettingsTable.tsx  # NEW: watchlist table + delete
└── components/layout/
    └── Sidebar.tsx               # EXTEND: add Bell nav item
```

---

## Pattern 1: PTB Deep-link `/start TOKEN` — Exact Message Format

**VERIFIED via Context7 (PTB source + docs)**

Когда пользователь кликает deep-link `t.me/{BOTNAME}?start=TOKEN` и открывает бота:
- Telegram шлёт **message update** (не callback_query)
- `update.message.text` = `"/start TOKEN"` — ПОЛНАЯ строка включая команду
- Токен — всё, что идёт после `"/start "` (с пробелом)
- `/start` без токена → `update.message.text = "/start"` (без пробела в конце)

**Извлечение токена:**
```python
# Source: PTB Message class + Telegram Bot API docs
text = update.message.text or ""
if text.startswith("/start "):  # space is required — distinguishes token from plain /start
    token = text[7:].strip()    # "/start " is 7 chars
    # process token...
elif text == "/start":
    # plain /start without deep link — ignore (user typed manually, not our flow)
    pass
```

**`update.message.from_user.id`** — Telegram user ID отправителя = chat_id для private-чата.

### Anti-Patterns to Avoid
- **`text.split(" ")[1]`** — падает с IndexError если text = "/start" без пробела
- **`context.args`** — доступен только через PTB Application/CommandHandler framework. Наш webhook использует `Update.de_json(body, bot=None)` без Application — `context` недоступен. Используйте строковый парсинг.

---

## Pattern 2: Расширение telegram_webhook.py (минимальное изменение)

**VERIFIED: читал telegram_webhook.py целиком**

Текущая структура:
```python
update = Update.de_json(body, bot=None)

if not update.callback_query:
    # Non-callback update — accept silently
    return {"ok": True}   # <-- сюда вставляем обработку message
```

**Новая структура** (минимальное изменение — только вставить перед return):
```python
update = Update.de_json(body, bot=None)

if not update.callback_query:
    # Phase 6: handle /start TOKEN message for Telegram account linking
    if update.message and update.message.text:
        await _handle_start_command(update.message, db)
    return {"ok": True}   # return остаётся на месте
```

**Вспомогательная функция** (добавить выше endpoint):
```python
async def _handle_start_command(message, db: AsyncSession) -> None:
    """Handle /start TOKEN deep-link for Telegram account linking (NOTIF-04)."""
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.config import settings

    text = message.text or ""
    if not text.startswith("/start "):
        return  # plain /start without token — ignore

    token = text[7:].strip()
    if not token:
        return

    chat_id = message.from_user.id if message.from_user else None
    if not chat_id:
        return

    # Look up user by token
    result = await db.execute(
        select(User).where(User.telegram_link_token == token)
    )
    user = result.scalar_one_or_none()

    async with telegram.Bot(settings.telegram_bot_token) as bot:
        if user is None:
            await bot.send_message(chat_id=chat_id, text="Ссылка не найдена. Зайдите в TenderIt и получите новую.")
            return

        now = datetime.now(timezone.utc)
        if user.telegram_link_token_expires_at and user.telegram_link_token_expires_at < now:
            await bot.send_message(chat_id=chat_id, text="Ссылка устарела. Зайдите в TenderIt и получите новую.")
            # Clean up expired token
            user.telegram_link_token = None
            user.telegram_link_token_expires_at = None
            await db.commit()
            return

        # Link successful
        user.telegram_chat_id = chat_id
        user.telegram_link_token = None
        user.telegram_link_token_expires_at = None
        await db.commit()
        await bot.send_message(chat_id=chat_id, text="Telegram успешно подключён к TenderIt ✓")
```

**Неизменяемые инварианты (из комментариев к telegram_webhook.py):**
- T-05-31: secret-token guard остаётся первым — весь код ниже него (включая новую функцию) автоматически защищён
- T-05-30, T-07-01, T-07-02: callback_query-ветки не трогаем вообще
- `bot=None` в `Update.de_json` — корректно работает для парсинга message-updates (верифицировано в существующих тестах: test_telegram_webhook.py Test 5 уже создаёт message-update с `bot=None`)

---

## Pattern 3: Token Generation и Storage

**[VERIFIED: Python stdlib docs + pyproject.toml Python 3.12]**

```python
import secrets
from datetime import datetime, timezone, timedelta

token = secrets.token_urlsafe(32)
# Produces 43-char URL-safe base64 string. Fits in String(64) with 21 chars to spare.
# Entropy: 256 bits — collision probability negligible.

expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
# MUST use timezone.utc (aware datetime) — column is DateTime(timezone=True).
# Using datetime.utcnow() (naive) causes TypeError on comparison. [PITFALL — see below]
```

**Migration 0008** — только `op.add_column`, без создания таблиц:

```python
# revision: "0008", down_revision: "0007"
def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("telegram_link_token", sa.String(64), nullable=True),
    )
    op.create_index(
        "idx_users_telegram_link_token",
        "users",
        ["telegram_link_token"],
        unique=True,
    )
    op.add_column(
        "users",
        sa.Column(
            "telegram_link_token_expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )

def downgrade() -> None:
    op.drop_column("users", "telegram_link_token_expires_at")
    op.drop_index("idx_users_telegram_link_token", table_name="users")
    op.drop_column("users", "telegram_link_token")
```

**User model расширение** (`user.py`):
```python
# Add after telegram_chat_id (existing):
telegram_link_token: Mapped[Optional[str]] = mapped_column(
    String(64), nullable=True, unique=True, index=True
)
telegram_link_token_expires_at: Mapped[Optional[datetime]] = mapped_column(
    sa.TIMESTAMP(timezone=True), nullable=True
)
```

---

## Pattern 4: Notifications Router

**[VERIFIED: читал company.py, tenders.py, main.py]**

```python
# backend/app/routers/notifications.py
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/notifications/telegram/link-token")
async def create_link_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    token = secrets.token_urlsafe(32)
    current_user.telegram_link_token = token
    current_user.telegram_link_token_expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=15)
    )
    await db.commit()
    deep_link = f"https://t.me/{settings.telegram_bot_username}?start={token}"
    return {"deep_link": deep_link}

@router.get("/notifications/status")
async def get_notification_status(
    current_user: User = Depends(get_current_user),
):
    return {
        "telegram_connected": current_user.telegram_chat_id is not None,
        "telegram_chat_id": current_user.telegram_chat_id,
    }

@router.delete("/notifications/telegram", status_code=204)
async def disconnect_telegram(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    current_user.telegram_chat_id = None
    current_user.telegram_link_token = None
    current_user.telegram_link_token_expires_at = None
    await db.commit()
    return Response(status_code=204)
```

**main.py — добавить две строки** (pattern из существующего кода):
```python
from app.routers import notifications  # добавить в существующий import-блок
# ...
application.include_router(notifications.router, prefix="/api", tags=["notifications"])
```

**Новая настройка в config.py:**
```python
# Phase 6: Telegram bot username for deep-link generation (NOTIF-04)
# Set TELEGRAM_BOT_USERNAME env var in production.
telegram_bot_username: str = ""
```

---

## Pattern 5: Frontend Polling — React Query v5

**[VERIFIED: package.json (@tanstack/react-query ^5.100.14) + читал applications/[id]/page.tsx + Providers.tsx]**

### QueryClientProvider
Уже присутствует в `(dashboard)/Providers.tsx` — новая страница ничего не добавляет:
```tsx
// (dashboard)/layout.tsx
<Providers>{children}</Providers>  // QueryClientProvider уже здесь
```

### Паттерн условного поллинга (v5 синтаксис)

**ВАЖНО:** В React Query v5 `refetchInterval` как функция принимает `(query)`, а не `(data, error)` (v4 breaking change).

```tsx
// frontend/src/app/(dashboard)/settings/notifications/page.tsx
'use client'

import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

interface NotificationStatus {
  telegram_connected: boolean
  telegram_chat_id: number | null
}

export default function NotificationsPage() {
  const [deepLink, setDeepLink] = useState<string | null>(null)
  const [pollingActive, setPollingActive] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { data: status, isLoading } = useQuery<NotificationStatus>({
    queryKey: ['notification-status'],
    queryFn: () => api.get<NotificationStatus>('/api/notifications/status'),
    // Poll every 3s ONLY while waiting for Telegram link; stop when connected
    refetchInterval: (query) => {
      if (!pollingActive) return false
      if (query.state.data?.telegram_connected) return false
      return 3000
    },
    retry: false,
  })

  // Stop polling when connected (cleanup timeout)
  useEffect(() => {
    if (status?.telegram_connected && pollingActive) {
      setPollingActive(false)
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [status?.telegram_connected, pollingActive])

  async function handleConnectClick() {
    const result = await api.post<{ deep_link: string }>(
      '/api/notifications/telegram/link-token', {}
    )
    setDeepLink(result.deep_link)
    setPollingActive(true)
    // Stop polling after 60s regardless
    timeoutRef.current = setTimeout(() => {
      setPollingActive(false)
      setDeepLink(null)
    }, 60_000)
  }

  async function handleDisconnect() {
    await api.delete('/api/notifications/telegram')
    // React Query will refetch on next poll or manual invalidation
  }

  // ... render TelegramConnectCard + WatchlistSettingsTable
}
```

### Polling timeout boundary
- `pollingActive: true` → refetchInterval = 3s
- `status.telegram_connected: true` → polling stops (via refetchInterval function)
- After 60s → `setTimeout` → `setPollingActive(false)` + `setDeepLink(null)` → deep link UI скрывается

---

## Pattern 6: Sidebar Nav Extension

**[VERIFIED: читал Sidebar.tsx целиком]**

Текущие импорты в Sidebar.tsx: `LayoutDashboard, Search, Building2, FileText, ClipboardList, LogOut, Sparkles, ExternalLink` — `Bell` НЕ импортирован.

`Bell` существует в `lucide-react` (библиотека установлена: `"lucide-react": "^1.17.0"`). Нужно добавить к импорту.

**Изменение в Sidebar.tsx:**
```tsx
// BEFORE:
import { LayoutDashboard, Search, Building2, FileText, ClipboardList, LogOut, Sparkles, ExternalLink } from 'lucide-react'

// AFTER:
import { LayoutDashboard, Search, Building2, FileText, ClipboardList, LogOut, Sparkles, ExternalLink, Bell } from 'lucide-react'

// navItems array — добавить после { href: '/documents', ... }:
{ href: '/settings/notifications', label: 'Настройки', icon: Bell },
```

**Позиция:** после "Документы" (последний item в текущем navItems). Итоговый порядок: Обзор, Тендеры, Заявки, Подборка, Профиль, Документы, **Настройки**.

---

## Pattern 7: Settings Page Layout

**[VERIFIED: читал profile/page.tsx, CompanyProfileForm.tsx, (dashboard)/layout.tsx]**

Паттерн страницы:
```tsx
// frontend/src/app/(dashboard)/settings/notifications/page.tsx
'use client'

export default function NotificationsSettingsPage() {
  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold">Настройки уведомлений</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Подключите Telegram для получения уведомлений о тендерах
        </p>
      </div>

      <TelegramConnectCard />
      <WatchlistSettingsTable />
    </div>
  )
}
```

- `(dashboard)/layout.tsx` автоматически оборачивает в Sidebar + Providers
- Отдельный layout для `/settings/notifications` НЕ нужен
- Файл страницы: `frontend/src/app/(dashboard)/settings/notifications/page.tsx`
- Компоненты: `frontend/src/components/notifications/TelegramConnectCard.tsx` + `WatchlistSettingsTable.tsx`

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Secure token generation | UUID4 / random.choices | `secrets.token_urlsafe(32)` | Cryptographically secure PRNG; stdlib |
| Conditional polling | `setInterval` + `clearInterval` | `useQuery({ refetchInterval: fn })` | React Query обрабатывает cleanup, stale data, error states |
| Deep-link URL construction | Custom URL builder | `f"https://t.me/{bot_username}?start={token}"` | Telegram документирует этот точный формат |
| Bot reply in webhook | New bot singleton | `async with telegram.Bot(token) as bot` | Существующий паттерн в telegram_service.py |
| Watchlist CRUD | New backend endpoints | `GET /api/watchlist` + `DELETE /api/watchlist/{n}` | Уже реализованы в tenders.py |

---

## Common Pitfalls

### Pitfall 1: `/start` vs `/start TOKEN` — text parsing
**What goes wrong:** Если проверять `if " " in text` или `text.split()[1]`, то при `text = "/start"` (без токена) получим IndexError или неверный результат.
**Why it happens:** Telegram шлёт `/start` (без payload) когда пользователь открывает бота вручную, без deep-link. Это легитимный кейс.
**How to avoid:** Всегда проверять `text.startswith("/start ")` (с пробелом) перед извлечением токена.
**Warning signs:** IndexError или AttributeError в webhook logs при ручном `/start`.

### Pitfall 2: Naive vs Aware Datetime (timezone)
**What goes wrong:** `user.telegram_link_token_expires_at < datetime.utcnow()` → `TypeError: can't compare offset-naive and offset-aware datetimes`.
**Why it happens:** Колонка `DateTime(timezone=True)` → asyncpg возвращает `datetime` с `tzinfo=UTC`. `datetime.utcnow()` — naive.
**How to avoid:** Всегда `datetime.now(timezone.utc)` для сравнения с колонками `timezone=True`.
**Warning signs:** `TypeError` в stacktrace при истечении токена.

### Pitfall 3: `context.args` недоступен в raw webhook режиме
**What goes wrong:** PTB tutorial использует `context.args` для извлечения аргументов `/start`. Но это работает только через `Application`/`CommandHandler` framework.
**Why it happens:** Наш webhook принимает сырой JSON и вызывает `Update.de_json(body, bot=None)` — `ContextTypes` не создаётся.
**How to avoid:** Парсить `update.message.text` вручную: `text[7:].strip()` после `text.startswith("/start ")`.

### Pitfall 4: React Query v5 — `refetchInterval` function signature изменился
**What goes wrong:** `refetchInterval: (data, error) => data?.telegram_connected ? false : 3000` — это **v4 синтаксис**, в v5 вернёт TypeScript ошибку или работает непредсказуемо.
**Why it happens:** TanStack Query v5 breaking change: функция принимает `(query: Query)` вместо `(data, error)`.
**How to avoid:** v5 паттерн: `refetchInterval: (query) => query.state.data?.telegram_connected ? false : 3000`.

### Pitfall 5: Существующий тест test 5 нужно обновить
**What goes wrong:** `test_webhook_plain_message_returns_ok` отправляет `"text": "Hello"` (не `/start TOKEN`). После нашего изменения этот тест продолжает работать (нет `"/start "` в тексте → early return). Но тест описан как "non-callback update ignored" — это описание изменится (plain messages теперь могут БЫТЬ обработаны, если text = `/start TOKEN`).
**How to avoid:** Тест 5 продолжает проходить без изменений. Добавить новые тесты: `test_webhook_start_token_links_telegram` и `test_webhook_start_token_expired`.

### Pitfall 6: Missing `telegram_bot_username` в settings
**What goes wrong:** Backend не может сгенерировать deep_link без BOTNAME.
**Why it happens:** Текущий `config.py` имеет `telegram_bot_token` но не `telegram_bot_username`.
**How to avoid:** Добавить `telegram_bot_username: str = ""` в `Settings` в `config.py`. Установить `TELEGRAM_BOT_USERNAME` в `.env` в production.

### Pitfall 7: Race condition при двойном POST link-token
**Решение:** Просто перезаписать токен. Новый токен перезаписывает старый (UPDATE, не INSERT). Предыдущая ссылка становится невалидной (токен не совпадает) — безопасно.

---

## Code Examples

### Extracting TOKEN from PTB message update
```python
# Source: PTB Message class (Context7: /python-telegram-bot/python-telegram-bot)
# In raw webhook: update.message is telegram.Message object parsed from JSON

def extract_start_token(message) -> str | None:
    """Extract deep-link token from /start TOKEN message. Returns None if not a tokenized /start."""
    text = (message.text or "").strip()
    if not text.startswith("/start "):
        return None
    token = text[7:].strip()
    return token if token else None
```

### React Query v5 conditional polling
```tsx
// Source: @tanstack/react-query v5 docs + applications/[id]/page.tsx pattern
const { data } = useQuery<NotificationStatus>({
  queryKey: ['notification-status'],
  queryFn: () => api.get<NotificationStatus>('/api/notifications/status'),
  refetchInterval: (query) => {
    // v5 API: query.state.data (not (data, error) like v4)
    if (!pollingActive) return false
    if (query.state.data?.telegram_connected) return false
    return 3000  // poll every 3s while waiting
  },
  retry: false,
  staleTime: 0,  // always consider stale during polling
})
```

### Sending reply in webhook (no Application framework)
```python
# Source: telegram_service.py pattern (async with telegram.Bot pattern)
async with telegram.Bot(settings.telegram_bot_token) as bot:
    await bot.send_message(
        chat_id=chat_id,
        text="Telegram успешно подключён к TenderIt ✓"
    )
```

---

## Runtime State Inventory

> Phase 6 — не rename/refactor. Runtime state, тем не менее, значим из-за Telegram webhook регистрации.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `users.telegram_chat_id` — существующие данные от Phase 5 (если есть) | Никаких миграций данных; колонка уже nullable |
| Live service config | Telegram webhook `set_webhook` вызывается при каждом старте `main.py` lifespan — URL регистрируется автоматически | Никаких ручных шагов; тот же URL `/api/telegram/webhook` |
| OS-registered state | None | None |
| Secrets/env vars | `TELEGRAM_BOT_USERNAME` — новая переменная, нужна для deep-link | Добавить в `.env` + production secrets |
| Build artifacts | None | None |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| python-telegram-bot | Webhook message handler | ✓ | 22.8 | — |
| @tanstack/react-query | Frontend polling | ✓ | ^5.100.14 | — |
| PostgreSQL | Migration 0008 | ✓ (assumed dev env running) | 16 | — |
| TELEGRAM_BOT_TOKEN | deep link + bot.send_message | ✓ (set in Phase 5) | — | Empty = notifications skipped (existing guard in main.py) |
| TELEGRAM_BOT_USERNAME | link-token deep_link URL | ✗ (new requirement) | — | Empty string → broken deep link URL |

**Missing dependencies with no fallback:**
- `TELEGRAM_BOT_USERNAME` env var — без него `deep_link` будет `"https://t.me/?start=TOKEN"` (невалидный URL). Плановое задание Wave 0: добавить в `.env` и `config.py`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| Config file | `backend/pytest.ini` (`asyncio_mode = auto`) |
| Quick run command | `cd backend && pytest tests/test_telegram_webhook.py tests/test_notifications.py -x -q` |
| Full suite command | `cd backend && pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NOTIF-04 | POST link-token → token записан в User | unit | `pytest tests/test_notifications.py::test_create_link_token -x` | ❌ Wave 0 |
| NOTIF-04 | GET status → `telegram_connected: true` когда chat_id установлен | unit | `pytest tests/test_notifications.py::test_get_status -x` | ❌ Wave 0 |
| NOTIF-04 | DELETE disconnect → chat_id = NULL | unit | `pytest tests/test_notifications.py::test_disconnect -x` | ❌ Wave 0 |
| NOTIF-04 | webhook `/start TOKEN` → chat_id записан в БД | unit | `pytest tests/test_telegram_webhook.py::test_webhook_start_token_links_telegram -x` | ❌ Wave 0 |
| NOTIF-04 | webhook `/start TOKEN` expired → error reply, chat_id не записан | unit | `pytest tests/test_telegram_webhook.py::test_webhook_start_token_expired -x` | ❌ Wave 0 |
| NOTIF-06 | GET /api/watchlist → список тендеров | unit | `pytest tests/test_watchlist.py -x` (если есть) | manual check |

### Sampling Rate
- Per task commit: `cd backend && pytest tests/test_notifications.py tests/test_telegram_webhook.py -x -q`
- Per wave merge: `cd backend && pytest -x -q`
- Phase gate: полный suite зелёный до `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_notifications.py` — covers NOTIF-04 (link-token, status, disconnect endpoints)
- [ ] 2 новых теста в `backend/tests/test_telegram_webhook.py` (start token linking + expiry)
- [ ] `frontend/src/components/notifications/` — директория создаётся в Wave 1

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `get_current_user` dep (JWT) на всех `/api/notifications/*` |
| V3 Session Management | no | Токен сессии через httpOnly cookie — фаза не меняет сессии |
| V4 Access Control | yes | `telegram_link_token` lookup — пользователь идентифицируется токеном, не self-reported chat_id |
| V5 Input Validation | yes | Token length validation (`if not token: return`); chat_id = integer из Telegram (не user input) |
| V6 Cryptography | yes | `secrets.token_urlsafe(32)` — криптографически безопасный PRNG |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Token forgery — угадать чужой link_token | Spoofing | `secrets.token_urlsafe(32)` = 256 бит энтропии; токен истекает за 15 мин |
| Token replay — использовать токен повторно | Elevation of Privilege | Токен очищается после первого использования (`telegram_link_token = None`) |
| IDOR на disconnect | Elevation of Privilege | `get_current_user` — `telegram_chat_id` пишется только к authenticated user |
| Webhook spoofing | Spoofing | `X-Telegram-Bot-Api-Secret-Token` guard (T-05-31) — уже реализован, сохранить |
| Expired token abuse | Elevation of Privilege | `expires_at` check на каждый `/start TOKEN` в webhook handler |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `secrets.token_urlsafe(32)` доступен в Python 3.12 stdlib | Pattern 3 | Нет риска — stdlib с Python 3.6+ |
| A2 | 60 секунд — разумный timeout для ожидания Telegram linkage | Polling Pattern | Если медленный пользователь — просто нажмёт "Подключить" снова |
| A3 | `telegram_bot_username` можно передавать как строку, без вызова `bot.get_me()` | Pattern 4 (router) | Если username неизвестен или неправильный — deep_link сломан. Требует добавления в `.env`. |

---

## Open Questions

1. **Нужен ли `staleTime: 0` для `/notification-status` запроса при polling?**
   - Что мы знаем: QueryClient по умолчанию имеет `staleTime: 60_000` (из Providers.tsx). Это означает что `useQuery` не будет refetch если данные "свежие" (< 1 min).
   - Что неясно: при `refetchInterval: 3000`, React Query всё равно делает refetch независимо от staleTime — `refetchInterval` всегда срабатывает.
   - Рекомендация: добавить `staleTime: 0` к этому конкретному `useQuery` для ясности, но это не блокирующий вопрос.

2. **Нужна ли queryClient.invalidateQueries после disconnect?**
   - Что мы знаем: React Query кэширует `['notification-status']`. После `DELETE /notifications/telegram` данные в кэше устарели.
   - Рекомендация: вызвать `queryClient.invalidateQueries({ queryKey: ['notification-status'] })` после disconnect или использовать `queryClient.setQueryData` для оптимистичного update.

---

## Sources

### Primary (HIGH confidence)
- `backend/app/routers/telegram_webhook.py` — прочитан целиком, понята текущая структура
- `backend/app/services/telegram_service.py` — прочитан целиком, `async with Bot` паттерн
- `backend/app/models/user.py` — прочитан целиком, существующие поля
- `backend/alembic/versions/0004_create_applications.py` — паттерн `op.add_column` на users
- `backend/alembic/versions/0007_create_tender_matches.py` — последняя миграция, `down_revision`
- `frontend/src/app/(dashboard)/applications/[id]/page.tsx` — `refetchInterval: 30000` паттерн
- `frontend/src/app/(dashboard)/Providers.tsx` — QueryClientProvider, staleTime: 60_000
- `frontend/src/components/layout/Sidebar.tsx` — navItems structure, lucide imports
- `frontend/package.json` — `@tanstack/react-query: ^5.100.14` verified
- `backend/pyproject.toml` — `python-telegram-bot==22.8` verified
- Context7 `/python-telegram-bot/python-telegram-bot` — Message.text deep-link format, PTB patterns

### Secondary (MEDIUM confidence)
- Context7 PTB docs: CommandHandler.check_update, message.entities — подтверждают что deep-link payload в message.text

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — всё верифицировано через package.json и pyproject.toml
- PTB deep-link format: HIGH — верифицировано через Context7 PTB source + Message class docs
- Architecture: HIGH — основано на прочитанном codebase
- Pitfalls: HIGH — питфоллы вытекают из реальных несоответствий в коде (бот=None, v5 синтаксис)
- React Query polling: HIGH — существующий паттерн в `[id]/page.tsx` + verified v5 API

**Research date:** 2026-07-20
**Valid until:** 2026-08-20 (PTB 22.x stable; React Query v5 stable)
