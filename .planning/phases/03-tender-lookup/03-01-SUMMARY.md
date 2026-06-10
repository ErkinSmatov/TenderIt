---
phase: 03-tender-lookup
plan: 01
status: complete
completed: "2026-06-10"
---

# Plan 03-01 Summary — Wave 1: Models + Service Layer

## What Was Done

- `settings.goszakup_api_token: str = ""` добавлен в Settings (пустой default → тесты без токена).
- `Tender` + `UserWatchlist` ORM-модели созданы с точным DDL из 03-CONTEXT.md:
  - JSONB: `lots_data`, `raw_data`
  - TIMESTAMPTZ: `start_date`, `end_date`, `publish_date`, `cached_at`, `created_at`
  - `UniqueConstraint("user_id", "tender_id", name="uq_user_watchlist")`
- `models/__init__.py` обновлён — alembic autogenerate видит оба класса.
- Миграция `0002_create_tenders_watchlist.py` создана: `down_revision = '861194df635a'`.
- `goszakup_service.fetch_tender_by_number_anno` реализован с httpx + tenacity:
  - Retry только на 5xx и сетевые ошибки (не 4xx).
  - 3 попытки, exponential back-off 1-10s.
  - Токен только из `settings.goszakup_api_token`.
- `tender_service.get_or_fetch_tender` реализован (cache-aside, 30-min TTL):
  - Свежий кэш → возврат без API-вызова.
  - Устаревший/отсутствующий → fetch + pg_insert ON CONFLICT DO UPDATE.
  - 404 (пустой массив) → return None, не кэшировать.
- `tender_service.add_to_watchlist` реализован (idempotent, ON CONFLICT DO NOTHING).
- 5 unit-тестов зелёных (respx + AsyncMock, без реального PostgreSQL).

---

## Service Function Contracts

| Функция | Сигнатура | Возвращает |
|---------|-----------|-----------|
| `fetch_tender_by_number_anno` | `(number_anno: str)` | `dict \| None` |
| `get_or_fetch_tender` | `(db: AsyncSession, number_anno: str)` | `Tender \| None` |
| `add_to_watchlist` | `(db: AsyncSession, user_id: int, number_anno: str)` | `UserWatchlist \| None` |

---

## Date Parsing

Формат из SPIKE-01: `"YYYY-MM-DD HH:MM:SS"` (пробел, без tz).
Функция `_parse_gz_date(value)` прикрепляет `timezone(timedelta(hours=5))` (Алматы UTC+5).
На ошибке парсинга возвращает `None` — никогда не кидает исключение.

---

## Retry Predicate

```python
def _is_retryable(exc):
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500  # ONLY 5xx
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    return False  # 4xx (401/403/404) → NO retry
```

---

## Model Column List

### Tender
`id, number_anno (unique, index), name_ru, name_kz, total_sum NUMERIC(18,2), customer_name_ru, customer_name_kz, status_id, status_name_ru, start_date TIMESTAMPTZ, end_date TIMESTAMPTZ, publish_date TIMESTAMPTZ, lots_data JSONB, raw_data JSONB, cached_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL`

### UserWatchlist
`id, user_id (FK users CASCADE), tender_id (FK tenders CASCADE), added_at TIMESTAMPTZ NOT NULL, notification_on BOOLEAN NOT NULL DEFAULT true, UNIQUE(user_id, tender_id) → uq_user_watchlist`

### Migration Revision ID
`0002` (down_revision: `861194df635a`)

---

## Test Results

```
5 passed in 0.07s
  test_fetch_tender_found       PASSED
  test_fetch_tender_not_found   PASSED
  test_cache_hit_skips_api      PASSED
  test_cache_stale_refetches    PASSED
  test_tender_response_schema   PASSED
```
