---
phase: 07-discovery-matching
verified: 2026-07-20T00:00:00Z
status: human_needed
score: 6/6 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Запустить полный тестовый набор pytest для Phase 7"
    expected: "41 тест проходит без ошибок: test_matching_service.py (10), test_discovery_filters.py (5), test_discovery_matches.py (5), test_application_service.py (5), test_telegram_disc_webhook.py (6), test_goszakup_batch.py (5), test_poll_discovery.py (5)"
    why_human: "pytest требует запущенного PostgreSQL + Redis; тестовая БД недоступна из окружения верификатора"
  - test: "Проверить применённые Alembic-миграции к реальной БД"
    expected: "alembic current показывает '0007 (head)'"
    why_human: "Требует подключения к PostgreSQL"
  - test: "Проверить визуальный рендеринг фронтенда"
    expected: "Страница /discovery: пустое состояние с ссылкой 'Настройте фильтры'; при наличии матчей — карточки с бейджами статуса. Страница /discovery-filters: форма с полями ключевых слов/СПГЗ/региона/суммы. Sidebar: пункт 'Подборка' + ссылка 'Telegram бот' в нижней секции."
    why_human: "Требует запущенного dev-сервера Next.js"
  - test: "Проверить сквозной Telegram-flow"
    expected: "При наличии настроенного telegram_chat_id — пользователь получает карточку тендера с кнопками 'Участвуем' / 'Пропустить'; нажатие 'Участвуем' создаёт Application со статусом 'draft'; нажатие 'Пропустить' обновляет match.status='skipped'"
    why_human: "Требует реального Telegram-бота с валидным BOT_TOKEN и chat_id"
  - test: "Подтвердить предположение refEnstruCode для поля СПГЗ в goszakup Lots"
    expected: "Выполнить запрос query { __type(name: 'Lot') { fields { name } } } к live API goszakup и убедиться, что поле называется именно refEnstruCode; если нет — обновить _SPGZ_LOT_FIELD в goszakup_service.py"
    why_human: "Требует live API-соединения с goszakup.gov.kz + Bearer токена; из CI-окружения API недостижим"
---

# Phase 7: Discovery & Matching — Verification Report

**Phase Goal:** Users can configure keyword/region/category filters; the system periodically fetches new tenders from goszakup, matches them against each user's filters, and notifies via the existing Telegram bot — user clicks "Участвуем" to enter the Phase 5 submission pipeline.
**Verified:** 2026-07-20
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Пользователь может создать и обновить набор фильтров (ключевые слова, СПГЗ-коды, регион, сумма от/до) через UI | ✓ VERIFIED | `PUT /api/discovery/filters` в `discovery.py` (upsert с ON CONFLICT(user_id)), `ClientFilterCreate` с @field_validator, страница `/discovery-filters` с useMutation |
| 2 | ARQ-воркер опрашивает goszakup batch API каждые 15 минут и апсертит новые/изменённые тендеры в локальную БД | ✓ VERIFIED | `poll_goszakup_discovery` в `worker_settings.py` — `cron(poll_goszakup_discovery, minute={0,15,30,45}, unique=True)`; upsert через `pg_insert(Tender).on_conflict_do_update(index_elements=['number_anno'])` |
| 3 | Matching-воркер запускается после каждого poll и создаёт записи `tender_match` для пользователей, чьи фильтры совпали | ✓ VERIFIED | `run_matching` в `functions=[..., run_matching]`; вызов `match_tenders_for_user` + `pg_insert(TenderMatch).on_conflict_do_nothing(index_elements=['user_id','tender_id'])` |
| 4 | Пользователь видит ленту «Подборка» с совпавшими тендерами и статусами (Новый / Пропущен / Участвуем) | ✓ VERIFIED | `GET /api/discovery/matches` с JOIN на Tender; страница `/discovery/page.tsx` использует `useQuery(['discovery-matches'])`; `TenderMatchStatusBadge` отображает 4 статуса |
| 5 | При наличии telegram_chat_id пользователь получает карточку тендера с кнопками «Участвуем» / «Пропустить»; «Участвуем» создаёт заявку и включает Phase 5 pipeline | ✓ VERIFIED | `send_discovery_notification` отправляет `InlineKeyboardMarkup` с `disc:participate:{match_id}` и `disc:skip:{match_id}`; webhook guard `parts[0] not in ("confirm", "disc")`; `disc:participate` вызывает `create_discovery_draft` → Application(status='draft') |
| 6 | В боковом меню присутствует ссылка на Telegram-бот | ✓ VERIFIED | `Sidebar.tsx` добавлен `{ href: '/discovery', label: 'Подборка', icon: Sparkles }` и ссылка `https://t.me/${NEXT_PUBLIC_TELEGRAM_BOT_USERNAME}` |

**Score:** 6/6 truths verified

---

### Required Artifacts

| Artifact | Ожидание | Статус | Детали |
|----------|----------|--------|--------|
| `backend/alembic/versions/0005_extend_tenders_source_fields.py` | ADD COLUMN source/region/spgz_code | ✓ VERIFIED | Три колонки добавлены с правильными ограничениями; server_default='goszakup' для source |
| `backend/alembic/versions/0006_create_client_filters.py` | CREATE TABLE client_filters с UNIQUE(user_id) | ✓ VERIFIED | `uq_client_filters_user_id` создан; FK users.id ON DELETE CASCADE |
| `backend/alembic/versions/0007_create_tender_matches.py` | CREATE TABLE tender_matches с UNIQUE(user_id,tender_id) + 2 индекса | ✓ VERIFIED | `uq_tender_matches_user_tender`, `idx_tender_matches_user_id`, `idx_tender_matches_status` — все присутствуют |
| `backend/app/models/client_filter.py` | ClientFilter ORM, ARRAY(Text) keywords/spgz_codes | ✓ VERIFIED | Все колонки, FK, ARRAY(Text) |
| `backend/app/models/tender_match.py` | TenderMatch ORM, FK → users.id и tenders.id | ✓ VERIFIED | Оба FK с ON DELETE CASCADE; String(50) status; notified_at/decided_at |
| `backend/app/schemas/client_filter.py` | ClientFilterCreate (validator max 20 keywords) + ClientFilterResponse | ✓ VERIFIED | `@field_validator('keywords')` → ValidationError при len>20 (live-проверен) |
| `backend/app/schemas/tender_match.py` | TenderMatchResponse с денормализованными полями тендера | ✓ VERIFIED | tender_name_ru, customer_name_ru, total_sum, end_date, region — все nullable |
| `backend/app/services/goszakup_service.py` | fetch_tenders_batch с tenacity retry | ✓ VERIFIED | @retry(3 attempts, exponential 1-10s); BATCH_QUERY; клиентская фильтрация по lastUpdateDate |
| `backend/app/workers/tasks/poll_goszakup_discovery.py` | ARQ cron, Redis last_polled_at, upsert, enqueue run_matching | ✓ VERIFIED | LAST_POLLED_KEY="discovery:last_polled_at"; asyncio.sleep(0.5) между страницами; запись только после успешного upsert |
| `backend/app/services/matching_service.py` | match_tenders_for_user — ILIKE OR-join, region exact, spgz IN, amount range | ✓ VERIFIED | Все 5 типов фильтров реализованы; AND-логика между типами, OR — внутри keyword-списка |
| `backend/app/workers/tasks/run_matching.py` | ARQ on-demand task, ON CONFLICT DO NOTHING, D-03 guard | ✓ VERIFIED | `on_conflict_do_nothing(index_elements=['user_id','tender_id'])`; `if user.telegram_chat_id is not None` |
| `backend/app/workers/worker_settings.py` | 2 cron_jobs + 2 functions | ✓ VERIFIED | Live: `functions=['auto_submit_application','run_matching']`; `cron_jobs count: 2` |
| `backend/app/routers/discovery.py` | 5 эндпоинтов с IDOR-защитой | ✓ VERIFIED | GET/PUT filters, GET matches (WHERE user_id=current_user.id), POST participate/skip (404 на несовпадение) |
| `backend/app/main.py` | discovery.router зарегистрирован под /api | ✓ VERIFIED | `application.include_router(discovery.router, prefix="/api", tags=["discovery"])` |
| `backend/app/services/application_service.py` | create_discovery_draft (bypass Pydantic validator) | ✓ VERIFIED | Прямая конструкция `Application(lots_data=[], status='draft')` без ApplicationCreate |
| `backend/app/services/telegram_service.py` | send_discovery_notification + InlineKeyboard | ✓ VERIFIED | `InlineKeyboardMarkup([[InlineKeyboardButton("Участвуем", callback_data=f"disc:participate:{match_id}"), ...]])` |
| `backend/app/routers/telegram_webhook.py` | guard обновлён; disc:* handlers с IDOR | ✓ VERIFIED | `parts[0] not in ("confirm", "disc")`; IDOR через telegram_chat_id сравнение |
| `frontend/src/types/discovery.ts` | TenderMatchStatus, TenderMatchResponse, ClientFilterResponse | ✓ VERIFIED | Все типы определены, status type = 'matched' | 'notified' | 'skipped' | 'participating' |
| `frontend/src/components/discovery/TenderMatchStatusBadge.tsx` | 4 статуса с русскими метками и цветами | ✓ VERIFIED | matched→Новый(blue), notified→Уведомлён(amber), participating→Участвуем(green), skipped→Пропущен(gray) |
| `frontend/src/components/discovery/TenderMatchCard.tsx` | Кнопки скрыты при participating/skipped | ✓ VERIFIED | `isActionable = status !== 'participating' && status !== 'skipped'`; POST к /api/discovery/{id}/participate |
| `frontend/src/app/(dashboard)/discovery/page.tsx` | useQuery → discovery/matches; пустое состояние | ✓ VERIFIED | `queryFn: () => api.get('/api/discovery/matches')`; пустое состояние с ссылкой на /discovery-filters |
| `frontend/src/app/(dashboard)/discovery-filters/page.tsx` | useMutation → PUT discovery/filters; 'Фильтры сохранены' | ✓ VERIFIED | `mutation.mutate(...)` → `api.put('/api/discovery/filters', data)`; `setSaved(true)` + timeout 3s |
| `frontend/src/components/layout/Sidebar.tsx` | 'Подборка' + SparklesIcon + Telegram bot link | ✓ VERIFIED | `{ href: '/discovery', label: 'Подборка', icon: Sparkles }`; ссылка `https://t.me/${NEXT_PUBLIC_TELEGRAM_BOT_USERNAME}` в bottom section |
| `frontend/src/middleware.ts` | /discovery и /discovery-filters в protectedRoutes | ✓ VERIFIED | `const protectedRoutes = [..., '/discovery', '/discovery-filters']` |
| `frontend/.env.example` | NEXT_PUBLIC_TELEGRAM_BOT_USERNAME | ✓ VERIFIED | Строка присутствует |

---

### Key Link Verification

| From | To | Via | Статус | Детали |
|------|----|-----|--------|--------|
| `run_matching.py` | `matching_service.py` | `from app.services.matching_service import match_tenders_for_user` | ✓ WIRED | Прямой импорт на уровне модуля |
| `run_matching.py` | `telegram_service.py` | lazy import `send_discovery_notification` | ✓ WIRED | Внутри try-блока; lazy import documented (параллельное выполнение) |
| `poll_goszakup_discovery.py` | `goszakup_service.py` | `from app.services.goszakup_service import fetch_tenders_batch` | ✓ WIRED | Прямой импорт |
| `discovery.py` | `application_service.py` | lazy import `create_discovery_draft` | ✓ WIRED | `from app.services.application_service import create_discovery_draft` (внутри endpoint) |
| `discovery.py` | `main.py` | `app.include_router(discovery.router, prefix="/api")` | ✓ WIRED | Строка 84 main.py |
| `telegram_webhook.py` | `application_service.py` | `from app.services.application_service import create_discovery_draft` | ✓ WIRED | Модульный импорт (не lazy) — безопасно, 07-04 завершён до 07-05 |
| `telegram_webhook.py` | `tender_match` модель | `select(TenderMatch).where(TenderMatch.id == match_id)` | ✓ WIRED | `get_tender_match_by_id` helper |
| `TenderMatchCard.tsx` | `/api/discovery/{id}/participate` | `api.post('/api/discovery/${match.id}/participate', {})` | ✓ WIRED | useMutation в компоненте |
| `discovery/page.tsx` | `/api/discovery/matches` | `api.get('/api/discovery/matches')` | ✓ WIRED | useQuery с queryKey=['discovery-matches'] |
| `discovery-filters/page.tsx` | `/api/discovery/filters` | `api.put('/api/discovery/filters', data)` | ✓ WIRED | useMutation |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Источник | Реальные данные | Статус |
|----------|---------------|----------|-----------------|--------|
| `/discovery/page.tsx` | `data: TenderMatchResponse[]` | `GET /api/discovery/matches` → `get_matches()` → `SELECT TenderMatch JOIN Tender WHERE user_id=current_user.id` | PostgreSQL JOIN запрос | ✓ FLOWING |
| `/discovery-filters/page.tsx` | `currentFilter: ClientFilterResponse` | `GET /api/discovery/filters` → `select(ClientFilter).where(user_id=current_user.id)` | PostgreSQL запрос | ✓ FLOWING |
| `run_matching` → `TenderMatch` | `new_match_id` | `pg_insert(TenderMatch).on_conflict_do_nothing().returning(TenderMatch.id)` | INSERT с реальными данными | ✓ FLOWING |
| `poll_goszakup_discovery` → `Tender` | `upserted_ids` | `pg_insert(Tender).on_conflict_do_update().returning(Tender.id)` | goszakup GraphQL → PostgreSQL | ✓ FLOWING |

---

### Behavioral Spot-Checks

| Поведение | Команда | Результат | Статус |
|-----------|---------|-----------|--------|
| Импорт моделей и схем | `python3 -c "from app.models.client_filter import ClientFilter; from app.models.tender_match import TenderMatch; from app.schemas.client_filter import ClientFilterCreate, ClientFilterResponse; from app.schemas.tender_match import TenderMatchResponse; print('OK')"` | `models+schemas OK` | ✓ PASS |
| Импорт сервисов и воркеров | `python3 -c "from app.services.goszakup_service import fetch_tenders_batch; from app.workers.tasks.poll_goszakup_discovery import poll_goszakup_discovery; from app.services.matching_service import match_tenders_for_user; from app.workers.tasks.run_matching import run_matching; print('OK')"` | `services+workers OK` | ✓ PASS |
| Импорт роутера и сервисов Phase 5 | `python3 -c "from app.routers.discovery import router; from app.main import app; from app.services.application_service import create_discovery_draft, create_application; from app.services.telegram_service import send_tender_notification, send_discovery_notification; print('OK')"` | `router+services OK` | ✓ PASS |
| Валидатор keywords (DoS guard) | `python3 -c "from app.schemas.client_filter import ClientFilterCreate; ClientFilterCreate(keywords=['a']*21)"` | `pydantic_core.ValidationError` raised | ✓ PASS |
| WorkerSettings functions и cron_jobs | `python3 -c "from app.workers.worker_settings import WorkerSettings; print([f.__name__ for f in WorkerSettings.functions]); print(len(WorkerSettings.cron_jobs))"` | `['auto_submit_application', 'run_matching']`, `2` | ✓ PASS |

---

### Requirements Coverage

| Requirement | Исходный план | Описание | Статус | Свидетельство |
|-------------|--------------|----------|--------|---------------|
| DISC-01 | 07-01, 07-03, 07-05 | Фильтры: ключевые слова, СПГЗ, регион, сумма | ✓ SATISFIED | `ClientFilter` ORM + `ClientFilterCreate` schema + PUT /api/discovery/filters + /discovery-filters page |
| DISC-02 | 07-02, 07-03 | ARQ batch poll goszakup каждые 15 мин, ON CONFLICT DO UPDATE | ✓ SATISFIED | `poll_goszakup_discovery` cron(minute={0,15,30,45}, unique=True) + `_upsert_tenders` |
| DISC-03 | 07-01, 07-03 | Matching-воркер: tender_match записи (matched→notified→skipped|participating) | ✓ SATISFIED | `run_matching` + `match_tenders_for_user` + ON CONFLICT DO NOTHING + status machine |
| DISC-04 | 07-03, 07-05 | Лента «Подборка» с карточками | ✓ SATISFIED | GET /api/discovery/matches + /discovery page + TenderMatchCard + TenderMatchStatusBadge |
| DISC-05 | 07-04 | Telegram-уведомление + «Участвуем»/«Пропустить» buttons | ✓ SATISFIED | `send_discovery_notification` + `disc:*` handlers в telegram_webhook.py + `create_discovery_draft` |
| DISC-06 | 07-05 | Ссылка на Telegram-бот в боковом меню | ✓ SATISFIED | `Sidebar.tsx` external link с `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME` |

**Примечание по REQUIREMENTS.md:** DISC-01 через DISC-06 присутствуют в теле документа, но отсутствуют в таблице Traceability (в конце REQUIREMENTS.md). Кроме того, в ROADMAP.md таблица Progress показывает "0/6 | Planned" для Phase 7, хотя планы 07-01 – 07-05 помечены как `[x]` в разделе Phase Details. Это расхождение в документации, не в коде.

---

### Anti-Patterns Found

| Файл | Строка | Паттерн | Серьёзность | Влияние |
|------|--------|---------|-------------|---------|
| `backend/app/services/goszakup_service.py` | 80-99 | `ASSUMED: refEnstruCode` — поле СПГЗ в goszakup Lots не верифицировано via live API | ⚠️ WARNING | Если поле называется иначе, `spgz_code` всегда будет NULL → СПГЗ-фильтр тихо перестанет работать. Задокументировано как ACTION item с конкретными командами интроспекции. Колонка nullable — остальная функциональность не затронута. |

Маркеров TBD / FIXME / XXX ни в одном изменённом файле не найдено.

---

### Human Verification Required

#### 1. Полный тестовый набор pytest (41 тест)

**Тест:** `cd backend && pytest tests/test_matching_service.py tests/test_discovery_filters.py tests/test_discovery_matches.py tests/test_application_service.py tests/test_telegram_disc_webhook.py tests/test_goszakup_batch.py tests/test_poll_discovery.py -x -v`

**Ожидание:** 41 тест проходит без ошибок

**Почему требует человека:** Требует запущенного PostgreSQL + Redis + полной тестовой инфраструктуры. Из окружения верификатора недоступно.

---

#### 2. Alembic migration state

**Тест:** `cd backend && alembic current`

**Ожидание:** `0007 (head)`

**Почему требует человека:** Требует подключения к PostgreSQL.

---

#### 3. Фронтенд — визуальная проверка

**Тест:**
- Открыть `/discovery` без авторизации → ожидается редирект на `/login`
- Открыть `/discovery-filters` без авторизации → ожидается редирект на `/login`
- Авторизованный пользователь: `/discovery` → пустое состояние с "Настройте фильтры" link
- Авторизованный пользователь: `/discovery-filters` → форма фильтров, после Save → "Фильтры сохранены"
- Sidebar: виден пункт "Подборка" с иконкой Sparkles
- Sidebar (нижняя секция): виден пункт "Telegram бот" (требует NEXT_PUBLIC_TELEGRAM_BOT_USERNAME в .env.local)

**Ожидание:** Все 6 пунктов визуально работают

**Почему требует человека:** Требует запущенного dev-сервера Next.js.

---

#### 4. Telegram end-to-end flow

**Тест:**
- Убедиться, что у пользователя заполнен `telegram_chat_id` (Phase 6 /start flow)
- Дождаться следующего цикла poll (15 мин) или запустить вручную
- Проверить получение Telegram-карточки с кнопками "Участвуем" / "Пропустить"
- Нажать "Участвуем" → проверить создание Application со status='draft' в БД

**Ожидание:** Уведомление приходит; "Участвуем" создаёт Application; match.status='participating'

**Почему требует человека:** Требует Telegram Bot token, реального chat_id, и запущенного ARQ worker.

---

#### 5. Подтверждение поля СПГЗ в goszakup API

**Тест:** Выполнить GraphQL-запрос `query { __type(name: "Lot") { fields { name } } }` к `https://ows.goszakup.gov.kz/v3/graphql` с валидным Bearer-токеном

**Ожидание:** Поле `refEnstruCode` существует в типе `Lot`; если нет — найти правильное имя и обновить `_SPGZ_LOT_FIELD` в `goszakup_service.py`

**Почему требует человека:** Live API goszakup недостижим из CI/worktree окружения (сеть изолирована).

---

### Gaps Summary

**Блокеров нет.** Все 6 критериев успеха ROADMAP.md верифицированы кодом и live-импортами.

**Предупреждение (не блокер):** Поле `refEnstruCode` для СПГЗ-кода в goszakup Lots является ASSUMED (не подтверждено через live API introspection). Если поле называется иначе:
- `spgz_code` всегда будет NULL для всех тендеров
- СПГЗ-фильтр пользователей тихо перестанет работать
- Остальные фильтры (keywords, region, amount) не затронуты
- Колонка nullable → приложение не упадёт

Митигация: задокументировано в `goszakup_service.py` как `SPIKE-BATCH` comments с ACTION items. Рекомендуется выполнить introspection при первом доступном live-подключении к API.

**Документационные расхождения (INFO):**
- DISC-01 через DISC-06 отсутствуют в таблице Traceability в `REQUIREMENTS.md`
- DISC-01 через DISC-06 помечены `[ ]` (не выполнено) в теле `REQUIREMENTS.md`
- `ROADMAP.md` Progress Table показывает "0/6 | Planned" для Phase 7, хотя планы 07-01–07-05 отмечены `[x]` в Phase Details

Эти расхождения — в документации, не в коде. Код реализует все требования.

---

_Verified: 2026-07-20_
_Verifier: Claude (gsd-verifier)_
