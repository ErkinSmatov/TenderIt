# SPIKE-01: goszakup GraphQL API Findings

**Date:** 2026-06-10
**Token obtained:** 2026-06-09 (1-year validity)
**Endpoint:** `https://ows.goszakup.gov.kz/v3/graphql`
**Test tender number used:** `17163708-1`

> **Wave 1 gate:** The `refBuyStatusId` value for "open for applications" in the
> **refBuyStatusId Reference** section below is **220**. Wave 1 is unblocked.
> Phase 5 ARQ polling logic depends on this value to detect when a tender opens.

---

## Token Status

- [x] Confirmed working — HTTP 200 returned, TrdBuy data in response

**Notes:** Минимальный запрос `{ __typename }` ответил за 0.42 сек. TrdBuy-запрос с вложенными Lots — за ~70 сек (требует таймаут 90s). Таймаут уже поднят в тесте до 90.0.

---

## Real numberAnno Format

**Raw value returned by API:** `"17163708-1"`

**Is it purely numeric?** No
**Pattern:** `{trd_buy_id}-{version_suffix}` — числовой ID тендера + дефис + числовой суффикс (обычно `1`)
**Max length observed:** 12 characters (`17163708-1`)

**Validation implication:**
Текущее решение (03-CONTEXT.md §3): любая непустая строка ≤ 100 символов, strip whitespace — **подходит без изменений**. Regex не нужен: формат `{digits}-{digits}` подтверждён, но вариации возможны.

**Важно для фронтенда:** пользователь должен вводить именно `17163708-1`, не просто `17163708`. Плейсхолдер в UI-SPEC (`"Например: 123456"`) нужно обновить на `"Например: 17163708-1"`.

---

## Date String Format

Raw values из реального TrdBuy-ответа:

| Field | Raw string value | Format |
|-------|-----------------|--------|
| `startDate` | `"2026-06-10 17:57:53"` | `YYYY-MM-DD HH:MM:SS` |
| `endDate` | `"2026-06-12 17:57:53"` | `YYYY-MM-DD HH:MM:SS` |
| `publishDate` | `"2026-06-10 17:57:53"` | `YYYY-MM-DD HH:MM:SS` |
| `lastUpdateDate` | `"2026-06-10 17:54:54"` | `YYYY-MM-DD HH:MM:SS` |

**Timezone:** Наивный (без суффикса tz). По контексту — Алматы UTC+5.

**⚠ Критическое отличие от ожидаемого:**
Даты — **НЕ ISO-8601**. Ожидался формат `"2026-06-10T00:00:00.000Z"`, пришёл `"2026-06-10 17:57:53"` (пробел вместо T, нет tz-суффикса).

**Parsing implication для Wave 1 Pydantic-валидатора:**
```python
# В TenderCreate/TenderResponse: поля дат объявить как Optional[datetime]
# Использовать @field_validator с явным парсингом:
from datetime import datetime, timezone, timedelta

ALMATY_TZ = timezone(timedelta(hours=5))

@field_validator("start_date", "end_date", "publish_date", mode="before")
@classmethod
def parse_goszakup_date(cls, v):
    if v is None:
        return None
    # Формат: "YYYY-MM-DD HH:MM:SS" (наивный, UTC+5)
    dt = datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=ALMATY_TZ)
```

---

## refBuyStatusId Reference

> **GATE CLEARED.** Значение для "открытого" тендера: `refBuyStatusId = 220`

| `refBuyStatusId` | `RefBuyStatus.nameRu` | `RefBuyStatus.code` | Meaning |
|------------------|-----------------------|---------------------|---------|
| **220** | **"Опубликовано (прием заявок)"** | **`PublishedOrderTaking`** | **← OPEN: прием заявок. Это значение Phase 5 опрашивает** |
| 220 (Lot) | — | — | `refLotStatusId` для лота тоже 220 при открытом тендере |

**Замечание:** В CONTEXT.md и документации портала это состояние называлось `"Принимаются заявки"`, фактическое `nameRu` — `"Опубликовано (прием заявок)"`. Оба описывают одно: тендер открыт для подачи заявок. Код `PublishedOrderTaking` — каноническое название.

**Для Phase 5 ARQ-поллинга:**
```python
OPEN_FOR_APPLICATIONS_STATUS_ID = 220  # "Опубликовано (прием заявок)" / PublishedOrderTaking
```

**Дополнительные статусы:** наблюдался только 220. Другие значения (завершён, отменён и т.д.) необходимо документировать при встрече.

---

## Nullable Fields

**Обнаружены null-поля в реальном ответе:**

| Поле | Значение | Примечание |
|------|---------|-----------|
| `customerNameRu` | `null` | Несмотря на наличие `customerBin`, имя заказчика отсутствует — поле Optional |
| `customerNameKz` | `null` | Аналогично |
| `nameKz` | заполнено | В данном тендере есть |

**Implication для модели `Tender` в Wave 1:**
`customer_name_ru`, `customer_name_kz` — `VARCHAR(500) NULL` (уже так в DDL из CONTEXT.md — всё верно).

---

## Redacted Sample Response

```json
{
  "data": {
    "TrdBuy": [
      {
        "id": 17163708,
        "numberAnno": "17163708-1",
        "nameRu": "Услуги по техническому обслуживанию пожарной сигнализации и речевого оповещения всех объектов университета",
        "nameKz": "Университеттің барлық нысандарына техникалық қызмет көрсету өрт дабылы және сөйлеу құлақтандыру қызметтері",
        "totalSum": 24180000,
        "countLots": 1,
        "customerBin": "<REDACTED>",
        "customerNameRu": null,
        "customerNameKz": null,
        "refBuyStatusId": 220,
        "RefBuyStatus": {
          "id": 220,
          "nameRu": "Опубликовано (прием заявок)",
          "nameKz": "Жарияланды (өтінімді қабылдау)",
          "code": "PublishedOrderTaking"
        },
        "startDate": "2026-06-10 17:57:53",
        "endDate": "2026-06-12 17:57:53",
        "publishDate": "2026-06-10 17:57:53",
        "lastUpdateDate": "2026-06-10 17:54:54",
        "Lots": [
          {
            "id": 42212976,
            "lotNumber": "81638850-ОИ2",
            "nameRu": "Услуги по техническому обслуживанию пожарной/охранной сигнализации/систем тушения/видеонаблюдения и аналогичного оборудования",
            "nameKz": "Өрт/күзеттік хабарлағышты/өрт сөндіру/бейнебақылау жүйелерін және ұқаса жабдықтауды техникалық қамтамасыз ету бойынша қызмет көрсетулер",
            "descriptionRu": "Услуги по техническому обслуживанию пожарной/охранной сигнализации/систем тушения/видеонаблюдения и аналогичного оборудования",
            "amount": 24180000,
            "refLotStatusId": 220
          }
        ]
      }
    ]
  }
}
```

---

## Open Questions After Spike

- [ ] Какие другие `refBuyStatusId` существуют (завершён, отменён, черновик)? Встречать по ходу работы.
- [x] ~~Часовой пояс дат~~ — наивный формат `YYYY-MM-DD HH:MM:SS`, предположительно UTC+5 (Алматы).
- [x] ~~Формат numberAnno~~ — `{id}-{suffix}`, например `17163708-1`.
- [ ] `totalSum` — в ответе `integer`, в документации `Float`. Проверить с тендером где сумма дробная. Wave 1 хранит как `NUMERIC(18,2)` — безопасно.

---

## Sign-Off

- [x] Все пять секций заполнены
- [x] `refBuyStatusId = 220` для "Принимаются заявки" / "PublishedOrderTaking" записан
- [x] `customerBin` заменён на `<REDACTED>`
- [x] Токен нигде в файле не фигурирует
- [x] Wave 1 разблокирован
