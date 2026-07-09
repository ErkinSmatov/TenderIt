---
phase: 05-eds-signing-submission
discussed: 2026-06-11
spike_completed: 2026-07-09
status: decisions_locked
spike_blocker: none
---

# Phase 5: EDS Signing & Submission — Context & Decisions

## Phase Goal

Пользователь заранее подготавливает подписанный черновик заявки.
Когда отслеживаемый тендер открывается для подачи заявок, система уведомляет
пользователя через Telegram и автоматически подаёт заявку по подтверждению
(или через 15-минутный таймаут).

---

## SPIKE-03: ЗАВЕРШЁН (2026-07-09)

**Полные findings:** `backend/spikes/findings/SPIKE-03-FINDINGS.md`

### Ключевые выводы SPIKE-03

| Вопрос | Ответ |
|--------|-------|
| Auth механизм | **Сценарий B — PHP сессия (PHPSESSID + CSRF)**, NOT Bearer |
| Content-Type | `application/x-www-form-urlencoded` (не JSON!) |
| Цена | **Гамма-шифрование** через NCALayer (CMS encryption + GOST sign) |
| Unsigned XML шаг | **Отсутствует** — XML генерируется порталом внутренне |
| Финальный сабмит | `POST /ru/application/ajax_public_application/{tenderBuyId}/{appId}` |
| Документы | Не захвачены — открытый вопрос |
| GOST сертификат | **GOST-2022 подтверждён** из signData в HAR |

---

## Решения, принятые на обсуждении

### D-05-01: Архитектура submission слоя — GoszakupPortalClient (обновлено по SPIKE-03)

**Решение:** Backend реализует `GoszakupPortalClient` — конкретный HTTP-клиент для портала.
Абстрактный интерфейс SubmissionGateway убран — реальный флоу теперь известен.

```python
# backend/app/services/goszakup_portal_client.py

class GoszakupPortalClient:
    """HTTP-клиент для v3bl.goszakup.gov.kz (PHP portal, form-encoded requests)."""

    async def public_application(
        self,
        tender_buy_id: int,
        application_id: int,
        session_cookie: str,
        csrf_token: str,
    ) -> dict:
        """
        Финальный сабмит.
        POST /ru/application/ajax_public_application/{tender_buy_id}/{application_id}
        Returns: {"status": "ok"} or {"status": "error", "message": "..."}
        """
```

**Что делает браузер (не сервер):**
- Шаги 1-11: create_draft, add_lots, beneficiary, gamma encryption, save signs, priceoffers_next
- Передаёт на backend: `{goszakup_application_id, session_cookie, csrf_token}`

**Что делает ARQ-воркер:**
- Шаг 12: вызывает `public_application()` с хранимой сессией при открытии тендера

**Rationale:** SPIKE-03 показал — нет unsigned XML, нет Bearer token, нет JSON API.
Это legacy PHP-портал с form-encoded запросами и сессионными куками.

---

### D-05-02: Аутентификация для submission — Сценарий B (подтверждён SPIKE-03)

**Статус:** CONFIRMED — PHP сессия (PHPSESSID + CSRF).

**Архитектура (Вариант 2):**

```
[Браузер TenderIt UI]
  │  1. Пользователь заполняет заявку
  │  2. Браузер вызывает goszakup шаги 1-11 напрямую (портал как-есть)
  │  3. Браузер передаёт {session_cookie, csrf_token, goszakup_application_id} на наш backend
  ▼
[Наш Backend]
  │  Redis хранит: goszakup_session:{user_id} = {phpsessid, csrf, app_id}  TTL=20h
  ▼
[ARQ Worker]
     Обнаружил status_id==220 → вызывает ajax_public_application с сессией из Redis
```

**Session refresh flow (если сессия истекла):**
- ARQ получает 401 → уведомление пользователю: "Нажмите для обновления сессии"
- Пользователь кликает → браузер TenderIt логинится в goszakup через NCALayer
- Новая сессия → Redis → ARQ retry

**Redis ключи:**
```
goszakup_session:{user_id}  →  {phpsessid, csrf, application_id, tender_buy_id}  TTL=20h
```

---

### D-05-03: Данные черновика заявки — минимальный MVP

**Решение:** Пользователь вводит ТОЛЬКО:
- Цену per лот (`unit_price` × quantity = `total_price` авто)
- Выбор документов из Document Vault (мульти-селект, используем `/api/documents/attachable`)

**Авто-заполняется из Company Profile:**
- `supplierBin` — из `company_profiles.bin`
- `supplierName` — из `company_profiles.name`
- `supplierAddress` — из `company_profiles.address`
- `supplierDirector` — из `company_profiles.director_name`

**Значения по умолчанию (пользователь не видит в MVP):**
- `deliveryTerm`: 30 (дней)
- `paymentTerm`: "по факту поставки"
- `vatPercent`: 0 (большинство SMB не плательщики НДС)
- `currency`: "KZT"

**Rationale:** Директор/ИП не должен знать goszakup-специфику.
Минимум ввода = максимум конверсии. VAT и delivery terms — v2.

---

### D-05-04: Машина состояний заявки

```
Черновик → Подписано → Ожидает открытия → Отправляется → Отправлено
                                                       ↘ Ошибка (с retry до 30 мин)
```

**ORM поле:** `applications.status` — enum строка:
`draft | signed | waiting | submitting | submitted | error`

**Переходы:**
- `draft → signed`: пользователь подписал через NCALayer, backend получил signedXml
- `signed → waiting`: заявка сохранена, тендер ещё не открыт (status_id ≠ 220)
- `waiting → submitting`: ARQ polling-job обнаружил status_id == 220 → отправил уведомление + запустил submit job
- `submitting → submitted`: goszakup вернул success
- `submitting → error`: goszakup вернул ошибку (retry до 30 мин с экспоненциальным back-off)

**Signed XML хранится:** в `applications.signed_xml` (TEXT column) — временно до submit, потом очищается

---

### D-05-05: ARQ polling — стратегия

**Решение:** Один ARQ job `poll_watchlist_tenders`, запускается каждые 5 минут.

**Логика:**
1. Найти все `applications` со статусом `waiting`
2. Для каждой — получить `tender.status_id` через goszakup_service (с кэшем 5 мин)
3. Если `status_id == 220` (OPEN_FOR_APPLICATIONS_STATUS_ID) → триггер submission

**Использует существующее:**
- `OPEN_FOR_APPLICATIONS_STATUS_ID = 220` из `goszakup_service.py`
- `UserWatchlist.notification_on` — проверяем перед уведомлением
- `redis_service.py` — паттерн для хранения подтверждений (15-мин TTL)

---

### D-05-06: Уведомления в Phase 5 (полный флоу)

**Решение:** Phase 5 реализует полный Telegram-флоу (APPL-08 + APPL-09).
WhatsApp — Phase 6.

**Phase 5 реализует:**
- Telegram-бот (python-telegram-bot) с inline кнопками «Да / Нет»
- Сообщение: `"Тендер №{numberAnno} открыт. Подаём заявку? [Да] [Нет]"`
- Ответ «Да» → немедленный submit
- Ответ «Нет» → статус `error` (отменена пользователем)
- Нет ответа 15 мин → ARQ delayed job → автоматический submit (fallback)

**Подтверждение хранится в Redis:**
```
Key: confirm:{application_id}
TTL: 900s (15 минут)
Value: "pending" → обновляется на "yes"/"no" при ответе
```

**Требования для Telegram-бота:**
- Пользователь должен связать Telegram-аккаунт (хранить `users.telegram_chat_id`)
- Если `telegram_chat_id` не установлен → уведомление только в UI (in-app alert)

**Phase 6 добавляет:**
- WhatsApp via Twilio
- UI для настройки уведомлений (канал, фильтры)
- NOTIF-04, NOTIF-05, NOTIF-06

---

### D-05-07: NCALayer hook — финальная архитектура

**Решение:** `useNCALayer()` hook — полная реализация на основе SPIKE-02.

```typescript
// Dual-mode dispatch (из SPIKE-02-FINDINGS.md):
// version < 2: commonUtils + array args + raw XML → responseObject
// version >= 2: basics + object args + base64 XML → result

interface NCALayerHookResult {
  status: 'disconnected' | 'connecting' | 'connected' | 'signing' | 'error'
  version: string | null
  certificates: Certificate[]
  connect: () => Promise<void>
  getCertificates: () => Promise<Certificate[]>
  signXml: (xml: string, certSerial: string) => Promise<string>
  error: string | null
}
```

**Ключевые детали (из SPIKE-02):**
- URL: `wss://127.0.0.1:13579` (порт 13579 подтверждён)
- Версия: broadcast автоматически на connect `{"result":{"version":"1.4"}}`
- 1.x: `signXml` args = `["PKCS12","SIGNATURE","<raw xml>","",""]`, результат в `responseObject`
- 2.x: `signXml` args = `{tokenType,keyType,xmlToSign:<base64>}`, результат в `result`
- AUTH сертификаты исключаются из UI (показываем только keyType=SIGNATURE)
- NCALayer 1.x (macOS) полностью поддерживается — нет минимальной версии

**Состояния в UI:**
- `disconnected` → показать кнопку «Подключить NCALayer» + ссылку на установку (SIGN-05)
- `connected` → показать данные сертификата (SIGN-02) + предупреждение если < 30 дней (SIGN-03)
- `signing` → спиннер «Введите PIN в окне NCALayer...»
- `error` → показать сообщение с причиной

---

### D-05-08: Backend — верификация подписи

**Решение:** В MVP backend НЕ верифицирует подпись локально.

**Rationale:**
- pyhanko + GOST не подтверждены из SPIKE-02 (D-S02-05 = PENDING)
- goszakup сам верифицирует подпись при submit — это достаточный контроль для MVP
- Добавление pyhanko после SPIKE-02 GOST теста — допустимо в v2

**Что backend делает:**
- Принимает `signed_xml` как строку (не парсит, не верифицирует)
- Сохраняет в `applications.signed_xml`
- При submit передаёт в SubmissionGateway as-is
- Логирует факт получения (audit trail без содержимого)

---

## DB Schema (новые таблицы)

### applications

```sql
CREATE TABLE applications (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tender_id   INTEGER NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    -- Draft data (хранится в TenderIt, не на goszakup)
    lots_data   JSONB NOT NULL,          -- [{lotId, unitPrice, quantity, totalPrice}]
    document_ids INTEGER[] NOT NULL DEFAULT '{}',  -- ссылки на documents.id
    -- goszakup Portal IDs (заполняются после того как браузер создал черновик)
    goszakup_application_id  BIGINT,     -- portal applicationId (71931023)
    goszakup_tender_buy_id   BIGINT,     -- tenderBuyId для URL (17269797)
    -- Portal Session (Вариант 2 — для ARQ авто-сабмита)
    -- Хранится в Redis: goszakup_session:{user_id} с TTL 20h
    -- НЕ в PostgreSQL (сессии меняются часто, короткий TTL)
    -- State machine
    status      TEXT NOT NULL DEFAULT 'draft',
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    -- Timestamps
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ready_at    TIMESTAMPTZ,             -- когда браузер завершил шаги 1-11
    submitted_at TIMESTAMPTZ,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_applications_user_id ON applications(user_id);
CREATE INDEX idx_applications_status ON applications(status) WHERE status IN ('waiting', 'submitting');
```

**Изменения vs исходная схема:**
- `signed_xml` убран — нет unsigned XML в реальном флоу
- `signed_at` → `ready_at` — момент когда браузер завершил шаги 1-11
- Добавлен `goszakup_tender_buy_id` — нужен ARQ для URL финального сабмита
- Сессия хранится в Redis (не в PostgreSQL) — слишком короткоживущая

### users (добавить поле)

```sql
ALTER TABLE users ADD COLUMN telegram_chat_id BIGINT;
```

---

## Алмбик-миграция

Revision: `0004` → `down_revision = "0003"`

---

## Phase 5 Планы (структура после SPIKE-03)

После заполнения SPIKE-03 планировщик создаёт:

| Plan | Содержание |
|------|-----------|
| 05-01 | SPIKE-03 analysis + DB migration (applications table) + SubmissionGateway interface |
| 05-02 | NCALayer hook (`useNCALayer`) + certificate UI (SIGN-01..05) |
| 05-03 | Application state machine + draft creation endpoint + signing endpoint |
| 05-04 | ARQ polling worker + Telegram bot + confirm flow (APPL-07..09) |
| 05-05 | Frontend: application list, status tracking, submission UI (APPL-01..06) |

**Последовательность:** 05-01 → 05-02 (можно параллельно с 05-03) → 05-03 → 05-04 → 05-05

---

## Что НЕ входит в Phase 5

- WhatsApp → Phase 6
- MP.kz submission → v2 (SPIKE-04 помечен как deferred)
- Верификация подписи (pyhanko) → v2 (после GOST-теста)
- Настройка уведомлений в UI → Phase 6
- Мультилот с разными delivery terms per лот → v2

---

## Checklist для начала Phase 5

- [x] SPIKE-03 завершён: `SPIKE-03-FINDINGS.md` заполнен (2026-07-09)
- [x] Auth-механизм подтверждён: **Сценарий B** (PHP сессия + CSRF)
- [x] Финальный сабмит эндпойнт: `POST /ru/application/ajax_public_application/{trdBuyId}/{appId}`
- [x] Авто-сабмит архитектура: **Вариант 2** (сессия в Redis, ARQ вызывает шаг 12)
- [x] Гамма-шифрование: браузер через NCALayer, backend не участвует в шифровании
- [ ] Document attachment flow — открытый вопрос (не блокирует MVP: документы опциональны в v1)
