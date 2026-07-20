# Phase 6: Notifications - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-20
**Phase:** 06-notifications
**Areas discussed:** WhatsApp scope, Watchlist semantics, Telegram linking UX, Status polling, Settings navigation, Disconnect flow

---

## Scope: WhatsApp

| Option | Description | Selected |
|--------|-------------|----------|
| Реализовать WhatsApp через Twilio | OTP-верификация номера, `whatsapp_service.py`, Twilio webhook, extend auto_submit worker | |
| Только Telegram, WhatsApp → v2 | Исключить NOTIF-05 из Phase 6 полностью | ✓ |

**User's choice:** "WhatsApp не будем делать, только telegram"
**Notes:** NOTIF-05 явно деферируется в v2. Это уменьшает объём Phase 6 до Telegram linking + watchlist UI.

---

## Watchlist: Enable/Disable семантика

| Option | Description | Selected |
|--------|-------------|----------|
| Просто удалить | Нет is_active поля. DELETE /api/watchlist/{number_anno} существует. Страница показывает список + кнопку Удалить. | ✓ |
| Добавить is_active toggle | Новое поле is_active на UserWatchlist, migration 0008, PATCH endpoint. Позволяет приостановить отслеживание без удаления. | |

**User's choice:** Просто удалить (Recommended)
**Notes:** UserWatchlist не получает новых полей. migration 0008 используется только для telegram_link_token.

---

## Telegram Linking UX

| Option | Description | Selected |
|--------|-------------|----------|
| Deep link + copy | Backend генерирует токен. Frontend показывает кнопку "Открыть в Telegram" (deep link t.me/bot?start=TOKEN) + текстовую инструкцию. | ✓ |
| QR code + deep link | Дополнительно показывает QR-код для сканирования с мобильного. Требует qrcode-библиотеку. | |

**User's choice:** Deep link + copy (Recommended)
**Notes:** QR-код — unnecessary complexity для MVP. Большинство пользователей кликают по ссылке.

---

## Frontend Status Polling

| Option | Description | Selected |
|--------|-------------|----------|
| GET /api/notifications/status polling | Frontend поллит каждые 3 сек (макс 60 сек) после показа deep link. При telegram_connected: true — обновляет UI. | ✓ |
| Ручной refetch по кнопке | Пользователь нажимает "Я уже отправил /start" — frontend делает один запрос. | |

**User's choice:** GET /api/notifications/status поллинг (Recommended)
**Notes:** Автоматический polling лучше UX — пользователь не должен явно нажимать кнопку подтверждения.

---

## Settings Page Navigation

| Option | Description | Selected |
|--------|-------------|----------|
| /settings/notifications | Новый пункт "Настройки" в Sidebar с icon Bell. Отдельная страница. | ✓ |
| /profile дополнительный раздел | Вкладка на странице профиля компании. Меньше переключений навигации. | |

**User's choice:** /settings/notifications (Recommended)
**Notes:** Чистое разделение — профиль компании отдельно, уведомления отдельно.

---

## Settings Page Content

| Option | Description | Selected |
|--------|-------------|----------|
| Telegram блок + Watchlist на одной странице | Два блока: (1) TelegramConnectCard вверху; (2) WatchlistSettingsTable ниже. | ✓ |
| Telegram отдельно, watchlist в /tenders | Watchlist management остаётся на странице тендеров. | |

**User's choice:** Telegram блок + Watchlist на одной странице (Recommended)
**Notes:** Всё в одном месте — меньше навигации для пользователя.

---

## Telegram Disconnect

| Option | Description | Selected |
|--------|-------------|----------|
| Disconnect кнопка | DELETE /api/notifications/telegram → telegram_chat_id = NULL. Полезно при смене Telegram-аккаунта. | ✓ |
| Нет disconnect | Только через support. Проще в MVP. | |

**User's choice:** Disconnect кнопка (Recommended)
**Notes:** Стандартный UX — пользователь должен уметь отвязать аккаунт самостоятельно.

---

## Claude's Discretion

- Конкретный интервал поллинга (3 сек) и timeout (60 сек) — рекомендованные значения
- Race condition при повторном вызове link-token — рекомендуется перезаписывать токен
- Точный формат PTB payload при deep-link `/start TOKEN` — researcher проверит docs
- Позиция "Настройки" в navItems Sidebar (после Документы)
- Loading spinner UI во время поллинга

## Deferred Ideas

- **WhatsApp/Twilio (NOTIF-05)** — явное решение пользователя. v2 после валидации.
- **Browser push notifications** — не упоминались.
- **Email notifications** — вне скопа.
