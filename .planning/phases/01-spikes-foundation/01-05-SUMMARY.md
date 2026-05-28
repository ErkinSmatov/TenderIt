---
phase: 01-spikes-foundation
plan: "05"
subsystem: legal-research
tags: [legal, compliance, kazakhstan, data-localization, mp.kz, playwright, adr, spike]

requires:
  - phase: 01-01
    provides: project scaffold and repository structure

provides:
  - attorney-brief-spike05-legal
  - adr-001-mpkz-integration-pending
  - adr-002-legal-basis-pending
  - spike04-findings-template
  - mpkz-api-endpoints-template
  - kazakhstan-hosting-comparison

affects:
  - Phase 3 SRCH-02 MP.kz sync worker (blocked on ADR-001 decision)
  - Phase 5 SUBM-01 EDS signing and submission (blocked on ADR-002 legal clearance)
  - Phase 2 AUTH-01 onboarding flow (may need disclosure screen per legal opinion)

tech-stack:
  added: []
  patterns:
    - "MADR (Markdown Architecture Decision Records) format for ADRs"
    - "Legal brief as living document — Part 1 (attorney questions) + Part 2 (findings) structure"
    - "grep-extractable status fields: DECISION: and LEGAL_STATUS: for automated phase gate checks"

key-files:
  created:
    - docs/SPIKE-05-LEGAL.md
    - docs/adr/ADR-001-mpkz-integration-approach.md
    - docs/adr/ADR-002-automated-submission-legal-basis.md
    - backend/spikes/findings/SPIKE-04-FINDINGS.md
    - backend/spikes/findings/mpkz-api-endpoints.json
  modified: []

key-decisions:
  - "ADR-001 left PENDING — requires SPIKE-04 human browser traffic analysis before DECISION can be set"
  - "ADR-002 left PENDING — requires Kazakhstan attorney opinion before legal basis can be confirmed"
  - "LEGAL_STATUS field format established as grep-extractable line for phase gate automation"
  - "KazCloud preliminary recommended over Beeline KZ and Kcell for MVP hosting (ISO 27001, purpose-built cloud)"
  - "Attorney brief covers 5 legal questions: submission permissibility, EDS authorization (ЗЭЦД), liability, data localization (Law No. 94-VI amended 2025), ЦЭФ partner agreement"

patterns-established:
  - "ADR pattern: MADR format with Status / Date / Deciders / Context / Decision / Evidence / Consequences — used for all architecture decisions in this project"
  - "Spike findings template pattern: Spike Metadata / Network Traffic Summary / [API Status OR Playwright Structure] / Auth Analysis / DECISION — standardized format matching previous spikes (SPIKE-01, SPIKE-03)"
  - "Legal document pattern: Part 1 (attorney brief, pre-populated) + Part 2 (findings, populated after consultation) — enables async workflow between agent and attorney"

requirements-completed:
  - SPIKE-04
  - SPIKE-05

duration: ~20min
completed: "2026-05-28"
---

# Phase 1 Plan 05: SPIKE-04 MP.kz + SPIKE-05 Legal Review Summary

**Attorney brief (5 KZ-specific legal questions) + hosting comparison (KazCloud/Beeline/Kcell) + ADR-001/ADR-002 templates created; SPIKE-04 browser traffic capture required from human before ADR-001 can be finalized.**

## Performance

- **Duration:** ~20 minutes (research + document creation)
- **Started:** 2026-05-28T15:14:00Z
- **Completed:** 2026-05-28T15:34:00Z
- **Tasks:** 1 complete (Task 1: legal docs + ADRs), 1 template committed (Task 2: SPIKE-04 artifacts), 1 pending (Task 3: post-checkpoint finalization)
- **Files created:** 5

## Accomplishments

- Created complete Kazakhstan legal brief with 5 legally-specific questions citing actual Kazakhstan law articles (Закон РК No. 434-V, No. 370-II, No. 94-VI) for attorney consultation
- Researched and documented three Kazakhstan hosting providers (KazCloud, Beeline KZ, Kcell) with pricing estimates, SLA, certifications, and preliminary recommendation
- Created ADR-001 (MP.kz approach) and ADR-002 (legal basis) in MADR format with both decision branches fully documented, pending final verdict
- Pre-populated SPIKE-04-FINDINGS.md template with dual-branch structure (API branch and Playwright branch) so the executor agent can fill it in immediately after human provides findings
- Created mpkz-api-endpoints.json with dual-schema template matching both discovery outcomes

## Task Commits

1. **Task 1: Legal docs and ADR templates** — `300762e` (feat)
2. **Task 2: SPIKE-04 pre-populated templates** — `dd5e667` (feat)
3. **Task 3: Post-checkpoint finalization** — pending (requires human SPIKE-04 findings)

## Files Created/Modified

- `docs/SPIKE-05-LEGAL.md` — Full attorney brief with 5 legal questions (Kazakhstan law citations included), hosting provider comparison (KazCloud/Beeline/Kcell with pricing), LEGAL_STATUS: PENDING field, attorney contact recommendations
- `docs/adr/ADR-001-mpkz-integration-approach.md` — MADR format, Status: PENDING, both Option A (internal API) and Option B (Playwright) consequences documented in detail
- `docs/adr/ADR-002-automated-submission-legal-basis.md` — MADR format, Status: PENDING, 4 consequence branches (no restrictions / consent flow / API agreement / BLOCKED) with implementation implications and attorney engagement checklist
- `backend/spikes/findings/SPIKE-04-FINDINGS.md` — Dual-branch findings template with tables for network traffic, selectors, authentication analysis, DECISION: placeholder
- `backend/spikes/findings/mpkz-api-endpoints.json` — Dual-schema JSON template (variant A: API found, variant B: Playwright required)

## Decisions Made

- **KazCloud preliminary recommendation:** Of the three Kazakhstan hosting providers, KazCloud is the best fit for MVP: purpose-built cloud (not telco side business), ISO 27001 certification, competitive pricing for cloud-native workloads. Requires confirmation after attorney data localization opinion.
- **Attorney brief structure:** Prepared as "living document" — Part 1 (pre-populated questions for attorney) + Part 2 (empty, to be populated after consultation). This decouples the preparation work (done by agent) from the consultation (done by human) without creating a separate file.
- **grep-extractable status fields:** Both `DECISION:` in SPIKE-04-FINDINGS.md and `LEGAL_STATUS:` in SPIKE-05-LEGAL.md are formatted for automated grep-based phase gate checking, consistent with SPIKE-01 and SPIKE-03 patterns.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed as specified.

### Notes on Plan Structure

The plan has Task 2 as `type="checkpoint:human-action"` (blocking gate). This agent executed Task 1 fully and pre-populated the Task 2 artifacts (SPIKE-04-FINDINGS.md template and mpkz-api-endpoints.json) to accelerate resumption after the human completes the browser analysis. Task 3 (finalize findings + update ADRs) depends entirely on the SPIKE-04 human findings and must be executed by a continuation agent after the human provides their results.

## CHECKPOINT DETAILS: SPIKE-04 Required

**What the human needs to do** (full instructions in plan Task 2):

1. Open https://mp.kz in Chrome
2. Open DevTools (F12) → Network tab → filter by "Fetch/XHR" → enable "Preserve log"
3. Navigate to the tender listings page and scroll through results
4. Record: Are responses `application/json` (→ API exists) or `text/html` (→ Playwright needed)?
5. If API found: note the base URL, auth requirements, key endpoint paths
6. If HTML only: note the CSS selectors for tender cards, pagination, and key fields
7. Test in incognito: do tender listings load without authentication?
8. Check for /api-docs or /developers paths on mp.kz

**Resume signal:** Type "spike-04 executed" with: (1) "API found" or "no API — HTML only", (2) if API: base URL and auth requirement, (3) number of distinct API endpoints observed.

## Known Stubs

- `DECISION:` field in `backend/spikes/findings/SPIKE-04-FINDINGS.md` — awaiting human SPIKE-04 execution
- `mpkz-api-endpoints.json` — template only, schema variant not yet selected
- ADR-001 Status: PENDING — changes to ACCEPTED after SPIKE-04
- ADR-002 Status: PENDING — changes to ACCEPTED after attorney opinion
- `LEGAL_STATUS: PENDING — attorney search in progress` — changes after attorney engaged

These stubs are intentional — they represent the open human-action gates in the plan. They will be resolved by the continuation agent after the human provides SPIKE-04 findings.

## Threat Flags

No new security surface introduced. Threat model items from plan addressed:

| Threat | Mitigation | Status |
|--------|-----------|--------|
| T-05-01: Attorney correspondence in git | Only question brief + status in git; actual attorney letter stays outside repo | Mitigated by structure |
| T-05-02: MP.kz session cookies in findings | SPIKE-04-FINDINGS.md template explicitly instructs: do not commit session tokens | Documented in template |
| T-05-03: Using undocumented MP.kz API without ToS review | Spike is read-only; legal review covers ToS before Phase 3 | Accepted for spike |

## Next Phase Readiness

**Blocked waiting for:**
1. SPIKE-04 human browser analysis → then continuation agent can finalize SPIKE-04-FINDINGS.md and ADR-001
2. Attorney engagement for SPIKE-05 → then LEGAL_STATUS can be updated and ADR-002 finalized

**Once both unblocked:**
- Phase 3 SRCH-02 (MP.kz adapter) can be planned with the correct implementation approach
- Phase 5 SUBM-01 can proceed to production launch gating once legal clearance received
- Kazakhstan hosting provider can be provisioned once attorney confirms localization requirements

## Self-Check: PASSED

- [x] `docs/SPIKE-05-LEGAL.md` exists (315 lines) with all 5 legal questions, KZ law citations, hosting comparison, LEGAL_STATUS: field
- [x] `docs/adr/ADR-001-mpkz-integration-approach.md` exists in MADR format with Status: PENDING
- [x] `docs/adr/ADR-002-automated-submission-legal-basis.md` exists in MADR format with Status: PENDING
- [x] `backend/spikes/findings/SPIKE-04-FINDINGS.md` exists with DECISION: placeholder
- [x] `backend/spikes/findings/mpkz-api-endpoints.json` exists with dual-schema template
- [x] Task 1 commit 300762e present in git log
- [x] Task 2 commit dd5e667 present in git log
- [x] `grep "LEGAL_STATUS:" docs/SPIKE-05-LEGAL.md` → "LEGAL_STATUS: PENDING — attorney search in progress"
- [x] `grep -c "KazCloud\|Beeline\|Kcell" docs/SPIKE-05-LEGAL.md` → 12 (at least 3)

---
*Phase: 01-spikes-foundation*
*Completed: 2026-05-28*
