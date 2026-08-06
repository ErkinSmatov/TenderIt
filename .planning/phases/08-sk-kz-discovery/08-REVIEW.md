---
phase: 08-sk-kz-discovery
reviewed: 2026-08-06T12:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - backend/app/services/sk_kz_service.py
  - backend/app/workers/tasks/poll_sk_kz_discovery.py
  - backend/app/services/telegram_service.py
  - backend/app/workers/tasks/run_matching.py
  - backend/app/schemas/tender_match.py
  - backend/app/routers/discovery.py
  - backend/tests/test_discovery_matches.py
  - backend/tests/test_sk_kz_service.py
  - backend/tests/test_poll_sk_kz_discovery.py
  - backend/app/workers/worker_settings.py
  - frontend/src/types/discovery.ts
  - frontend/src/components/discovery/TenderMatchCard.tsx
findings:
  critical: 1
  warning: 6
  info: 4
  total: 11
status: issues_found
---

# Phase 8: Code Review Report

**Reviewed:** 2026-08-06T12:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Ревью охватывает весь стек фазы 8: REST-клиент zakup.sk.kz, ARQ-задачи, маршруты discovery,
Pydantic-схемы и фронтенд-компонент. Реализация в целом грамотная: правильный IDOR-контроль,
ON CONFLICT идемпотентность, защита от инъекции в Telegram-сообщении через явный `source_label`.

Найден один блокирующий дефект: отсутствие проверки типа ответа от внешнего API перед итерацией —
нестандартный ответ от zakup.sk.kz обрушит ARQ-воркер через `AttributeError`.
Также найдены шесть предупреждений, включая потенциальную потерю данных при первом запуске,
дублирование функции `_portal_url` в двух модулях и отсутствие обработки ошибок мутаций
на фронтенде.

---

## Critical Issues

### CR-01: `fetch_sk_tenders_page` не проверяет тип ответа перед итерацией

**File:** `backend/app/services/sk_kz_service.py:116-121`

**Issue:** После `response.raise_for_status()` код делает предположение, что тело ответа
является JSON-массивом и сразу итерирует его:

```python
items: list[dict] = response.json()
return [item for item in items if _item_updated_since(item, since)]
```

Если zakup.sk.kz вернёт объект вместо массива (например, сообщение о технических работах
`{"message": "Service unavailable"}`, 200 OK от CDN-прокси, или пустой ответ `null`),
то `for item in items` будет итерировать по ключам словаря (строки вместо dict),
и первый же вызов `_item_updated_since(item, since)` упадёт с:

```
AttributeError: 'str' object has no attribute 'get'
```

Исключение пробросится наружу без перехвата, завершит выполнение ARQ-задачи
`poll_sk_kz_discovery` и — при достаточном количестве повторов — заблокирует воркер.
Это реалистичный сценарий: публичные API часто отдают объект ошибки с HTTP 200.

**Fix:**
```python
items = response.json()

if not isinstance(items, list):
    logger.error(
        "sk.kz filter returned unexpected type %s (expected list): %r",
        type(items).__name__,
        str(items)[:200],
    )
    return []

return [item for item in items if _item_updated_since(item, since)]
```

---

## Warnings

### WR-01: Потеря данных при первом запуске — только первая страница из 24-часового окна

**File:** `backend/app/workers/tasks/poll_sk_kz_discovery.py:68-70`

**Issue:** Первый запуск задачи использует DEFAULT_LOOKBACK_HOURS=24, а затем читает
только `page=0` (50 тендеров). Сразу после обработки метка времени в Redis сдвигается
в `now()`. Если za 24 часа появилось более 50 тендеров, страницы 1+ никогда не будут
обработаны: следующий опрос начнётся уже с текущего момента и минует их насовсем.

Комментарий «`<50 new tenders is realistic`» справедлив для 15-минутного интервала,
но не для 24-часового окна при первом запуске или при восстановлении после длительного
простоя.

**Fix:** Добавить пагинационный цикл с ранним выходом:

```python
page = 0
all_tender_dicts: list[dict] = []
while True:
    page_items = await fetch_sk_tenders_page(since, page=page, size=_PAGE_SIZE)
    if not page_items:
        break
    all_tender_dicts.extend(page_items)
    if len(page_items) < _PAGE_SIZE:
        # Последняя страница — дальше нет новых тендеров
        break
    page += 1
```

Если полный цикл слишком затратен для штатного режима (15 мин), можно ограничить
количество страниц константой `MAX_PAGES = 5`.

---

### WR-02: Неиспользуемый импорт `parse_sk_date` и импорт приватной функции `_map_sk_tender`

**File:** `backend/app/workers/tasks/poll_sk_kz_discovery.py:31`

**Issue:**

```python
from app.services.sk_kz_service import fetch_sk_tenders_page, parse_sk_date, _map_sk_tender
```

`parse_sk_date` нигде не вызывается в этом модуле — это мёртвый импорт.

`_map_sk_tender` — приватная функция (префикс `_`), использование которой за пределами
своего модуля нарушает контракт публичного API. Если сигнатура или семантика функции
изменится, рефакторинг-инструменты могут пропустить этот импорт.

**Fix:**
1. Удалить `parse_sk_date` из строки импорта.
2. Переименовать `_map_sk_tender` в `map_sk_tender` (убрать `_`) в `sk_kz_service.py`,
   обновить импорт и все внутренние вызовы.

---

### WR-03: Дублирование функции `_portal_url` в двух несвязанных модулях

**File:** `backend/app/workers/tasks/run_matching.py:41-49`
**File:** `backend/app/routers/discovery.py:52-61`

**Issue:** Одинаковая функция определена в двух местах. При изменении URL-паттерна sk.kz
потребуется обновить оба файла — и есть риск рассинхронизации. Текущие версии уже
содержат разные docstring-комментарии («Confirmed» vs. «Assumed»), что указывает на
начало дивергенции.

**Fix:** Вынести в общий модуль:

```python
# backend/app/services/portal_urls.py
def portal_url(source: str | None, number_anno: str | None) -> str | None:
    """Compute the public portal URL for a tender based on its source."""
    if source == "sk_kz" and number_anno:
        return f"https://zakup.sk.kz/eprocsearch/tender/{number_anno}"
    return None
```

Импортировать из обоих мест: `from app.services.portal_urls import portal_url`.

---

### WR-04: Lazy-импорты внутри внутреннего цикла `for tender_id` в `run_matching.py`

**File:** `backend/app/workers/tasks/run_matching.py:145-149`

**Issue:**

```python
for tender_id in matching_ids:
    ...
    try:
        from app.config import settings
        from app.services.telegram_service import (
            send_discovery_notification,
        )
```

`from ... import ...` исполняется при каждой итерации внутреннего цикла.
Python кэширует модули в `sys.modules`, поэтому повторной загрузки не будет,
но каждая итерация всё равно выполняет поиск в `sys.modules` и привязку имени.
При больших объёмах (N фильтров × M тендеров) это добавляет ненужную работу.
Комментарий о «parallel worktree ImportError» уже не актуален: к моменту выполнения
задачи оба плана смёрджены.

**Fix:** Переместить импорты за пределы циклов — в начало функции `run_matching` или
хотя бы за пределы внешнего цикла `for cf in filters`:

```python
async def run_matching(ctx: dict, new_tender_ids: list[int]) -> None:
    from app.config import settings
    from app.services.telegram_service import send_discovery_notification
    ...
```

---

### WR-05: Отсутствуют обработчики `onError` у всех трёх мутаций в `TenderMatchCard`

**File:** `frontend/src/components/discovery/TenderMatchCard.tsx:71-91`

**Issue:** `participateMutation`, `skipMutation` и `deleteMutation` не определяют
`onError`. При сетевой ошибке, 409 Conflict, 404 или 500 с сервера пользователь
не получает никакой обратной связи — кнопка просто перестаёт быть активной (`isPending`
сбрасывается) и UI остаётся в прежнем состоянии без объяснений.

Для `participateMutation` это особенно критично: навигация `router.push(...)` не
выполнится при ошибке, но пользователь не поймёт, что произошло.

**Fix:**

```typescript
const participateMutation = useMutation({
  mutationFn: () =>
    api.post<ApplicationResponse>(`/api/discovery/${match.id}/participate`, {}),
  onSuccess: (data) => {
    router.push(`/applications/${data.id}`)
  },
  onError: (err) => {
    // Показать toast / alert; пример с console.error как минимум:
    console.error('Ошибка при подаче заявки:', err)
    // TODO: заменить на toast('Не удалось подать заявку. Попробуйте снова.')
  },
})
```

Аналогично для `skipMutation` и `deleteMutation`.

---

### WR-06: `isActionable`, `showParticipate`, `showSkip` — три идентичных булевых выражения

**File:** `frontend/src/components/discovery/TenderMatchCard.tsx:93-95`

**Issue:**

```typescript
const isActionable  = match.status !== 'participating' && match.status !== 'skipped'
const showParticipate = match.status !== 'participating' && match.status !== 'skipped'
const showSkip      = match.status !== 'skipped' && match.status !== 'participating'
```

Все три переменные тождественны. Структура кода предполагает намерение иметь разные
условия (например, скрывать «Пропустить» для уже участвующих, но показывать другие
кнопки), однако это намерение не реализовано. Это либо нераскрытая логика, либо
мёртвый код.

**Fix — вариант A (просто убрать дублирование):**
```typescript
const isActionable = match.status !== 'participating' && match.status !== 'skipped'
// showParticipate и showSkip заменить на isActionable везде в JSX
```

**Fix — вариант B (если нужна разная видимость кнопок):**
```typescript
const showParticipate = match.status !== 'participating' && match.status !== 'skipped'
const showSkip        = match.status !== 'skipped'  // Показывать даже для 'participating'?
```

Определить правильное поведение и привести код в соответствие.

---

## Info

### IN-01: Неиспользуемый комментарий «early-stop» не соответствует реализации

**File:** `backend/app/services/sk_kz_service.py:118-121`

**Issue:** Комментарий утверждает «Early-stop rationale: once an item is older than
`since`, all remaining items are also older», но никакого ранней остановки в коде нет —
list comprehension проходит по всем элементам. Это не функциональная ошибка (поведение
правильное), но вводит в заблуждение при чтении.

**Fix:** Удалить или исправить комментарий:
```python
# Items are sorted by lastModifiedDate desc; filter keeps only items >= since.
return [item for item in items if _item_updated_since(item, since)]
```

---

### IN-02: `status: str` в схеме — нет валидации по допустимым значениям

**File:** `backend/app/schemas/tender_match.py:37`

**Issue:** `status: str` принимает любую строку. В проекте уже есть прецедент
использования `Literal` (см. `ExpiryStatus` в `document.py`). Неверный статус,
попавший в ответ, пройдёт сериализацию без ошибки.

**Fix:**
```python
from typing import Literal

status: Literal['matched', 'notified', 'participating', 'skipped']
```

---

### IN-03: Устаревший docstring в `run_matching.py`

**File:** `backend/app/workers/tasks/run_matching.py:64-67`

**Issue:** Docstring функции `run_matching` и строка 6 файла указывают:
«Called by poll_goszakup_discovery after each successful upsert batch».
После фазы 8 её также вызывает `poll_sk_kz_discovery`. Документация устарела.

**Fix:** Обновить docstring:
```
Called by poll_goszakup_discovery and poll_sk_kz_discovery after each successful upsert batch.
```

---

### IN-04: `_get_user_id_from_client` в тестах возвращает последнего пользователя в БД, а не пользователя переданного клиента

**File:** `backend/tests/test_discovery_matches.py:109-120`

**Issue:** Функция заявляет «Get the user_id of the authenticated client», но реально
делает `SELECT ... ORDER BY User.id DESC LIMIT 1` — возвращает последнего созданного
пользователя в базе. Если между вызовом `_register_and_login` и
`_get_user_id_from_client` появится другой пользователь (параллельный тест),
функция вернёт неправильный ID. IDOR-тесты могут давать ложноположительный результат.

**Fix:** Извлекать `user_id` из JWT-токена, возвращённого при регистрации/логине:

```python
async def _register_and_login(prefix: str) -> tuple[AsyncClient, int]:
    """Create a fresh authenticated AsyncClient; return (client, user_id)."""
    ac = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
        resp = await ac.post(
            "/api/auth/register",
            json={"email": email, "password": "SecurePass123!"},
        )
    assert resp.status_code == 201
    user_id: int = resp.json()["user_id"]  # или декодировать JWT
    return ac, user_id
```

---

_Reviewed: 2026-08-06T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
