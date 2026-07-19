---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 07
current_plan: 1
status: executing
last_updated: "2026-07-19T10:32:00.967Z"
progress:
  total_phases: 7
  completed_phases: 5
  total_plans: 28
  completed_plans: 22
  percent: 79
---

# TenderIt — Project State

## Project Reference

**Core value:** Подача тендерной заявки за 3 клика: нашли → подписали ЭЦП → отправлено автоматически.
**Stack:** Next.js 14 + FastAPI + PostgreSQL 16 + Redis + ARQ + MinIO
**Platforms v1:** goszakup.gov.kz + MP.kz
**Target user:** Директор / ИП малого бизнеса в Казахстане

---

## Current Position

Phase: 07 (discovery-matching) — EXECUTING
Plan: 1 of 6
**Milestone:** v1 MVP
**Current Phase:** 07
**Current Plan:** 1
**Status:** Executing Phase 07

```
Progress: [██████████] 100%
Phase 1 of 6
```

---

## Phase Completion

| Phase | Status | Completed |
|-------|--------|-----------|
| 1. Spikes & Foundation | Not started | - |
| 2. Auth & Company Profile | Not started | - |
| 3. Tender Data Pipeline | Not started | - |
| 4. Document Vault | Not started | - |
| 5. EDS Signing & Submission | Not started | - |
| 6. Notifications | Not started | - |

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Requirements total | 39 |
| Requirements complete | 0 |
| Phases complete | 0 / 6 |
| Plans complete | 0 |
| Plans total | TBD |

---
| Phase 05 P03 | ~46min | 3 tasks | 18 files |
| Phase 05 P04 | 18min | 3 tasks | 14 files |

## Accumulated Context

### Key Decisions Pending

- **goszakup submission payload fields** — unknown until SPIKE-03 completes. Phase 5 (SIGN/APPL) must not begin until this spike result is documented.
- **MP.kz integration approach** — REST/GraphQL vs. Playwright scraping. Determined by SPIKE-04.
- **pyhanko GOST-3410-2012-512 support** — must verify in SPIKE-02. If absent, NCANode (Node.js sidecar) is the fallback — adds Docker service.
- **KZ data localization provider** — must select KZ-hosted infrastructure (KazCloud / Beeline KZ / Kcell) before Phase 4 onboards real user documents. Gated by SPIKE-05 legal review.
- **NCALayer WebSocket envelope format** — exact JSON shape for `signXml` call. Determined by SPIKE-02.

### Architecture Constraints

- NCALayer runs on the user's machine; the server never calls it. All NCALayer interactions are browser-only via `useNCALayer()` React hook.
- Submission pipeline is three-stage: (1) FastAPI assembles XML payload, (2) browser sends to NCALayer, (3) browser POSTs signed XML to FastAPI which calls goszakup mutation.
- Signed XML must be stored in PostgreSQL before first submission attempt (durable retry requires idempotent signed document).
- One account = one company (v1 constraint; multi-company is v2).

### Open Blockers

| Blocker | Gates | Resolution |
|---------|-------|------------|
| SPIKE-01: goszakup schema unverified | Phase 3 goszakup sync | Run spike |
| SPIKE-02: NCALayer message envelope unknown | Phase 5 SIGN | Run spike on Windows VM |
| SPIKE-03: submission payload fields unknown | Phase 5 APPL | Browser traffic capture |
| SPIKE-04: MP.kz API approach unknown | Phase 3 MP.kz adapter | Network traffic analysis |
| SPIKE-05: legal review not done | Phase 5 launch | Engage KZ attorney |

### Todos

- [ ] Initialize project scaffold (Next.js 14 + FastAPI + PostgreSQL + Redis + MinIO + ARQ + Docker Compose)
- [ ] Set up CI/CD skeleton (lint, test, build pipeline)
- [ ] Run SPIKE-01 through SPIKE-05 and document findings in `/docs/spikes/`
- [ ] Select KZ-hosted infrastructure provider before Phase 4 begins
- [ ] Recruit 2-3 beta users at end of Phase 3 (tender search functional, can validate with real tenders)

---

## Session Continuity

**Last updated:** 2026-07-18
**Last action:** 05-03 complete — portal proxy (steps 1-11), useCryptoSocket hook, 4-step ApplicationWizard
**Next action:** 05-04 — ARQ submission worker + Telegram/WhatsApp notifications

---

## Notes

- Research SUMMARY.md flags Phases 1 and 4 as needing additional research before planning. Phase 1 is self-contained (spikes ARE the research). Phase 4 planning should incorporate SPIKE-02 and SPIKE-03 findings.
- No goszakup sandbox environment is known to exist — all spike testing runs against production. Use conservative call rates from day one.
- `commit_docs: true` in config.json — all planning file changes should be committed.
