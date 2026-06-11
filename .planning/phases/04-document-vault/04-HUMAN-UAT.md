---
status: partial
phase: 04-document-vault
source: [04-VERIFICATION.md]
started: 2026-06-11T00:00:00Z
updated: 2026-06-11T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Навигация «Документы» в сайдбаре
expected: Sidebar рендерится с иконкой FileText и ссылкой /documents; переход происходит
result: passed — пользователь подтвердил 2026-06-11

### 2. Загрузка документа end-to-end
expected: Загрузить PDF через форму с категорией «Устав», без срока → карточка появляется в списке без бейджа, 201 от /api/documents
result: [pending]

### 3. Бейдж истечения + суммарный Alert
expected: Загрузить файл с категорией «Лицензия», срок через 5 дней → бейдж «Истекает через 7 дней» + Alert в DocumentVault
result: [pending]

### 4. Скачивание через pre-signed URL
expected: Нажать «Скачать» → window.open срабатывает, файл скачивается из MinIO
result: [pending]

### 5. Удаление документа
expected: DELETE 204 + карточка исчезает из UI; чужой doc_id → 404
result: [pending]

### 6. Клиентская валидация > 20 МБ
expected: Alert с ошибкой появляется до отправки запроса
result: [pending]

## Summary

total: 6
passed: 1
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
