---
phase: 03-tender-lookup
plan: 02
status: complete
completed: "2026-06-10"
---

# Plan 03-02 Summary — Wave 2: HTTP Routes + Integration Tests

## What Was Done

- Pydantic schemas (`TenderResponse`, `LotItem`, `WatchlistAddRequest`, `WatchlistEntryResponse`) созданы в `app/schemas/tender.py`.
- `WatchlistAddRequest` strip + max_length=100 через `@field_validator` без regex.
- `tender_service` расширен: `remove_from_watchlist` (IDOR-safe) + `list_watchlist` (selectinload).
- Роутер `app/routers/tenders.py` с 4 маршрутами, все auth-gated через `Depends(get_current_user)`.
- `main.py` подключает роутер с prefix `/api`.
- 6 route integration tests зелёных.
- Полный backend suite: **51 passed, 0 failed**.

---

## Endpoint Contracts

| Method | Path | Status | Notes |
|--------|------|--------|-------|
| GET | `/api/tenders/{number_anno}` | 200 / 404 | 401 без auth |
| POST | `/api/watchlist` | 201 / 404 | Idempotent (200/201 on duplicate) |
| DELETE | `/api/watchlist/{number_anno}` | 204 / 404 | IDOR-safe |
| GET | `/api/watchlist` | 200 | Список только текущего пользователя |

---

## IDOR Mitigation

`remove_from_watchlist` и `list_watchlist` принимают `user_id` из JWT (`current_user.id`),
никогда из тела запроса. DELETE фильтрует по `(user_id, tender_id)` — нельзя удалить
запись другого пользователя.

---

## Backend Test Summary

| Файл | Тестов | Статус |
|------|--------|--------|
| `test_tender_service.py` | 5 | passed |
| `test_tenders.py` | 6 | passed |
| Phase 2 тесты (auth, company, bin) | 40 | passed |
| **Итого** | **51** | ✅ |
