---
phase: 05
slug: eds-signing-submission
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-09
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (backend), pytest-asyncio |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 05-01-01 | 01 | 1 | APPL-01 | unit | `pytest tests/test_applications.py` | ⬜ pending |
| 05-01-02 | 01 | 1 | APPL-02 | unit | `pytest tests/test_applications.py` | ⬜ pending |
| 05-02-01 | 02 | 1 | SIGN-01 | manual | See Manual-Only | ⬜ pending |
| 05-02-02 | 02 | 1 | SIGN-02 | manual | See Manual-Only | ⬜ pending |
| 05-03-01 | 03 | 2 | APPL-03 | unit | `pytest tests/test_applications.py` | ⬜ pending |
| 05-04-01 | 04 | 2 | APPL-07 | unit | `pytest tests/test_arq_workers.py` | ⬜ pending |
| 05-04-02 | 04 | 2 | APPL-08 | manual | See Manual-Only | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_applications.py` — APPL-01..03 (создаётся в 05-01 Task 3)
- [ ] `backend/tests/test_goszakup_proxy.py` — proxy client tests с respx (создаётся в 05-01 Task 3)
- [ ] `backend/tests/test_poll_watchlist.py` — APPL-07 cron polling (создаётся в 05-04 Task 1)
- [ ] `backend/tests/test_auto_submit.py` — APPL-03 auto-submit ARQ job (создаётся в 05-04 Task 2)
- [ ] `backend/tests/test_confirm_flow.py` — APPL-09 confirm + 15-min fallback (создаётся в 05-04 Task 3)
- [ ] `backend/tests/test_telegram_webhook.py` — APPL-08 webhook handler (создаётся в 05-04 Task 3)

*Existing pytest infrastructure from Phase 4 covers fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| NCALayer WebSocket подключение | SIGN-01 | Требует запущенный NCALayer на localhost | Открыть страницу, проверить индикатор статуса |
| Отображение сертификата | SIGN-02 | Требует реальный .p12 файл и NCALayer | Подключить NCALayer, выбрать сертификат, проверить имя/срок |
| Предупреждение < 30 дней | SIGN-03 | Требует сертификат с коротким сроком | Использовать тест-сертификат с exp < 30 дней |
| PIN-диалог NCALayer | SIGN-04 | Требует реальный NCALayer | Пройти флоу подписания, ввести PIN |
| Ссылка на установку | SIGN-05 | Требует отключённый NCALayer | Закрыть NCALayer, проверить UI |
| Telegram notify Да/Нет | APPL-08 | Требует реальный Telegram бот | Настроить бот, открыть тендер вручную, проверить сообщение |
| Авто-сабмит через 15 мин | APPL-09 | Требует ожидания | Не нажимать Да/Нет, ждать 15 мин, проверить статус |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
