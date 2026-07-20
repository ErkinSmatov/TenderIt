# Phase 6: Notifications - Context

**Gathered:** 2026-07-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 6 доставляет одну вещь: пользователь может подключить свой Telegram-аккаунт к TenderIt через deep-link `/start` flow и управлять своим watchlist на странице настроек.

**В рамках Phase 6:**
- Telegram account linking: генерация токена → deep-link → `/start TOKEN` → `telegram_chat_id` записан
- Telegram disconnect: очистка `telegram_chat_id`
- `/settings/notifications` page: Telegram-блок (подключить/отключить) + watchlist таблица (просмотр + удалить)
- Sidebar: новый пункт "Настройки" → `/settings/notifications`

**Вне рамок Phase 6:**
- WhatsApp/Twilio → **deferred v2** (пользователь принял решение исключить из MVP)
- Никаких новых Telegram-ботов — только расширение существующего (D-09 из Phase 7)

</domain>

<decisions>
## Implementation Decisions

### D-01: WhatsApp deferred
**LOCKED.** NOTIF-05 (WhatsApp через Twilio) исключается из Phase 6. Реализуется в v2. Бэкенд и фронтенд WhatsApp не создаются. Миграции для `whatsapp_phone` нет.

### D-02: Watchlist management — только удаление
**LOCKED.** NOTIF-06 означает: страница со списком отслеживаемых тендеров + кнопка "Удалить" у каждого. Никакого toggle enable/disable. Миграция с `is_active` не нужна. Используется существующий `DELETE /api/watchlist/{number_anno}`.

### D-03: Telegram deep-link flow
**LOCKED.** Алгоритм:
1. Пользователь нажимает "Подключить Telegram" на `/settings/notifications`
2. Frontend вызывает `POST /api/notifications/telegram/link-token` (JWT-авторизованный)
3. Backend генерирует UUID-токен, сохраняет его в `User.telegram_link_token` + `User.telegram_link_token_expires_at` (15 мин), возвращает `{deep_link: "https://t.me/{BOTNAME}?start={TOKEN}"}`
4. Frontend показывает кнопку "Открыть Telegram" (внешняя ссылка на deep_link) + текст "Перейдите в бот и нажмите Start"
5. Пользователь открывает Telegram → бот получает `/start TOKEN`
6. Backend-обработчик валидирует токен, записывает `user.telegram_chat_id`, очищает токен
7. Frontend поллит `GET /api/notifications/status` каждые 3 сек (макс 60 сек) → при `telegram_connected: true` обновляет UI

### D-04: Telegram /start обработчик в telegram_webhook.py
**LOCKED.** Расширяем существующий `backend/app/routers/telegram_webhook.py` для обработки **message**-обновлений (не только callback_query). Когда Telegram шлёт сообщение с текстом `/start TOKEN` (или `/start` + inline deep-link payload):
- Ищем пользователя по `telegram_link_token`
- Проверяем `telegram_link_token_expires_at` (истёк → отвечаем "Ссылка устарела, зайдите в TenderIt и получите новую")
- Записываем `user.telegram_chat_id = message.from_user.id`
- Очищаем `telegram_link_token` и `telegram_link_token_expires_at`
- Отвечаем: "Telegram успешно подключён к TenderIt ✓"

**Не создавать новый роутер, не создавать новый бот** (D-09 Phase 7).

### D-05: Telegram disconnect
**LOCKED.** `DELETE /api/notifications/telegram` (JWT-авторизованный) → устанавливает `user.telegram_chat_id = NULL`, очищает `telegram_link_token` (если есть). Кнопка "Отключить" показывается только когда `telegram_connected: true`.

### D-06: GET /api/notifications/status endpoint
**LOCKED.** Возвращает `{telegram_connected: bool, telegram_chat_id: int | null}`. Используется для initial render страницы и для поллинга после показа deep link. Только JWT-авторизованный доступ.

### D-07: /settings/notifications page layout
**LOCKED.** Единая страница с двумя секциями:
1. **TelegramConnectCard** (верхний блок): статус (✓ Telegram подключён + кнопка "Отключить") или (кнопка "Подключить Telegram" → показывает deep link + polling)
2. **WatchlistSettingsTable** (ниже): таблица отслеживаемых тендеров (номер, название, дедлайн, статус) + кнопка "Удалить" у каждой строки

### D-08: Sidebar навигация
**LOCKED.** Добавить новый пункт в `navItems` в `Sidebar.tsx`:
- href: `/settings/notifications`
- label: "Настройки"
- icon: `Bell` из lucide-react

Расположение: после "Документы" (или вместе с Профилем — researcher подтвердит по текущим шаблонам).

### D-09: DB migration 0008
**LOCKED.** Добавить в таблицу `users`:
- `telegram_link_token` — `String(64)`, nullable, уникальный индекс
- `telegram_link_token_expires_at` — `DateTime(timezone=True)`, nullable

Следующая миграция после текущей 0007 (create_tender_matches).

### D-10: Новый роутер notifications.py
**LOCKED.** Создать `backend/app/routers/notifications.py` с тремя эндпоинтами:
- `POST /api/notifications/telegram/link-token`
- `GET /api/notifications/status`
- `DELETE /api/notifications/telegram`

Подключить в `backend/app/main.py` с prefix `/api`.

### Claude's Discretion
- Конкретная длина поллинга (3 сек / 60 сек — рекомендованные значения, researcher может скорректировать)
- Обработка race condition: одновременный вызов link-token два раза — перезаписать токен или вернуть существующий (рекомендуется перезаписывать)
- Как именно Telegram шлёт deep-link payload: `/start TOKEN` как текст в message.text — researcher должен проверить PTB docs, т.к. поведение зависит от версии
- Иконка Bell — если нет в текущих импортах Sidebar, добавить из lucide-react
- Конкретный UI внутри TelegramConnectCard (loading spinner во время поллинга и т.д.) — следовать существующим паттернам

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Backend — расширять, не переписывать
- `backend/app/routers/telegram_webhook.py` — existing webhook router to EXTEND with message update handler. Guard pattern for secret token уже реализован — сохранить.
- `backend/app/services/telegram_service.py` — PTB `async with telegram.Bot(token)` pattern для отправки ответа пользователю после /start
- `backend/app/models/user.py` — User ORM model (добавить telegram_link_token поля)
- `backend/app/routers/tenders.py` — `DELETE /api/watchlist/{number_anno}` endpoint (watchlist delete уже реализован — reuse на фронте)

### Миграции
- `backend/alembic/versions/0004_create_applications.py` — pattern для ADD COLUMN на users (уже добавлял telegram_chat_id — тот же шаблон для 0008)

### Frontend — следовать паттернам
- `frontend/src/components/layout/Sidebar.tsx` — добавить новый nav item (Bell icon, href /settings/notifications)
- `frontend/src/app/(dashboard)/profile/page.tsx` — pattern для settings-style страниц в dashboard layout
- `frontend/src/app/(dashboard)/profile/CompanyProfileForm.tsx` — паттерн формы с API-вызовами

### Requirements
- `.planning/REQUIREMENTS.md` строки NOTIF-04, NOTIF-06 — определения требований

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DELETE /api/watchlist/{number_anno}` (tenders.py) — уже реализован, frontend просто вызывает его
- `GET /api/watchlist` (tenders.py) — уже реализован, используется для WatchlistSettingsTable
- `telegram.Bot(token)` async context manager — паттерн из telegram_service.py для ответа на /start
- Lucide-react: `Bell` icon доступен (библиотека уже используется — see Sidebar.tsx imports)
- `api` client из `@/lib/api` — fetch wrapper, используется во всех роутах (reuse в notifications page)
- `useAuthStore` из `@/store/authStore` — auth state (JWT) для API-вызовов

### Established Patterns
- **JWT-auth**: все `/api/*` роуты защищены через `get_current_user` dep (FastAPI). Новые роуты в `notifications.py` следуют тому же шаблону
- **ARQ guards**: `if user.telegram_chat_id is None: skip` pattern (Phase 7 workers) — Phase 6 РАЗБЛОКИРУЕТ их, но не изменяет
- **Migration pattern**: `op.add_column("users", sa.Column(...))` + `op.drop_column` in downgrade — из 0004
- **Webhook secret verification**: `X-Telegram-Bot-Api-Secret-Token` проверка в telegram_webhook.py — сохранить при расширении
- **Dashboard layout**: `(dashboard)/layout.tsx` + Sidebar — все новые страницы используют тот же лэйаут

### Integration Points
- `backend/app/main.py` — `include_router(notifications_router, prefix="/api")` нужно добавить
- `telegram_webhook.py` — добавить обработку `update.message` (сейчас: early return если нет callback_query)
- `User` model → расширить двумя nullable полями (link token)
- `Sidebar.tsx` navItems array — добавить один item

</code_context>

<specifics>
## Specific Ideas

- После успешного подключения Telegram (backend записал chat_id) бот должен ответить сообщением "Telegram успешно подключён к TenderIt ✓" — это подтверждение для пользователя в Telegram
- Frontend показывает состояние polling визуально (spinner или "Ожидание подключения...") пока `telegram_connected` не станет `true`
- Страница `/settings/notifications` не требует отдельного layout — использует существующий `(dashboard)/layout.tsx`

</specifics>

<deferred>
## Deferred Ideas

- **WhatsApp / Twilio** (NOTIF-05) — явное решение пользователя: не строить в MVP. Реализовать в v2 после валидации Telegram-флоу. Потребует: `whatsapp_phone` поле на User, `whatsapp_service.py`, endpoints для OTP-верификации, Twilio webhook.
- **Push-уведомления в браузере** — не упоминались, вне скопа v1.
- **Email-уведомления** — вне скопа (нет в требованиях).

</deferred>

---

*Phase: 06-notifications*
*Context gathered: 2026-07-20*
