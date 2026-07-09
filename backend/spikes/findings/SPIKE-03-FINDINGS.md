# SPIKE-03: goszakup.gov.kz Tender Application Submission — Findings

**Status:** COMPLETE — заполнено из HAR-захвата реального флоу

---

## Spike Metadata

| Field | Value |
|-------|-------|
| Date captured | 2026-07-09 |
| Captured by | Аккаунт поставщика (ИП/ТОО) |
| goszakup account type | Supplier (поставщик) |
| Tender type used for testing | ЗЦП, tenderBuyId=17269797 |
| Capture method | Chrome DevTools → Export HAR |
| goszakup portal version | v3 (v3bl.goszakup.gov.kz) |
| API base observed | `v3bl.goszakup.gov.kz` |

---

## КРИТИЧЕСКИЕ НАХОДКИ

### 1. Аутентификация — НЕ Bearer token. Это сессия + CSRF.

Никаких `Authorization: Bearer` заголовков нет. Каждый запрос использует:
- **Session cookie** (PHPSESSID) — PHP сессия, живёт ~8-24 часа
- **CSRF token** — передаётся в теле каждого запроса как `csrf=...`
- **Content-Type:** `application/x-www-form-urlencoded` (не JSON!)

**Вывод:** Сценарий **B** из D-05-02 подтверждён. Backend должен хранить `{phpsessid, csrf}` для авто-сабмита через ARQ.

### 2. Цена шифруется через NCALayer — это Гамма-шифрование (sealed bid)

Это главная неожиданность. Гозакуп использует **"Гамма-шифрование"** — sealed bid механизм. Цена подаётся в зашифрованном виде, никто (включая портал) не видит её до закрытия тендера. NCALayer вызывается дважды:
1. **Шифрование цены** (CMS encryption) — `encryptedData + sessionKey + salt + info + sign`
2. **GOST подпись** зашифрованных данных — `signData` (PKCS#7/CMS блоб)

**Нет отдельного "unsigned XML" для подписания.** Портал управляет XML внутри; мы работаем с зашифрованной ценой.

### 3. Финальный сабмит — один POST запрос с сессионной кукой

`POST /ru/application/ajax_public_application/{tenderBuyId}/{applicationId}` с `public_app=Y`.
Не требует NCALayer — только живую сессию. Это и есть точка, где ARQ завершает авто-сабмит.

---

## Application Flow — Полный флоу (из HAR)

URL-паттерн: `https://v3bl.goszakup.gov.kz/ru/application/{action}/{tenderBuyId}/{applicationId}`

| # | URL | Метод | Тело | Ответ |
|---|-----|-------|------|-------|
| 1 | `/ru/application/ajax_create_application/17269797` | POST | `csrf=...&subject_address=639347&iik=1791326&contact_phone=204223&tax_payer_type=UL` | `{"id":71931023}` (applicationId) |
| 2 | `/ru/application/ajax_add_lots/17269797/71931023` | POST | `csrf=...&selectLots[]=42460233` | HTTP 200, text/html |
| 3 | `/ru/application/ajax_lots_next/17269797/71931023` | POST | `next=1&confirmed=0&csrf=...` | HTTP 200, text/html |
| 4 | `/ru/beneficiary/ajax_save_info` | POST | `csrf=...&beneficiary_name=...&citizenship=398&res_country=398&beneficiary_doc_number=...&beneficiary_doc_date=2026-07-01&option_1=1&option_2=1&option_3=1&option_4=2&app_lot_id=86257005` | `{"status":"ok","..."}` |
| 5 | `/ru/application/ajax_docs_next/17269797/71931023` | POST | `next=1&csrf=...` | HTTP 200, text/html |
| 6 | `/ru/application/ajax_get_encr_info/17269797/71931023` | POST | `lpId=41914081&version=1.0.13.2287&csrf=...` | JSON с параметрами шифрования |
| 7 | *(NCALayer WS: шифровать цену)* | WS | — | `{encryptedData, sessionKey, salt, info, sign}` |
| 8 | `/ru/application/ajax_add_encrypt/17269797/71931023` | POST | `itemID=41914081&encryptedData=bR41xz...&sessionKey=...&salt=...&info=...&sign=...&csrf=...` | `{"status":"ok"}` |
| 9 | *(NCALayer WS: GOST подписать зашифр. данные)* | WS | — | `signData=MIIP8gYJKoZIhvcNA...` (PKCS#7) |
| 10 | `/ru/application/ajax_save_gamma_signs/17269797/71931023` | POST | `xmlData[41914081]=bR41xz...&signData[41914081]=MIIP8gYJKoZIhvcNA...&csrf=...` | `{"status":"ok"}` |
| 11 | `/ru/application/ajax_priceoffers_next/17269797/71931023` | POST | `csrf=...&offer[86257005][41914081][price]=bR41xz...&is_construction_pilot=` | HTTP 200, text/html |
| 12 | `/ru/application/ajax_public_application/17269797/71931023` | POST | `public_app=Y&agree_price=false&agree_contract_project=false&agree_covid19=false&csrf=...` | `{"status":"error","message":"налоговая задолженность..."}` ← бизнес-ошибка, не технический блок |

**Примечание по шагу 12:** Ошибка — не технический блок. Портал принял запрос, просто требует актуальную справку о налоговой задолженности. Финальный эндпойнт подтверждён.

---

## ID-маппинг

| ID | Откуда | Пример |
|----|--------|--------|
| `tenderBuyId` | goszakup API (из нашего `tenders` table) | 17269797 |
| `applicationId` | Ответ `ajax_create_application` | 71931023 |
| `lotId` | ID лота в тендере (selectLots[]) | 42460233 |
| `app_lot_id` | ID лот-заявки (создаётся при add_lots) | 86257005 — нужен для beneficiary и price |
| `lpId` / `itemID` | ID позиции цены в лоте | 41914081 — нужен для шифрования |

---

## Эндпойнты (итоговая структура)

### Создать черновик
```
POST /ru/application/ajax_create_application/{tenderBuyId}
Content-Type: application/x-www-form-urlencoded
Body: csrf=...&subject_address={supplierAddressId}&iik={iin}&contact_phone={phone}&tax_payer_type=UL
Response: {"id": <applicationId>}
```

### Добавить лоты
```
POST /ru/application/ajax_add_lots/{tenderBuyId}/{applicationId}
Body: csrf=...&selectLots[]={lotId}&selectLots[]={lotId2}...
```

### Подтвердить лоты
```
POST /ru/application/ajax_lots_next/{tenderBuyId}/{applicationId}
Body: next=1&confirmed=0&csrf=...
```

### Бенефициар (per лот)
```
POST /ru/beneficiary/ajax_save_info
Body: csrf=...&beneficiary_name=...&citizenship=398&res_country=398&beneficiary_doc_number=...
      &beneficiary_doc_date=YYYY-MM-DD&option_1=1&option_2=1&option_3=1&option_4=2
      &app_lot_id={app_lot_id}&beneficiary_id=
```

### Завершить шаг документов
```
POST /ru/application/ajax_docs_next/{tenderBuyId}/{applicationId}
Body: next=1&csrf=...
```

### Получить параметры шифрования (вызывается браузером перед NCALayer)
```
POST /ru/application/ajax_get_encr_info/{tenderBuyId}/{applicationId}
Body: lpId={lpId}&version={ncalayer_version}&csrf=...
Response: JSON с параметрами шифрования (publicKey и т.д.)
```

### Сохранить зашифрованную цену (после NCALayer CMS encryption)
```
POST /ru/application/ajax_add_encrypt/{tenderBuyId}/{applicationId}
Body: itemID={lpId}&encryptedData={encrypted_price}&sessionKey={...}&salt={...}&info={...}&sign={...}&csrf=...
```

### Сохранить GOST подпись (после NCALayer GOST sign)
```
POST /ru/application/ajax_save_gamma_signs/{tenderBuyId}/{applicationId}
Body: xmlData[{lpId}]={encryptedData}&signData[{lpId}]={pkcs7_cms_blob}&csrf=...
```

### Завершить шаг цены
```
POST /ru/application/ajax_priceoffers_next/{tenderBuyId}/{applicationId}
Body: csrf=...&offer[{app_lot_id}][{lpId}][price]={encryptedData}&is_construction_pilot=
```

### ★ ФИНАЛЬНЫЙ САБМИТ (вызывается ARQ)
```
POST /ru/application/ajax_public_application/{tenderBuyId}/{applicationId}
Content-Type: application/x-www-form-urlencoded
Cookie: PHPSESSID={session}
Body: public_app=Y&agree_price=false&agree_contract_project=false&agree_covid19=false&csrf={csrf}

Response success: {"status":"ok", ...}
Response error:   {"status":"error","message":"..."}
```

---

## Ответы портала

### Успех (шаг 12, ожидаемый)
```json
{"status": "ok"}
```
(Полный success ответ не захвачен — финальный тест был остановлен бизнес-ошибкой о налогах)

### Ошибка (захваченная)
```json
{
  "status": "error",
  "debtor": 0,
  "message": "Для подачи заявки на участие в закупке 17269797-1 необходимо иметь актуальные запрошенные сведения о налоговой задолженности..."
}
```

---

## Подпись — GOST 2022 подтверждён

В `signData` из шага 10 закодирован PKCS#7 конверт начинающийся с `MIIP8gYJKoZIhvcNA...`. В embedded сертификате явно присутствует GOST. Значит **D-S02-05** (pyhanko + GOST) актуален для v2.

---

## Документы — статус захвата

Документы не были приложены в тестовом флоу (шаг "show_doc" был пройден без загрузки файлов). Страница показывает документы по URL `/ru/application/show_doc/{tenderBuyId}/{applicationId}/{lotId}/{app_lot_id}`. Для MVP документы в Document Vault TenderIt могут прикрепляться **до** этого шага через стандартный загрузчик портала, либо через отдельный эндпойнт (требует дополнительного теста).

---

## DECISIONS

### D-S03-01: XML шаблон — НЕ НУЖЕН

- **EVIDENCE:** Нет шага "получить unsigned XML" — портал использует Гамма-шифрование цены
- **DECISION:** Jinja2 XML шаблон не нужен. Портал генерирует XML внутренне.
- **STATUS:** CONFIRMED

### D-S03-02: Encoding

- **EVIDENCE:** Все запросы `application/x-www-form-urlencoded`, ответы `application/json` UTF-8
- **DECISION:** UTF-8 для всех запросов
- **STATUS:** CONFIRMED

### D-S03-03: Прикрепление документов

- **EVIDENCE:** Не захвачено в тесте
- **DECISION:** TBD — требует отдельного теста. Предположительно через `/ru/application/show_doc/...` страницу
- **STATUS:** OPEN — не блокирует MVP если документы прикрепляются вручную на портале

### D-S03-04: Авто-сабмит архитектура — Вариант 2

- **EVIDENCE:** Финальный сабмит = один POST с session cookie и CSRF. NCALayer не нужен на шаге submit.
- **DECISION:** Браузер выполняет шаги 1-11. Backend хранит `{phpsessid, csrf, applicationId}` в Redis. ARQ вызывает шаг 12 при status_id == 220.
- **STATUS:** CONFIRMED

---

## Security Notes

| Threat | Mitigation |
|--------|-----------|
| HAR содержит session cookies | `raw-captures/` gitignored; только анонимизированные findings в git |
| BIN/IIN в тесте | Заменены placeholder-значениями в этом документе |
| Хранение session cookie в Redis | TTL <= 20h, зашифровать at-rest (v2); refresh flow при истечении |

---

*SPIKE-03 закрыт: 2026-07-09. Все `[TO FILL]` сняты. Готово для /gsd-plan-phase 5.*
