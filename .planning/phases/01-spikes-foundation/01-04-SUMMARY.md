---
phase: 01-spikes-foundation
plan: "04"
subsystem: backend/spikes
tags: [spike, goszakup, submission-payload, xml-signing, ncalayer, field-registry]
dependency_graph:
  requires:
    - 01-01 (backend scaffold — spikes directory lives in backend/)
  provides:
    - spike-03-findings-template
    - goszakup-submission-field-registry-provisional
    - ncalayer-signing-xml-structure-template
    - traffic-capture-guide
  affects:
    - Phase 5 APPL-03 SubmissionService (XML assembly Jinja2 template)
    - Phase 5 NCALayer browser hook (signedXml field structure)
tech_stack:
  added: []
  patterns:
    - Pre-populated spike template pattern (known fields + [TO FILL] markers)
    - HAR/raw-captures gitignored at project root (T-04-01 mitigation)
    - Anonymized sample artifacts (BIN/IIN placeholders, REDACTED tokens)
key_files:
  created:
    - backend/spikes/findings/SPIKE-03-FINDINGS.md
    - backend/spikes/findings/sample-submission-payload.json
    - backend/spikes/findings/sample-submission.xml
  modified:
    - .gitignore (added raw-captures/ and *.har exclusions)
decisions:
  - "D-S03-01 PROVISIONAL: Jinja2 XML template for Phase 5 payload assembly — confirm after live capture"
  - "D-S03-02 PROVISIONAL: UTF-8 encoding for signed XML — confirm from captured XML declaration"
  - "D-S03-03 PROVISIONAL: Two-call document attachment (upload → fileId → link) — confirm from capture"
  - "raw-captures/ and *.har gitignored from the start — protects session tokens and PII before any capture"
metrics:
  duration: "~20 minutes (template creation)"
  completed_date: "2026-05-28"
  tasks_completed: 0
  tasks_pending: 1
  tasks_total: 2
  files_created: 3
---

# Phase 1 Plan 04: SPIKE-03 goszakup Submission Payload Capture Summary

**One-liner:** Pre-populated SPIKE-03 template with 28 known goszakup v3 API fields in FIELD REGISTRY, NCALayer XMLDSig XML structure, multi-step submission flow, and step-by-step Chrome DevTools capture guide — awaiting live traffic capture.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| pre-checkpoint | Create spike template artifacts | 3f76aac | SPIKE-03-FINDINGS.md, sample-submission-payload.json, sample-submission.xml, .gitignore |

## Tasks Pending (Awaiting Human Action)

| Task | Name | Blocked By |
|------|------|-----------|
| 1 | SPIKE-03: Capture goszakup submission payload via browser DevTools | Human must log in to goszakup with real supplier account and record network traffic |
| 2 | Analyze captures and write final SPIKE-03-FINDINGS.md | Depends on Task 1 |

## Checkpoint: Awaiting Human Traffic Capture

This plan has `autonomous: false` — the core spike work (Task 1) is a human-executed browser investigation. No code can substitute for a real authenticated goszakup session with an eligible tender.

**What was done autonomously (pre-checkpoint):**
- Created `SPIKE-03-FINDINGS.md` (394 lines) with all 28 publicly-known goszakup v3 API submission fields pre-populated in the FIELD REGISTRY table, signed XML structure documented from NCALayer protocol specs, multi-step flow outline, all three decisions (D-S03-01/02/03) marked as provisional, and a complete traffic capture guide embedded directly in the document.
- Created `sample-submission-payload.json` with full anonymized JSON structure and `_TODO_confirm_from_capture` checklist.
- Created `sample-submission.xml` with both unsigned and signed XML structure templates (XMLDSig + CMS/PKCS#7 variants documented).
- Added `raw-captures/` and `*.har` to `.gitignore` (threat T-04-01 mitigation) before any capture happens.

**What requires human action (Task 1):**
See the detailed guide in `backend/spikes/findings/SPIKE-03-FINDINGS.md` under "Traffic Capture Guide". Summary:

1. Open Chrome → DevTools → Network tab → enable "Preserve log" + "Disable cache" → filter "Fetch/XHR"
2. Log in to `https://v3bl.goszakup.gov.kz` with a real supplier account
3. Navigate to an eligible tender and begin the application flow
4. For each API call: right-click → "Copy as cURL" → save to `backend/spikes/findings/raw-captures/`
5. At the signing step: also capture the WebSocket message to NCALayer (DevTools → Network → WS tab → ws://localhost:14579 → Messages tab, copy `xmlToSign` value)
6. If safe to submit: complete the submission and record the response
7. Export HAR: Network tab → export button → save as `goszakup-submission-session.har` (gitignored)
8. Anonymize all captures (replace BIN, IIN, tokens) and fill in the `[TO FILL]` fields in SPIKE-03-FINDINGS.md

**Resume signal:** After completing the capture, type:
`spike-03 captured` with a summary of: (1) whether you reached the signed submission step, (2) how many distinct API calls observed, (3) the host domain of the submission endpoint (e.g., `v3bl.goszakup.gov.kz`)

## Deviations from Plan

**1. [Autonomous pre-work added] Template artifacts created before checkpoint**
- The plan's success criteria required findings files to exist, but Task 1 is a human-action checkpoint.
- Rather than creating empty files, all publicly-known fields were pre-populated so Task 2 (the analysis) has a solid base to fill in from capture data rather than starting from scratch.
- This reduces the human work in Task 2 to "fill in [TO FILL] markers" rather than "write from blank".

**2. .gitignore updated proactively (threat mitigation T-04-01)**
- Added raw-captures/ and *.har to .gitignore before any capture is performed.
- Ensures the gitignore is in place before the human starts the capture session — eliminates risk of accidentally staging HAR files.

## Known Stubs

The three findings files are intentionally template/stub state:
- `SPIKE-03-FINDINGS.md`: 28 fields in FIELD REGISTRY are pre-populated from documentation; all `[TO FILL]` markers require live capture.
- `sample-submission-payload.json`: Structural template only; the actual field nesting (flat vs `data.*`), enum types, and submission URL are `[TO CONFIRM]`.
- `sample-submission.xml`: Root element name, namespace URI, and signature algorithm are provisional (XMLDSig vs CMS/PKCS#7 TBD).

These stubs are INTENTIONAL — they represent pre-capture knowledge. The stubs will be resolved in Task 2 after the human completes Task 1.

## Threat Mitigations Applied

| Threat ID | Description | Status |
|-----------|-------------|--------|
| T-04-01 | HAR file with session cookies committed | Mitigated — raw-captures/ and *.har added to .gitignore before capture |
| T-04-02 | BIN/IIN in sample files | Mitigated — all sample files use placeholder values (123456789012, 000000000000) |
| T-04-03 | Accidental binding tender submission | Documented in guide — capture can stop at signing step |
| T-04-04 | mitmproxy CA left in trust store | Documented removal command in capture guide |

## Self-Check: PASSED

- [x] `backend/spikes/findings/SPIKE-03-FINDINGS.md` exists (394 lines, above 150-line minimum)
- [x] `grep -c "FIELD REGISTRY" SPIKE-03-FINDINGS.md` returns 2 (section heading + table header)
- [x] `sample-submission-payload.json` exists with PII placeholders
- [x] `sample-submission.xml` exists with PII placeholders and [SIGNATURE_BYTES_REDACTED]
- [x] No unredacted auth tokens: `grep -ri "Bearer [a-zA-Z0-9]{20,}" backend/spikes/findings/` returns nothing
- [x] HAR files not tracked: `.gitignore` includes `*.har` and `raw-captures/`
- [x] Commit 3f76aac present in git log
- [x] All three decisions (D-S03-01, D-S03-02, D-S03-03) present in FINDINGS.md with PROVISIONAL status
