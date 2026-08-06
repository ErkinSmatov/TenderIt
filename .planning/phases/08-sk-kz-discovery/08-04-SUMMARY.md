---
phase: 08-sk-kz-discovery
plan: "04"
subsystem: frontend
tags: [discovery, sk-kz, source-badge, portal-link, typescript]
dependency_graph:
  requires: ["08-02"]
  provides: ["SC-08-03", "SC-08-05"]
  affects: [frontend/src/types/discovery.ts, frontend/src/components/discovery/TenderMatchCard.tsx]
tech_stack:
  added: []
  patterns: [conditional-rendering, component-composition, dynamic-badge]
key_files:
  modified:
    - frontend/src/types/discovery.ts
    - frontend/src/components/discovery/TenderMatchCard.tsx
decisions:
  - "SourceBadge defined in same file as TenderMatchCard — no separate file needed for a small helper"
  - "Manual sk.kz note placed after isActionable block to stay visible in the participating state"
  - "portal_url anchor uses rel='noopener noreferrer' + target='_blank' per threat model T-08-10"
metrics:
  duration: "~10 min"
  completed: "2026-08-06"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 8 Plan 4: Frontend — SourceBadge, portal link, sk.kz participation note — Summary

## One-liner

Dynamic SourceBadge in TenderMatchCard with blue/gray styling per source, portal_url anchor, and amber participation note for sk.kz tenders.

## What Was Built

### Task 1: Extend TenderMatchResponse TypeScript interface

Added two new optional fields to `TenderMatchResponse` in `frontend/src/types/discovery.ts`:
- `source: string | null` — value `'goszakup'` or `'sk_kz'`, `null` for records before Phase 8
- `portal_url: string | null` — direct link to tender on source portal; `null` for goszakup

Updated JSDoc to note that these fields are populated from the Tender JOIN in Phase 8.

### Task 2: Update TenderMatchCard — SourceBadge, portal link, sk.kz note

Three targeted changes to `frontend/src/components/discovery/TenderMatchCard.tsx`:

**CHANGE 1 — SourceBadge component** added above the main component:
- Label: `'SK.KZ'` for `sk_kz`, `'ГОСЗАКУП'` for all other values
- Color: blue (`border-blue-200 bg-blue-50 text-blue-700`) for sk_kz, gray (`border-gray-200 bg-gray-100 text-gray-600`) for others
- When `portalUrl` is truthy, wraps badge in `<a href={portalUrl} target="_blank" rel="noopener noreferrer">`

**CHANGE 2 — Replace hardcoded badge**: the `<span>goszakup</span>` in the "Источник" cell replaced with `<SourceBadge source={match.source} portalUrl={match.portal_url} />`

**CHANGE 3 — sk.kz participation note**: added after the action buttons block, conditionally rendered when `match.source === 'sk_kz' && match.status === 'participating'`:
```
Заявку нужно подать вручную на zakup.sk.kz
```
styled with `text-xs text-amber-600`.

## Verification Results

| Check | Result |
|-------|--------|
| `npx tsc --noEmit` | Exits 0 — no TypeScript errors |
| `grep -c "SourceBadge" TenderMatchCard.tsx` | 2 (definition + usage) |
| `grep -c "SK.KZ" TenderMatchCard.tsx` | 1 |
| `grep -c "ГОСЗАКУП" TenderMatchCard.tsx` | 1 |
| `grep -n rel="noopener noreferrer"` | Line 59 confirmed |
| `grep -c "source: string \| null" discovery.ts` | 1 |
| `grep -n "goszakup" TenderMatchCard.tsx` (hardcoded) | 0 — fully removed |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | `9824ebf` | feat(08-04): extend TenderMatchResponse with source and portal_url fields |
| Task 2 | `72b01c7` | feat(08-04): add dynamic SourceBadge, portal link and sk.kz participation note |

## Deviations from Plan

None — plan executed exactly as written.

## Security Notes

Threat T-08-10 mitigated: `rel="noopener noreferrer"` + `target="_blank"` on portal_url anchor.  
`portal_url` is computed server-side from a fixed template — no user-controlled input in the URL.

## Self-Check: PASSED

All files confirmed present. Both commits verified in git log.
