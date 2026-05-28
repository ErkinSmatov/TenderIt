---
phase: 01-spikes-foundation
plan: 03
subsystem: infra
tags: [ncalayer, websocket, eds, signing, spike, pki, kazakhstan]

requires:
  - phase: 01-01
    provides: monorepo scaffold — frontend/spikes/ directory target exists

provides:
  - Standalone NCALayer WebSocket test harness (frontend/spikes/ncalayer-test.html)
  - Pre-structured SPIKE-02-FINDINGS.md template awaiting live test data
  - frontend/spikes/findings/ directory for session log capture

affects:
  - phase-05 signing (SIGN-01 through SIGN-05 — useNCALayer() hook built against confirmed protocol)
  - 01-03 continuation agent (fills [TO FILL] entries after user runs the harness)

tech-stack:
  added: []
  patterns:
    - "NCALayer browser-only pattern: all signing via WebSocket to 127.0.0.1 — backend never touches NCALayer"
    - "Spike harness pattern: standalone file:// HTML with no CDN dependencies"
    - "JSON-RPC over WebSocket: module/method/args envelope for kz.gov.pki.knca.basics"

key-files:
  created:
    - frontend/spikes/ncalayer-test.html
    - frontend/spikes/SPIKE-02-FINDINGS.md
    - frontend/spikes/findings/.gitkeep
  modified: []

key-decisions:
  - "NCALayer test harness is browser-only (file:// URL) — no server component, consistent with CLAUDE.md architectural rule"
  - "kz.gov.pki.knca.basics used as primary module; kz.gov.pki.knca.commonUtils included as documented fallback"
  - "FINDINGS.md pre-populated with all MEDIUM-confidence data from research; [TO FILL] markers for live-test confirmation"
  - "D-S02 decisions (01-05) deferred until live test — port, module, keyType, signXml format, GOST verdict all pending"

patterns-established:
  - "Spike template pattern: create harness + pre-populated findings template before user runs live test"
  - "NCALayer signing flow: getKeyInfo to list certs → filter by keyType != AUTH → signXml with SIGNATURE cert → return base64 signed XML to backend"

requirements-completed:
  - SPIKE-02

duration: 12min
completed: 2026-05-28
---

# Phase 01 Plan 03: SPIKE-02 NCALayer WebSocket Test Harness Summary

**Standalone NCALayer WebSocket test harness and pre-populated SPIKE-02-FINDINGS.md template built — live test with real ЭЦП certificate required to confirm port, module, and signXml format before Phase 5 can begin.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-05-28T09:41:14Z
- **Completed:** 2026-05-28T09:53:41Z
- **Tasks:** 2 (Task 1 complete; Task 3 pre-populated; Task 2 is blocking human-action checkpoint)
- **Files created:** 3

## Accomplishments

- Built complete 670-line standalone HTML test harness (`ncalayer-test.html`) covering all required NCALayer methods: getVersion, getKeyInfo, browseKeyStore, signXml, createCMSSignatureFromBase64
- Pre-populated `SPIKE-02-FINDINGS.md` (328 lines) with all MEDIUM-confidence data from research, structured for direct continuation after live test with `[TO FILL]` markers
- Confirmed CLAUDE.md architectural constraints are enforced: browser-only, no backend WebSocket connection, private keys never leave device, test XML is non-binding

## Task Commits

1. **Task 1: NCALayer HTML test harness** - `c62fd1c` (feat)
2. **Task 3 pre-work: SPIKE-02-FINDINGS.md template + findings/ dir** - `eb6eacb` (feat)

**Plan metadata (SUMMARY.md):** committed with final docs commit

## Files Created

- `frontend/spikes/ncalayer-test.html` — 670-line standalone test harness, no external deps, works as file:// URL
- `frontend/spikes/SPIKE-02-FINDINGS.md` — 328-line findings template; 4 CONFIRMED_PORT occurrences, all 5 D-S02 decisions present
- `frontend/spikes/findings/.gitkeep` — directory placeholder for `spike-02-session-log.json` captured during live test

## Decisions Made

- Pre-populating SPIKE-02-FINDINGS.md before the live test (rather than waiting for checkpoint completion) enables the continuation agent to fill in only the delta after the user runs the harness — reducing human error in transcription.
- Used `kz.gov.pki.knca.basics` as primary module and included commonUtils as a clearly labeled fallback in inline comments. The distinction matters: if the user's NCALayer version only supports commonUtils, the continuation agent needs the fallback paths to be documented.
- Both ports (13579 primary, 14579 fallback) are pre-filled in the connection panel URL inputs with prominent netstat verification instructions.

## Deviations from Plan

**1. [Proactive - scope clarification] Task 3 executed as template creation before checkpoint**
- **Context:** Plan marks Task 2 as a `checkpoint:human-action` and Task 3 as an auto task after resume. The `<important_context>` explicitly instructs: "Write a detailed SPIKE-02-FINDINGS.md template with all required sections pre-populated with known information from NCALayer public docs, leaving blanks for fields that require live testing."
- **Action:** Created the full SPIKE-02-FINDINGS.md template now (pre-checkpoint) with all known data and `[TO FILL]` markers. The continuation agent after live test only needs to replace the markers.
- **Impact:** No scope creep — this is the plan intent per `<important_context>`. Saves a full round-trip for the continuation agent.

## Known Stubs

The following `[TO FILL]` entries in SPIKE-02-FINDINGS.md require live test data:

| Field | File | Reason |
|-------|------|--------|
| CONFIRMED_PORT actual value | frontend/spikes/SPIKE-02-FINDINGS.md | Requires netstat on NCALayer machine |
| getVersion response JSON | frontend/spikes/SPIKE-02-FINDINGS.md | Requires live WebSocket connection |
| getKeyInfo response JSON | frontend/spikes/SPIKE-02-FINDINGS.md | Requires live NCALayer + certificate |
| signXml request/response JSON | frontend/spikes/SPIKE-02-FINDINGS.md | Requires live signing with PIN |
| All D-S02-01 through D-S02-05 verdicts | frontend/spikes/SPIKE-02-FINDINGS.md | Requires live test observations |

These stubs are intentional and expected — they are the purpose of the checkpoint. The continuation agent fills them in after the user runs the harness.

## Threat Flags

No new network endpoints or auth paths introduced. Both files are local artifacts only:
- `ncalayer-test.html` is opened as `file://` on the user's machine — never served.
- `SPIKE-02-FINDINGS.md` is a documentation file — no runtime behavior.

T-03-01 through T-03-04 mitigations from the plan's threat model are implemented:
- Warning banner in HTML instructs use of test/development certificate, not production key
- PIN is entered in NCALayer's native OS dialog, not in the HTML page (verified: no password input field in test harness)
- Test XML is non-binding: `<tender><id>TEST-001</id><amount>100000</amount></tender>`

## Issues Encountered

None during harness and template creation.

## Next Phase Readiness

**Blocked on:** User running `ncalayer-test.html` against a live NCALayer installation with a real ЭЦП certificate and providing the session log + confirmed port/module/keyType data.

**After live test:** Continuation agent fills in all `[TO FILL]` entries in SPIKE-02-FINDINGS.md using the `spike-02-session-log.json`, commits the completed findings, and closes SPIKE-02.

**After SPIKE-02 closes:** Phase 5 (SIGN-01 through SIGN-05) has the confirmed protocol specification to build `useNCALayer()` against. Without the completed SPIKE-02-FINDINGS.md, Phase 5 implementation would be built against community assumptions (MEDIUM confidence) — unacceptable for a production legal signing flow.

---
*Phase: 01-spikes-foundation*
*Completed: 2026-05-28*
