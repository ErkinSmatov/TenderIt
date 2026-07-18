# TenderIt — Requirements v1

## v1 Requirements

### Authentication (AUTH)

- [ ] **AUTH-01**: Пользователь может зарегистрироваться с email и паролем
- [ ] **AUTH-02**: Пользователь может войти в систему и оставаться авторизованным между сессиями
- [ ] **AUTH-03**: Пользователь может сбросить пароль через email-ссылку
- [ ] **AUTH-04**: Пользователь может выйти из системы

### Company Profile (COMP)

- [ ] **COMP-01**: Пользователь может заполнить профиль компании: БИН, название, юридический адрес
- [ ] **COMP-02**: Пользователь может редактировать профиль компании в любое время

### Tender Lookup (SRCH)

- [ ] **SRCH-01**: Пользователь может найти тендер по номеру объявления (tenderID) через поле поиска
- [ ] **SRCH-02**: Система загружает данные тендера из goszakup.kz через Унифицированные сервисы API (токен получен, SPIKE-01 закрыт)
- [ ] **SRCH-03**: Пользователь видит карточку тендера: название, лот, заказчик, сумма, дедлайн, текущий статус тендера
- [ ] **SRCH-04**: Пользователь может добавить тендер в watchlist (список отслеживаемых) для подготовки заявки и авто-подачи

### Document Vault (DOCS)

- [ ] **DOCS-01**: Пользователь может загрузить документ компании (PDF, DOCX, любой формат)
- [ ] **DOCS-02**: Пользователь может назначить категорию документу (устав, лицензия, сертификат, свидетельство о регистрации, прочее)
- [ ] **DOCS-03**: Пользователь может указать срок действия документа и получать предупреждение за 14 и 7 дней до истечения
- [ ] **DOCS-04**: Пользователь может удалить документ из хранилища
- [ ] **DOCS-05**: Система автоматически подставляет актуальные документы компании при создании черновика заявки

### EDS Signing — NCALayer (SIGN)

- [ ] **SIGN-01**: Система проверяет доступность NCALayer (ws://localhost:14579) перед началом подписания и показывает понятный индикатор статуса
- [ ] **SIGN-02**: Система отображает данные сертификата ЭЦП (владелец, срок действия) до подписания
- [ ] **SIGN-03**: Система предупреждает пользователя, если сертификат ЭЦП истекает менее чем через 30 дней
- [ ] **SIGN-04**: Пользователь может подписать заявку через NCALayer (ввод PIN → NCALayer возвращает подписанный XML)
- [ ] **SIGN-05**: Система показывает инструкцию по установке NCALayer, если он не запущен

### Application Submission (APPL)

- [ ] **APPL-01**: Пользователь может создать черновик заявки на выбранный тендер
- [ ] **APPL-02**: Пользователь может просмотреть список документов, которые будут включены в заявку, до подписания
- [x] **APPL-03**: После подписания система автоматически отправляет заявку на портал через API
- [x] **APPL-04**: Пользователь видит статус заявки: Черновик → Подписано → Отправляется → Отправлено / Ошибка
- [x] **APPL-05**: Пользователь видит историю всех поданных заявок
- [x] **APPL-06**: Система уведомляет пользователя в UI, если автоматическая отправка завершилась ошибкой, с объяснением причины
- [ ] **APPL-07**: Система периодически опрашивает goszakup API и отслеживает статус каждого тендера в watchlist (ARQ polling job)
- [ ] **APPL-08**: Когда тендер переходит в статус «открыт для подачи заявок», система немедленно отправляет уведомление пользователю в Telegram/WhatsApp: «Тендер №{ID} открыт. Подаём заявку? [Да] [Нет]»
- [ ] **APPL-09**: Если пользователь нажал «Да» — заявка подаётся автоматически; если «Нет» — заявка отменяется; если ответа нет в течение 15 минут — заявка подаётся автоматически (fallback)

### Notifications (NOTIF)

- [ ] **NOTIF-04**: Пользователь может подключить Telegram-бот через команду /start с привязкой к аккаунту (используется для уведомлений об открытии тендеров)
- [ ] **NOTIF-05**: Пользователь может подключить WhatsApp (Twilio) для получения уведомлений об открытии тендеров
- [ ] **NOTIF-06**: Пользователь может просмотреть и управлять watchlist (включить/отключить/удалить отслеживаемые тендеры)

### Technical Spikes — Phase 1 (SPIKE)

- [x] **SPIKE-01**: ~~Верифицировать goszakup GraphQL API~~ → **RESOLVED**: токен для Унифицированных сервисов goszakup.kz получен (2026-06-09); используем REST Unified Services API вместо GraphQL
- [x] **SPIKE-02**: Верифицировать NCALayer WebSocket протокол — **RESOLVED** (2026-05-28): dual-mode, порт 13579, 1.x=commonUtils+array+raw XML, 2.x=basics+object+base64
- [ ] **SPIKE-03**: Захватить submission payload: перехватить браузерный трафик при ручной подаче заявки на goszakup, зафиксировать все обязательные поля XML
- [ ] **SPIKE-05**: Юридическая проверка: подтвердить допустимость автоматической подачи заявок от имени компании и требования к локализации данных в РК

---

## v2 Requirements (Deferred)

- Мультикомпания (несколько компаний на одном аккаунте)
- Email-уведомления
- Самрук-Казына (zakup.sk.kz) интеграция
- Аналитика тендеров (процент выигрышей, средняя сумма)
- Рекомендации тендеров на основе истории
- Данные директора, банковские реквизиты в профиле (добавить, когда нужны для сабмита)
- Telegram: статус отправки заявки
- WhatsApp: статус отправки заявки
- **SRCH-FILTER**: Фильтры тендеров по сумме, дедлайну, региону (не нужны при lookup по ID)
- **SRCH-KEYWORD**: Поиск тендеров по ключевым словам (browse, а не lookup)
- **MP.kz интеграция** (SPIKE-04): Верифицировать и подключить MP.kz как второй источник тендеров
- **NOTIF-SUBSCRIPTION**: Подписки на фильтры поиска + уведомления о новых совпадающих тендерах (NOTIF-01, NOTIF-02, NOTIF-03)

---

## Out of Scope

- Мобильное приложение (iOS/Android) — веб достаточен для MVP
- Монетизация / подписочная модель — после валидации продукта
- Загрузка ЭЦП-ключа на сервер — безопасность: ключ не покидает устройство
- Самрук-Казына, другие платформы помимо goszakup и MP.kz — v2
- Аналитика и прогнозирование — v2
- Интеграция с бухгалтерскими системами (1С и др.) — вне скопа

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SPIKE-01 | Phase 1 — Spikes & Foundation | ✅ Resolved 2026-06-09 |
| SPIKE-02 | Phase 1 — Spikes & Foundation | ✅ Resolved 2026-05-28 |
| SPIKE-03 | Phase 1 — Spikes & Foundation | Pending |
| SPIKE-05 | Phase 1 — Spikes & Foundation | Pending |
| AUTH-01 | Phase 2 — Auth & Company Profile | Pending |
| AUTH-02 | Phase 2 — Auth & Company Profile | Pending |
| AUTH-03 | Phase 2 — Auth & Company Profile | Pending |
| AUTH-04 | Phase 2 — Auth & Company Profile | Pending |
| COMP-01 | Phase 2 — Auth & Company Profile | Pending |
| COMP-02 | Phase 2 — Auth & Company Profile | Pending |
| SRCH-01 | Phase 3 — Tender Lookup | Pending |
| SRCH-02 | Phase 3 — Tender Lookup | Pending |
| SRCH-03 | Phase 3 — Tender Lookup | Pending |
| SRCH-04 | Phase 3 — Tender Lookup | Pending |
| DOCS-01 | Phase 4 — Document Vault | Pending |
| DOCS-02 | Phase 4 — Document Vault | Pending |
| DOCS-03 | Phase 4 — Document Vault | Pending |
| DOCS-04 | Phase 4 — Document Vault | Pending |
| DOCS-05 | Phase 4 — Document Vault | Pending |
| SIGN-01 | Phase 5 — EDS Signing & Submission | Pending |
| SIGN-02 | Phase 5 — EDS Signing & Submission | Pending |
| SIGN-03 | Phase 5 — EDS Signing & Submission | Pending |
| SIGN-04 | Phase 5 — EDS Signing & Submission | Pending |
| SIGN-05 | Phase 5 — EDS Signing & Submission | Pending |
| APPL-01 | Phase 5 — EDS Signing & Submission | Pending |
| APPL-02 | Phase 5 — EDS Signing & Submission | Pending |
| APPL-03 | Phase 5 — EDS Signing & Submission | Complete |
| APPL-04 | Phase 5 — EDS Signing & Submission | Complete |
| APPL-05 | Phase 5 — EDS Signing & Submission | Complete |
| APPL-06 | Phase 5 — EDS Signing & Submission | Complete |
| APPL-07 | Phase 5 — EDS Signing & Submission | Pending |
| APPL-08 | Phase 5 — EDS Signing & Submission | Pending |
| APPL-09 | Phase 5 — EDS Signing & Submission | Pending |
| NOTIF-04 | Phase 6 — Notifications | Pending |
| NOTIF-05 | Phase 6 — Notifications | Pending |
| NOTIF-06 | Phase 6 — Notifications | Pending |

**Total v1 requirements: 36 | Mapped: 36/36**
*(SPIKE-04, SRCH-05, SRCH-06, SRCH-07, NOTIF-01, NOTIF-02, NOTIF-03 → moved to v2)*

*Traceability updated 2026-06-09 — new workflow: lookup by tenderID + auto-submit with notify+confirm*
